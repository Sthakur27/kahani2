"""RPG run engine: class presets, the Effect interpreter (mutations applied when
an outcome fires), and run-state snapshotting. Kept out of the routers so the
rules live in one place. See docs/rpg-statefulness.md."""
import random

from sqlalchemy import select

from models import RunCharacter, RunFlag, RunInventory

# Short stat keys (as used on Edge.check_stat / Effect.stat) -> column names.
STAT_COLS = {
    "str": "strength",
    "dex": "dexterity",
    "con": "constitution",
    "int": "intelligence",
    "wis": "wisdom",
    "cha": "charisma",
}

# Starting class presets (stat spread + HP). Starting kits come with the items
# phase; for now classes differ by stats/HP only.
CLASS_PRESETS = {
    "warrior": dict(strength=15, dexterity=12, constitution=14, intelligence=8,
                    wisdom=10, charisma=10, hp=28),
    "rogue":   dict(strength=10, dexterity=15, constitution=12, intelligence=13,
                    wisdom=10, charisma=12, hp=22),
    "mage":    dict(strength=8, dexterity=11, constitution=10, intelligence=15,
                    wisdom=14, charisma=12, hp=18),
}


def ability_modifier(score: int) -> int:
    """D&D-style modifier: floor((score - 10) / 2)."""
    return (score - 10) // 2


# Which outcome band a roll lands in, and the fallback order if the author didn't
# write that band (crit_* fall back to their base band; base bands are required).
def band_for(roll: int, modifier: int, dc: int) -> str:
    """Natural 20 → crit_success, natural 1 → crit_fail, else d20+mod vs DC."""
    if roll >= 20:
        return "crit_success"
    if roll <= 1:
        return "crit_fail"
    return "success" if (roll + modifier) >= (dc or 0) else "fail"


BAND_FALLBACK = {
    "crit_success": ["crit_success", "success"],
    "success": ["success"],
    "fail": ["fail"],
    "crit_fail": ["crit_fail", "fail"],
}


def roll_check(character, stat: str, dc: int) -> dict:
    """Roll a server-side d20 + the character's stat modifier against `dc`."""
    col = STAT_COLS.get(stat or "")
    score = getattr(character, col) if col else 10
    mod = ability_modifier(score)
    d20 = random.randint(1, 20)
    return {
        "d20": d20,
        "modifier": mod,
        "total": d20 + mod,
        "dc": dc,
        "stat": stat,
        "band": band_for(d20, mod, dc),
    }


# --------------------------------------------------------------------------- #
# Effect interpreter — applies Effect rows to a run/character. Adding a new
# mechanic is a new `type` branch here, not a schema change.
# --------------------------------------------------------------------------- #
def apply_effects(session, run, character, effects) -> list[dict]:
    """Mutate run/character state for each effect; return an audit list."""
    applied = []
    for e in effects:
        t = e.type
        if t == "hp_delta":
            character.hp = max(0, min(character.max_hp, character.hp + (e.amount or 0)))
        elif t == "max_hp_delta":
            character.max_hp = max(1, character.max_hp + (e.amount or 0))
            character.hp = min(character.hp, character.max_hp)
        elif t == "heal_full":
            character.hp = character.max_hp
        elif t == "stat_delta" and e.stat in STAT_COLS:
            col = STAT_COLS[e.stat]
            setattr(character, col, max(1, getattr(character, col) + (e.amount or 0)))
        elif t == "set_flag":
            _set_flag(session, run.id, e.flag_key, e.flag_value)
        elif t == "grant_item" and e.item_id:
            _adjust_item(session, run.id, character.id, e.item_id, e.count or 1)
        elif t == "consume_item" and e.item_id:
            _adjust_item(session, run.id, character.id, e.item_id, -(e.count or 1))
        elif t == "end_run":
            run.status = "won"
        applied.append({
            "type": t, "amount": e.amount, "stat": e.stat,
            "item_id": e.item_id, "flag_key": e.flag_key,
        })

    # Death check (party-of-1 for now): a downed character ends the run.
    if character.hp <= 0 and character.status != "dead":
        character.status = "dead"
        run.status = "dead"
    return applied


def _set_flag(session, run_id, key, value):
    if not key:
        return
    flag = session.scalar(
        select(RunFlag).where(RunFlag.run_id == run_id, RunFlag.key == key)
    )
    if flag is None:
        session.add(RunFlag(run_id=run_id, key=key, value=value))
    else:
        flag.value = value


def _adjust_item(session, run_id, character_id, item_id, delta):
    inv = session.scalar(
        select(RunInventory).where(
            RunInventory.run_id == run_id,
            RunInventory.item_id == item_id,
            RunInventory.character_id == character_id,
        )
    )
    if inv is None:
        if delta > 0:
            session.add(RunInventory(
                run_id=run_id, character_id=character_id,
                item_id=item_id, count=delta,
            ))
    else:
        inv.count += delta
        if inv.count <= 0:
            session.delete(inv)


# --------------------------------------------------------------------------- #
# Snapshotting — the full state captured on each RunStep (basis for save/restore)
# --------------------------------------------------------------------------- #
def character_dict(c: RunCharacter) -> dict:
    return {
        "id": c.id,
        "name": c.name,
        "class": c.char_class,
        "hp": c.hp,
        "max_hp": c.max_hp,
        "status": c.status,
        "stats": {
            "str": c.strength, "dex": c.dexterity, "con": c.constitution,
            "int": c.intelligence, "wis": c.wisdom, "cha": c.charisma,
        },
    }


def build_snapshot(session, run) -> dict:
    chars = session.scalars(
        select(RunCharacter).where(RunCharacter.run_id == run.id)
    ).all()
    inv = session.scalars(
        select(RunInventory).where(RunInventory.run_id == run.id)
    ).all()
    flags = session.scalars(
        select(RunFlag).where(RunFlag.run_id == run.id)
    ).all()
    return {
        "status": run.status,
        "current_node_id": run.current_node_id,
        "party_gold": run.party_gold,
        "characters": [character_dict(c) for c in chars],
        "inventory": [
            {"item_id": i.item_id, "character_id": i.character_id, "count": i.count}
            for i in inv
        ],
        "flags": {f.key: f.value for f in flags},
    }
