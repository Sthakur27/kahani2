"""AI helpers for StorySim: polish rough notes into a node, and generate the
running 'story so far' summary.

Currently STUBBED — no Anthropic API key is required. The stub derives plausible
output locally. If ANTHROPIC_API_KEY is set, the real Claude calls are used
instead automatically (model claude-opus-4-8)."""
import json
import os

MODEL = "claude-opus-4-8"

_client = None


def ai_available() -> bool:
    # Always available — falls back to a local stub when there's no API key.
    return True


def _has_key() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def _get_client():
    global _client
    if _client is None:
        import anthropic

        _client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
    return _client


# --------------------------------------------------------------------------- #
# Public API (dispatches to Claude when a key is set, else the local stub)
# --------------------------------------------------------------------------- #
def draft_node(story, parent, bullets: str) -> dict:
    """Turn rough bullet notes into {edge_prompt, content}, using story context."""
    if _has_key():
        return _claude_draft(story, parent, bullets)
    return _stub_draft(story, parent, bullets)


def summarize_path(story, ancestors, node) -> str:
    """Generate summary_so_far for `node`, given its ancestor chain (root → parent)."""
    if _has_key():
        return _claude_summary(story, ancestors, node)
    return _stub_summary(story, ancestors, node)


GENRES = ["sci-fi", "fantasy", "mystery", "horror"]
RATINGS = ["pg", "mature"]


def generate_daily(genre: str, rating: str) -> dict:
    """Generate a daily prompt {title, blurb} for a genre + rating."""
    if _has_key():
        return _claude_generate_daily(genre, rating)
    return _stub_generate_daily(genre, rating)


def moderate_text(text: str, rating: str = "pg") -> dict:
    """Screen user-submitted text. Returns {'allowed': bool, 'reason': str|None}.
    Stricter for PG content."""
    if _has_key():
        return _claude_moderate(text, rating)
    return _stub_moderate(text, rating)


# --------------------------------------------------------------------------- #
# Local stubs (no API key needed)
# --------------------------------------------------------------------------- #
def _bullet_lines(bullets: str) -> list[str]:
    lines = [l.strip(" -*\t") for l in bullets.splitlines()]
    lines = [l for l in lines if l]
    return lines or [bullets.strip()]


def _as_sentence(text: str) -> str:
    text = text.strip()
    if not text:
        return ""
    text = text[0].upper() + text[1:]
    if text[-1] not in ".!?":
        text += "."
    return text


def _first_sentence(text: str) -> str:
    head = text.split(".")[0].strip()
    return head + "." if head else ""


def _stub_draft(story, parent, bullets: str) -> dict:
    lines = _bullet_lines(bullets)
    edge_words = lines[0].split()[:6]
    edge_prompt = " ".join(edge_words)
    edge_prompt = (edge_prompt[0].upper() + edge_prompt[1:]) if edge_prompt else "Continue"
    content = " ".join(_as_sentence(l) for l in lines)
    return {"edge_prompt": edge_prompt, "content": content}


def _stub_summary(story, ancestors, node) -> str:
    bits = [_first_sentence(story.blurb)]
    for n in [*ancestors, node]:
        if n.edge_prompt:
            choice = n.edge_prompt[0].lower() + n.edge_prompt[1:]
            bits.append(f"You chose to {choice}.")
        else:
            bits.append(_first_sentence(n.content))
    return " ".join(b for b in bits if b)


# --------------------------------------------------------------------------- #
# Real Claude calls (used when ANTHROPIC_API_KEY is set)
# --------------------------------------------------------------------------- #
_DRAFT_SYSTEM = (
    "You help authors write branches of a collaborative, choose-your-own-adventure "
    "story. Given the story so far and a few rough notes, produce two things: a short "
    "'story path' — the choice or action label that leads into this branch (a handful "
    "of words, like a button), and a polished 'blurb' — a vivid 2-4 sentence passage "
    "that continues the story. Match the tone, tense, and point of view of the existing "
    "story."
)

_SUMMARY_SYSTEM = (
    "You write the 'story so far' recap for a choose-your-own-adventure reader. "
    "Given the prompt and the path of passages taken, write a single concise paragraph "
    "(2-4 sentences) recapping the journey from the beginning up to and including the "
    "latest passage. Keep the tense and point of view of the story; present it as one "
    "continuous narrative, not a list."
)


def _claude_draft(story, parent, bullets: str) -> dict:
    client = _get_client()
    if parent is None:
        preceding = f"This branch responds directly to the story's opening prompt:\n{story.blurb}"
    else:
        preceding = f"This branch continues from the preceding passage:\n{parent.content}"
    user = (
        f"STORY TITLE: {story.title}\n"
        f"STORY PROMPT: {story.blurb}\n\n"
        f"{preceding}\n\n"
        f"THE AUTHOR'S ROUGH NOTES:\n{bullets}\n\n"
        "Polish these into the story path label and the blurb."
    )
    resp = client.messages.create(
        model=MODEL,
        max_tokens=1024,
        system=_DRAFT_SYSTEM,
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "edge_prompt": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["edge_prompt", "content"],
                    "additionalProperties": False,
                },
            },
        },
        messages=[{"role": "user", "content": user}],
    )
    text = next(b.text for b in resp.content if b.type == "text")
    return json.loads(text)


def _claude_summary(story, ancestors, node) -> str:
    client = _get_client()
    lines = [f"STORY PROMPT: {story.blurb}"]
    for n in [*ancestors, node]:
        if n.edge_prompt:
            lines.append(f"CHOICE: {n.edge_prompt}")
        lines.append(n.content)
    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_SUMMARY_SYSTEM,
        output_config={"effort": "low"},
        messages=[{"role": "user", "content": "\n".join(lines)}],
    )
    return next(b.text for b in resp.content if b.type == "text")


# --------------------------------------------------------------------------- #
# Daily generation + moderation — stubs
# --------------------------------------------------------------------------- #
import random  # noqa: E402

_PROMPT_POOL = {
    "sci-fi": [
        ("The Last Transmission", "Your colony ship's AI wakes you 400 years early. It won't say why — only that, of the 3,000 sleepers aboard, you are the one it trusts. The airlock to the bridge is already open."),
        ("Salvage Rights", "The derelict has been drifting dark for a century, and the law says first aboard owns whatever's inside. You cut through the hull and the lights flicker on to greet you by name."),
        ("Quiet Sky", "Every satellite went silent at 3:02 a.m. — except one, which is now broadcasting a countdown in a language no one has spoken for a thousand years. You're the only analyst left awake."),
    ],
    "fantasy": [
        ("The Debt Collector's Apprentice", "Your master collects debts owed to the old gods, and today she handed you the ledger and a single coin. The first name is one you recognize: your own."),
        ("Where the Roads Refuse", "The kingdom's roads have begun to rearrange themselves at night, and only you seem to notice. This morning, every one of them leads to a door that wasn't there yesterday."),
        ("The Unlit Lantern", "You inherit a lighthouse for a sea that dried up centuries ago. On your first night, something far out in the dust asks you, politely, to please turn on the light."),
    ],
    "mystery": [
        ("The Eighth Guest", "Seven invitations went out for the dinner. Eight people are seated at the table, and the host insists she only set seven places. Then the doors lock."),
        ("Return to Sender", "Letters you never wrote start arriving at your door, postmarked next week, signed in your handwriting. The latest one is a confession."),
        ("The Quiet Floor", "You manage a building where the fourth floor has no tenants on the lease — yet every night, the elevator stops there on its own, and someone gets off."),
    ],
    "horror": [
        ("It Keeps the Count", "The old house tallies things — footsteps, breaths, the living. You found the ledger in the walls, and your number is circled, smaller every day."),
        ("Don't Wake the Tide", "The village rule is simple: when the fog comes in, you do not answer the door, no matter whose voice it uses. Tonight the fog is early, and the voice is your mother's."),
        ("Subject: You", "Your new phone keeps autocompleting messages you haven't thought of yet — and they're always right. The latest draft just says: 'they're already inside.'"),
    ],
}


def _stub_generate_daily(genre: str, rating: str) -> dict:
    pool = _PROMPT_POOL.get(genre) or _PROMPT_POOL["sci-fi"]
    title, blurb = random.choice(pool)
    if rating == "mature":
        blurb += " (Mature telling — this one doesn't look away from the dark.)"
    return {"title": title, "blurb": blurb}


# Tame placeholder lists. Anything clearly hateful/violent is blocked everywhere;
# PG additionally blocks mild profanity so PG stories stay PG.
_BLOCK_ALWAYS = ["kill yourself", "kys", "make a bomb"]
_BLOCK_PG = ["damn", "hell", "crap", "bastard", "ass"]


def _stub_moderate(text: str, rating: str = "pg") -> dict:
    low = (text or "").lower()
    for phrase in _BLOCK_ALWAYS:
        if phrase in low:
            return {"allowed": False, "reason": "That contains content we don't allow."}
    if rating == "pg":
        words = set(low.replace(".", " ").replace(",", " ").split())
        hit = next((w for w in _BLOCK_PG if w in words), None)
        if hit:
            return {
                "allowed": False,
                "reason": f"This is a PG story — “{hit}” is a bit much. Try softening the language.",
            }
    return {"allowed": True, "reason": None}


# --------------------------------------------------------------------------- #
# Daily generation + moderation — real Claude (used when ANTHROPIC_API_KEY set)
# --------------------------------------------------------------------------- #
def _claude_generate_daily(genre: str, rating: str) -> dict:
    client = _get_client()
    tone = "Keep it strictly PG." if rating == "pg" else "A mature tone (dark themes ok); no gratuitous content."
    resp = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=(
            f"Invent an original {genre} writing prompt for a collaborative "
            f"choose-your-own-adventure. {tone} Return a short evocative title and "
            "a 2-4 sentence second-person setup that ends poised for the reader to act."
        ),
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "blurb": {"type": "string"},
                    },
                    "required": ["title", "blurb"],
                    "additionalProperties": False,
                },
            },
        },
        messages=[{"role": "user", "content": f"Genre: {genre}. Rating: {rating}."}],
    )
    return json.loads(next(b.text for b in resp.content if b.type == "text"))


def _claude_moderate(text: str, rating: str) -> dict:
    client = _get_client()
    bar = "PG (no profanity, sex, graphic violence)" if rating == "pg" else "mature (dark ok; no hate, sexual content involving minors, or real-world harm instructions)"
    resp = client.messages.create(
        model=MODEL,
        max_tokens=256,
        system=(
            f"You moderate user-written story passages. The story's bar is {bar}. "
            "Decide if the passage is allowed. If not, give a short, friendly reason."
        ),
        output_config={
            "effort": "low",
            "format": {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "properties": {
                        "allowed": {"type": "boolean"},
                        "reason": {"type": "string"},
                    },
                    "required": ["allowed", "reason"],
                    "additionalProperties": False,
                },
            },
        },
        messages=[{"role": "user", "content": text}],
    )
    data = json.loads(next(b.text for b in resp.content if b.type == "text"))
    return {"allowed": bool(data.get("allowed")), "reason": data.get("reason") or None}
