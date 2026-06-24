"""Consolidated, idempotent demo-data seeder for StorySim.

Run this once after cloning to populate the database with the four demo
stories (and their branching node trees, community users, and votes):

    ./venv/bin/python seed_demo.py            # seed if not already present
    ./venv/bin/python seed_demo.py --reset    # delete the four demo stories, then reseed

It is standalone and fresh-DB safe: it creates the schema itself, so it does
not require running app.py first. Reruns without --reset are no-ops.

Publish dates are relative to today so there is always a "today" story:
    The Cartographer's Last Map  = today
    The Last Lighthouse          = today - 1
    Signal from Europa           = today - 2
    The Tenant in 4B             = today - 3
"""

import datetime
import sys

from sqlalchemy import delete, func, select

from db import engine, SessionLocal, Base
import models
from models import User, Story, StoryNode, EdgeVote

# Exact titles of the four demo stories. Used to detect existing data and,
# with --reset, to delete ONLY these stories (cascading to their nodes/votes).
DEMO_TITLES = [
    "The Cartographer's Last Map",
    "The Last Lighthouse",
    "Signal from Europa",
    "The Tenant in 4B",
]


def get_or_create_user(session, username):
    existing = session.scalar(select(User).where(User.username == username))
    if existing:
        return existing
    u = User(username=username)
    session.add(u)
    session.flush()
    return u


def reset_demo(session):
    """Delete ONLY the four demo stories by exact title. Cascades remove their
    nodes and votes. Leaves the demo user, other stories, and other users alone."""
    story_ids = session.scalars(
        select(Story.id).where(Story.title.in_(DEMO_TITLES))
    ).all()
    if not story_ids:
        return 0
    # Remove votes -> nodes -> stories explicitly (ON DELETE CASCADE covers
    # nodes/votes, but be explicit so it works regardless of FK enforcement).
    node_ids = session.scalars(
        select(StoryNode.id).where(StoryNode.story_id.in_(story_ids))
    ).all()
    if node_ids:
        session.execute(
            delete(EdgeVote).where(EdgeVote.story_node_id.in_(node_ids))
        )
        session.execute(delete(StoryNode).where(StoryNode.id.in_(node_ids)))
    session.execute(delete(Story).where(Story.id.in_(story_ids)))
    session.commit()
    return len(story_ids)


# ---------------------------------------------------------------------------
# Per-story seeders. Each returns (story, node_count, vote_count).
# ---------------------------------------------------------------------------

def seed_cartographer(session, publish_date):
    usernames = ["cm_iris", "cm_theo", "cm_bramble", "cm_wren", "cm_dov", "cm_pell"]
    users = {name: get_or_create_user(session, name) for name in usernames}
    session.flush()

    iris = users["cm_iris"]
    theo = users["cm_theo"]
    bramble = users["cm_bramble"]
    wren = users["cm_wren"]
    dov = users["cm_dov"]
    pell = users["cm_pell"]

    story = Story(
        title="The Cartographer's Last Map",
        blurb=(
            "You are Mella Quill, the only mapmaker left in the hill town of Fenwick. "
            "Last night you finished the great survey map you'd labored over for three years "
            "and pinned it to the drying board before bed. This morning the ink is dry, the "
            "parchment is warm to the touch, and the map is wrong: a new road curls east from "
            "the market square, and where the empty moor used to be there is now a tidy little "
            "town labeled in your own handwriting, 'Hollowmere'. You never drew it. The map "
            "redrew itself."
        ),
        user_id=iris.id,
        publish_date=publish_date,
    )
    session.add(story)
    session.flush()

    nodes = {}

    def add_node(key, parent_key, author, edge_prompt, content, summary):
        parent_id = nodes[parent_key].id if parent_key else None
        n = StoryNode(
            story_id=story.id,
            parent_node_id=parent_id,
            user_id=author.id,
            edge_prompt=edge_prompt,
            content=content,
            summary_so_far=summary,
        )
        session.add(n)
        session.flush()
        nodes[key] = n
        return n

    # ===== Top-level branch A: Walk the new road =====
    add_node(
        "A", None, iris,
        "Follow the new road east",
        "You lace your boots before the kettle even sings. The new road is real beneath your feet, "
        "packed and pale, and it smells of crushed thyme that does not grow in Fenwick. With every "
        "step the hedgerows lean in a little closer, as if curious who finally came to walk them.",
        "Mella sets out along the impossible road the map drew toward Hollowmere.",
    )
    add_node(
        "A1", "A", theo,
        "Knock on the first door in Hollowmere",
        "Hollowmere is small and impossibly tidy, every shutter the green of new apples. You knock at "
        "the nearest cottage and a woman answers wearing your grandmother's face, younger than you ever "
        "knew her. 'We wondered when you'd finish us,' she says, and stands aside to let you in.",
        "Mella reaches Hollowmere and is welcomed by a woman wearing her late grandmother's face.",
    )
    add_node(
        "A1a", "A1", bramble,
        "Step inside and accept the tea",
        "Inside, the kettle is already steaming and two cups wait on the table. The tea tastes of the "
        "summer you turned nine. 'A town has to be drawn by someone who loves it,' she tells you. 'You "
        "loved this place before you knew its name.' Out the window, more cottages are quietly sketching "
        "themselves into being.",
        "Mella accepts tea from the grandmother-figure and learns Hollowmere grows from her own love.",
    )
    add_node(
        "A1b", "A1", wren,
        "Ask her how she knows your map",
        "'Know it?' She laughs, soft as turning pages. 'Child, I live in it. Every line you ink gives one "
        "of us a doorstep to stand on.' She presses a thimble into your palm, worn smooth, unmistakably "
        "your grandmother's. 'You left this in the real world. We kept it safe.'",
        "Mella asks the woman about the map and is given her grandmother's thimble as proof Hollowmere is real.",
    )
    add_node(
        "A2", "A", dov,
        "Ignore the town and trace the road to its end",
        "You decide the town can wait; a road that draws itself must lead somewhere. You walk past "
        "Hollowmere as its windows watch you, and the road narrows to a footpath, then to a single line "
        "of white pebbles, then to nothing at all. You stand at the exact edge of the drawn world. Ahead "
        "is unmarked parchment, blank and humming.",
        "Mella bypasses Hollowmere and follows the road to the literal edge of the map.",
    )
    add_node(
        "A2a", "A2", pell,
        "Step off the edge of the map",
        "You lift one boot over the white nothing and set it down. The ground catches you, cool and "
        "papery, and where you step a meadow blooms outward in every direction like spilled ink finding "
        "its shape. You are not falling. You are drawing.",
        "Mella steps past the map's edge and discovers her footsteps create new land.",
    )

    # ===== Top-level branch B: Study the map first =====
    add_node(
        "B", None, theo,
        "Stay home and study the changed map",
        "You do not trust your boots; you trust your eyes. You bring the magnifying lens to the parchment "
        "and bend close. The new road is drawn in your hand, yes, but in ink a shade greener than any you "
        "own, and the little town breathes: tiny chimney-smoke curls drift across the paper and vanish at "
        "the map's border.",
        "Rather than leave, Mella examines the self-drawn map closely and finds it subtly alive.",
    )
    add_node(
        "B1", "B", bramble,
        "Touch the drawn town with your fingertip",
        "You press a fingertip to Hollowmere's miniature square. It is warm, and warmer still, and for one "
        "breath you smell bread and hear a distant bell. When you pull back, your fingertip is dusted with "
        "real flour. The map gave you something to carry.",
        "Mella touches the painted town and the map answers with warmth, sound, and a dusting of real flour.",
    )
    add_node(
        "B1a", "B1", iris,
        "Taste the flour",
        "You touch the flour to your tongue. It is the bread of a bakery that does not exist yet, and "
        "suddenly you know its baker's name, the slant of his apron, the dog asleep at his feet. The map "
        "is not redrawing the world. It is remembering a world, and asking you to finish remembering.",
        "Tasting the map's flour, Mella realizes Hollowmere is a half-remembered world awaiting completion.",
    )
    add_node(
        "B2", "B", wren,
        "Try to erase the new road",
        "Unsettled, you fetch the bread-eraser and rub at the new road. The graphite of the moor returns "
        "for a moment, gray and empty and lonely. Then, slow as a held breath, the road draws itself back, "
        "darker now, as if to say it would rather not be unmade.",
        "Mella tries erasing the road; the empty moor briefly returns before the road stubbornly redraws itself.",
    )
    add_node(
        "B2a", "B2", dov,
        "Apologize to the map",
        "You set the eraser down and, feeling foolish, whisper 'I'm sorry' to a piece of parchment. The "
        "ink seems to soften. A new line appears at the map's corner, small and shy: a single cottage with "
        "a lamp lit in the window, and beneath it, in handwriting not quite yours, the word 'Welcome.'",
        "Mella apologizes to the map for erasing it; in answer it draws a welcoming lamplit cottage.",
    )

    # ===== Top-level branch C: Tell someone in Fenwick =====
    add_node(
        "C", None, bramble,
        "Show the map to old Sexton Hale",
        "You roll the parchment under your arm and hurry to the church, where Sexton Hale has rung the "
        "bells of Fenwick for fifty years. He unrolls the map on a pew, goes very still, and lays one "
        "trembling finger on Hollowmere. 'My boy was born there,' he says. 'Before it was nowhere.'",
        "Mella brings the map to Sexton Hale, who recognizes Hollowmere as a place that once existed.",
    )
    add_node(
        "C1", "C", pell,
        "Ask Hale what happened to Hollowmere",
        "Hale tells you of a flood the year you were born, a whole valley taken in a night, a town the "
        "county quietly scrubbed from its records to save on grief. 'No one drew it after that,' he says. "
        "'A place not on any map may as well have never been. Until now. Until you.'",
        "Hale reveals Hollowmere drowned the year of Mella's birth and was erased from all records.",
    )
    add_node(
        "C1a", "C1", theo,
        "Promise Hale you'll finish the map",
        "Something in his face decides you. 'Then I'll draw it back,' you say. 'Every lane, every "
        "doorstep.' Hale weeps without shame and rings the great bell once, a sound that rolls east "
        "across the moor and does not fade where it ought to. Somewhere out there, you feel sure, a "
        "town hears its name.",
        "Mella vows to restore Hollowmere on paper; Hale rings the bell and it carries impossibly far.",
    )
    add_node(
        "C2", "C", iris,
        "Ask if anyone survived the flood",
        "Hale's eyes go distant. 'One,' he murmurs. 'A baby, pulled from the water and carried over the "
        "hills to Fenwick, raised by a mapmaker's family. Named for the way the water quilled around her.' "
        "He looks at you for a long, long moment. 'Mella,' he says, 'you were the one.'",
        "Hale reveals the flood's lone survivor was a baby raised by mapmakers, and that baby was Mella.",
    )

    # ===== Top-level branch D: The map at night =====
    add_node(
        "D", None, wren,
        "Wait and watch the map at midnight",
        "You resolve to catch it in the act. You sit by candlelight with the map and your sharpest pen, "
        "and for hours nothing stirs. Then, at the bottom of the dark, the parchment exhales. A line "
        "begins to grow from Hollowmere, hesitant, reaching, as if waiting to see whether you'll help.",
        "Mella keeps a midnight vigil and watches the map begin to draw a new line, seemingly inviting her.",
    )
    add_node(
        "D1", "D", dov,
        "Guide the line with your own pen",
        "You lower your nib to meet the creeping line, and the moment they touch, warmth floods up your "
        "arm like sunlight through a window. Together you draw a bridge, a mill, a row of willows. You are "
        "not the master of this map and it is not the master of you. You are, at last, drawing together.",
        "Mella joins her pen to the map's living line and they begin building Hollowmere in collaboration.",
    )
    add_node(
        "D1a", "D1", bramble,
        "Sign your name beside Hollowmere",
        "When dawn comes the moor is full of streets. You dip your pen one last time and sign the margin, "
        "the way every cartographer signs a finished world. The ink settles, and far to the east a "
        "rooster you have never heard crows for the first morning of a town brought home. Your last map "
        "is not an ending. It is an address.",
        "At dawn Mella signs the restored map; Hollowmere wakes for its first true morning.",
    )
    add_node(
        "D2", "D", pell,
        "Pull your hand back and let it draw alone",
        "You withdraw your pen, afraid of what you might owe a thing that draws itself. The line falters, "
        "wavers, and stops half-formed, an unfinished street ending in white. The map waits all night for "
        "a hand that does not come. By morning the new line has faded to the faintest ghost of graphite.",
        "Mella refuses to help; the map's hopeful new line falters and nearly vanishes by morning.",
    )

    session.flush()

    # --- Votes ---
    vote_plan = [
        ("D",  [iris, theo, bramble, wren, dov, pell], [1, 1, 1, 1, 1, 1]),   # +6
        ("D1", [iris, theo, bramble, wren, dov],       [1, 1, 1, 1, 1]),       # +5
        ("D1a",[iris, theo, bramble, wren, dov, pell], [1, 1, 1, 1, 1, 1]),   # +6
        ("A",  [iris, theo, bramble, dov],             [1, 1, 1, -1]),         # +2
        ("A1", [iris, theo, wren],                     [1, 1, -1]),            # +1
        ("C",  [bramble, pell, iris],                  [1, 1, 1]),             # +3
        ("C1", [bramble, pell],                        [1, 1]),                # +2
        ("C2", [iris, theo],                           [1, 1]),                # +2
        ("D2", [iris, theo, bramble, wren],            [-1, -1, -1, -1]),      # -4
        ("B2", [theo, wren, dov],                      [-1, -1, 1]),           # -1
        ("A2a",[pell, dov],                            [-1, -1]),              # -2
    ]
    vote_count = 0
    for node_key, voters, values in vote_plan:
        node = nodes[node_key]
        for voter, value in zip(voters, values):
            session.add(EdgeVote(user_id=voter.id, story_node_id=node.id, value=value))
            vote_count += 1
    session.flush()
    return story, len(nodes), vote_count


def seed_lighthouse(session, publish_date):
    usernames = ["lh_mara", "lh_dev", "lh_priya", "lh_osei", "lh_yuki", "lh_finn"]
    users = {name: get_or_create_user(session, name) for name in usernames}
    session.flush()
    uid = {name: users[name].id for name in usernames}

    story = Story(
        title="The Last Lighthouse",
        blurb=(
            "The radio went silent three days ago. Tonight the lamp still turns, but no one "
            "has climbed the stairs in years. You push open the salt-warped door at the base "
            "of the tower..."
        ),
        user_id=uid["lh_mara"],
        publish_date=publish_date,
    )
    session.add(story)
    session.flush()

    nodes = {}

    def add_node(key, parent_key, author, edge_prompt, content, summary):
        parent_id = nodes[parent_key].id if parent_key else None
        n = StoryNode(
            story_id=story.id,
            parent_node_id=parent_id,
            user_id=uid[author],
            edge_prompt=edge_prompt,
            content=content,
            summary_so_far=summary,
        )
        session.add(n)
        session.flush()
        nodes[key] = n
        return n

    # ============================================================
    # ORIGINAL OPENING NODES (recreated so the story is standalone).
    # These were the pre-existing nodes the original enrichment script
    # depended on (formerly story #1 nodes 1, 2, 3, 7).
    # ============================================================
    add_node(
        "o1", None, "lh_mara",
        "Climb the spiral stairs toward the light",
        "Each step groans. Halfway up, a logbook lies open, its last entry smeared: "
        "'It answers when the lamp turns three times.'",
        "After three days of radio silence, you pushed through the lighthouse's salt-warped "
        "door and climbed the spiral stairs toward the still-turning lamp. Halfway up, an open "
        "logbook warned that the light answers when the lamp turns three times.",
    )
    add_node(
        "o2", None, "lh_dev",
        "Follow the wet footprints down to the cellar",
        "The prints are too long to be human. They end at a hatch in the floor that hums, "
        "faintly, like a held breath.",
        "After three days of radio silence, you entered the abandoned lighthouse and followed a "
        "trail of wet, too-long footprints down to the cellar, where they ended at a faintly "
        "humming hatch in the floor.",
    )
    add_node(
        "o3", "o1", "lh_priya",
        "Turn the lamp three times",
        "The light sweeps once, twice... on the third pass a voice climbs the stairs to meet you.",
        "Having climbed to the lamp and read the logbook's warning, you turned the light three "
        "times. On the third pass, a voice began climbing the stairs to meet you.",
    )
    add_node(
        "o7", "o1", "lh_yuki",
        "at the top of the lighthouse I enter and I see an old man",
        "he looks over but with a dark poker face and just says nothing I glance around nervously",
        "The radio went silent three days ago. You chose to climb the spiral stairs toward the "
        "light. You chose to at the top of the lighthouse I enter and I see an old man.",
    )

    # ============================================================
    # NEW TOP-LEVEL BRANCHES (parent_node_id = None)
    # ============================================================
    add_node(
        "a", None, "lh_mara",
        "Ring the fog bell hanging by the door",
        "You grab the corroded rope and pull. The bell gives a flat, drowned note "
        "that no air should be able to make. Out in the dark water, something answers "
        "with the same pitch, closer than the shore has any right to be.",
        "The radio is dead and the lamp turns untended. At the base of the tower you "
        "ring the fog bell, and the black water answers back.",
    )
    add_node(
        "b", None, "lh_dev",
        "Take the keeper's oilskin coat from its hook",
        "The coat is still warm. You slide your arms in and the sleeves are heavy, as "
        "if someone left their hands inside them. In the pocket your fingers close on "
        "a brass key wet with seawater.",
        "With the radio silent, you enter the abandoned tower and pull on the keeper's "
        "still-warm coat, finding a seawater-wet brass key in the pocket.",
    )
    add_node(
        "c", None, "lh_priya",
        "Turn back and run for the mainland road",
        "You bolt for the causeway, but the tide has come in wrong, hours early, and "
        "the road is gone beneath black glass. Behind you the lamp stops turning, and "
        "in the sudden stillness you hear it begin to climb the stairs.",
        "Rather than explore the silent tower, you flee for the causeway, but the tide "
        "has swallowed the road and something inside begins to climb.",
    )
    add_node(
        "d", None, "lh_yuki",
        "Search the ground-floor radio room",
        "Static hisses from a set no one switched on. The logsheet on the desk repeats "
        "one line in a tightening hand: THEY COME WITH THE LIGHT. The last entry is "
        "tonight's date, though you are the only soul for miles.",
        "Investigating the radio's silence, you find the ground-floor set hissing on "
        "its own and a logsheet warning that they come with the light, dated tonight.",
    )

    # ============================================================
    # CHILDREN of the ORIGINAL nodes (o1, o2, o7)
    # ============================================================
    add_node(
        "e1", "o1", "lh_osei",
        "Read the logbook's final entry aloud",
        "Your voice shakes the dust: 'The light is not ours. We only feed it.' As the "
        "last word leaves you, the lamp above flares white and the stairwell fills "
        "with the smell of brine and burning oil.",
        "You climb toward the light and find an open logbook. Reading its final line "
        "aloud, the lamp flares and the air turns to brine and burning oil.",
    )
    add_node(
        "e2", "o1", "lh_finn",
        "Pocket the logbook and keep climbing",
        "You tuck the book inside your jacket and press on. With each turn of the "
        "stair the pages grow warmer against your chest, and you begin to hear them "
        "riffling, though your hands are nowhere near.",
        "Climbing toward the light, you take the open logbook and continue upward as "
        "the pages warm and turn against your chest on their own.",
    )
    add_node(
        "f1", "o2", "lh_mara",
        "Lift the iron hatch the prints lead to",
        "The hatch is freezing and weeps saltwater around its seams. You haul it up "
        "and stale sea-air rushes past you into the room, going up, as if something "
        "below needs to breathe the lighthouse.",
        "Following inhumanly long footprints to a cellar hatch, you lift it and the "
        "sea-air below rushes upward as though the dark needs to breathe.",
    )
    add_node(
        "f2", "o2", "lh_dev",
        "Press your ear to the hatch and listen",
        "Beneath the iron you hear water lapping in a slow, deliberate rhythm, like "
        "breathing, like counting. Then it stops, all at once, the way a room goes "
        "quiet when it knows you are listening too.",
        "The long footprints end at a cellar hatch; you listen and hear breathing "
        "water below that falls silent the moment it senses you.",
    )
    add_node(
        "g1", "o7", "lh_priya",
        "Ask the old man where the keeper has gone",
        "He turns his head too far, past where a neck should stop, and smiles without "
        "any warmth. 'Gone?' he says. 'No one leaves the light. We only change which "
        "side of the glass we tend it from.'",
        "At the top you meet a silent old man. You ask after the keeper, and he turns "
        "his head impossibly far to say no one ever leaves the light.",
    )
    add_node(
        "g2", "o7", "lh_yuki",
        "Back slowly toward the stairs",
        "You retreat one step. The old man does not move, but the shadows he casts "
        "do, stretching across the floor to lap at your boots like a rising tide. The "
        "door to the stairs is closed now, and you did not hear it shut.",
        "Facing the silent old man, you edge toward the stairs, but his shadows crawl "
        "after you and the stairway door has soundlessly sealed.",
    )

    # ============================================================
    # GRANDCHILDREN (deeper levels under new nodes)
    # ============================================================
    add_node(
        "a1", "a", "lh_osei",
        "Ring the bell again to answer it",
        "You toll it on purpose this time. The reply comes instantly, a wall of sound "
        "from directly below the rocks, and the whole tower shivers like a struck "
        "tuning fork. Something has been waiting to be invited.",
        "After the fog bell drew an answer from the sea, you ring it again on purpose "
        "and the tower shudders as something accepts the invitation.",
    )
    add_node(
        "a2", "a", "lh_finn",
        "Cut the bell rope and silence it",
        "You saw through the rope with your keys and the clapper falls dead. But the "
        "answering note keeps coming across the water, rising, no longer needing your "
        "bell to know exactly where you stand.",
        "The fog bell woke something in the water; you cut its rope, yet the answering "
        "call rises on its own, now fixed on your position.",
    )
    add_node(
        "b1", "b", "lh_priya",
        "Try the brass key on the locked lamp-room door",
        "The key turns as though the lock were oiled yesterday. Beyond the door the "
        "lamp burns far too bright, and a second oilskin coat hangs there, dripping, "
        "shaped around a body that is not there.",
        "Wearing the keeper's coat, you use the brass key to open the lamp-room and "
        "find a second dripping coat hung around an absent body.",
    )
    add_node(
        "b2", "b", "lh_yuki",
        "Search the coat's other pockets first",
        "Inside the lining you find a tide-table with every date crossed out but "
        "tonight, and a photograph of the tower with too many windows lit. In each "
        "lit window a small pale face presses against the glass.",
        "Before using the brass key, you search the keeper's coat and find a tide-"
        "table ending tonight and a photo of the tower with watching faces in every "
        "window.",
    )
    add_node(
        "d1", "d", "lh_mara",
        "Answer the radio static with your voice",
        "You key the handset and say hello. The static folds back into a chorus of "
        "your own word, hundreds of voices saying hello in your exact tone, growing "
        "louder until the lamp upstairs answers each one with a turn.",
        "In the radio room you speak into the hissing set, and hundreds of copies of "
        "your own voice answer as the lamp turns to each one.",
    )
    add_node(
        "d2", "d", "lh_dev",
        "Yank the radio's power before it finishes",
        "You tear the cable from the wall. The static dies, but the logsheet keeps "
        "writing itself, the pen scratching out a new line: GOOD. NOW YOU CAN HEAR US "
        "WITHOUT IT.",
        "You cut power to the self-running radio, but the logsheet writes on by itself "
        "to say you can hear them now without it.",
    )

    # ============================================================
    # GREAT-GRANDCHILDREN
    # ============================================================
    add_node(
        "a1x", "a1", "lh_dev",
        "Step outside to meet whatever climbs the rocks",
        "You open the door to the spray. A line of figures in keeper's coats wades up out "
        "of the surf, each one wearing your own face, each one reaching for the bell rope "
        "you just let go.",
        "Having summoned the sea with the bell, you step outside to find figures in "
        "keeper's coats, all wearing your face, rising from the surf.",
    )
    add_node(
        "b1x", "b1", "lh_osei",
        "Put on the second, dripping coat",
        "Cold water seals around you and the lamp dims to a comfortable glow. You "
        "understand the rhythm of the turning now, the long watch ahead, and you no longer "
        "remember wanting to leave.",
        "In the lamp-room you don the second dripping coat, and as the cold settles you "
        "forget you ever meant to leave the light.",
    )

    session.flush()

    # ============================================================
    # VOTES — popularity varies clearly.
    # ============================================================
    all_users = usernames
    vote_count = 0

    def upvotes(node_key, voters):
        nonlocal vote_count
        node = nodes[node_key]
        for v in voters:
            session.add(EdgeVote(user_id=uid[v], story_node_id=node.id, value=1))
            vote_count += 1

    def downvotes(node_key, voters):
        nonlocal vote_count
        node = nodes[node_key]
        for v in voters:
            session.add(EdgeVote(user_id=uid[v], story_node_id=node.id, value=-1))
            vote_count += 1

    # CLEAR WINNER: node a (the fog bell) -> all 6 up, net +6
    upvotes("a", all_users)
    # Strong runner-up: e1 (read logbook aloud) -> 5 up, net +5
    upvotes("e1", ["lh_mara", "lh_dev", "lh_priya", "lh_osei", "lh_yuki"])
    # Strong: b1 (try brass key) -> 4 up 0 down, net +4
    upvotes("b1", ["lh_mara", "lh_dev", "lh_yuki", "lh_finn"])
    # Middling: d (radio room) -> 3 up, 1 down, net +2
    upvotes("d", ["lh_priya", "lh_osei", "lh_finn"])
    downvotes("d", ["lh_mara"])
    # Middling: f1 (lift hatch) -> 2 up, net +2
    upvotes("f1", ["lh_dev", "lh_yuki"])
    # Middling: g1 (ask old man) -> 2 up, 1 down, net +1
    upvotes("g1", ["lh_priya", "lh_finn"])
    downvotes("g1", ["lh_osei"])
    # Net-negative branch: c (run for the road) -> 1 up, 4 down, net -3
    upvotes("c", ["lh_priya"])
    downvotes("c", ["lh_mara", "lh_dev", "lh_osei", "lh_yuki"])
    # Another negative: d2 (yank power) -> 0 up, 2 down, net -2
    downvotes("d2", ["lh_finn", "lh_priya"])
    # Scattered votes on others and the original opening nodes.
    upvotes("b", ["lh_mara", "lh_osei"])         # +2
    upvotes("a1", ["lh_finn", "lh_yuki"])        # +2
    upvotes("o1", ["lh_priya"])                  # original "climb stairs": +1
    downvotes("o2", ["lh_finn"])                 # original "footprints": -1
    upvotes("f2", ["lh_mara"])                   # +1

    session.flush()
    return story, len(nodes), vote_count


def seed_europa(session, publish_date):
    usernames = [
        "eu_vance", "eu_okafor", "eu_marlow", "eu_petrov", "eu_singh", "eu_calder",
    ]
    users = {name: get_or_create_user(session, name) for name in usernames}
    session.flush()
    uid = {name: users[name].id for name in usernames}

    story = Story(
        title="Signal from Europa",
        blurb=(
            "You are the sole maintenance technician aboard Relay Station Kestrel, a "
            "windowless can of metal grinding its slow orbit around Europa. Three hundred "
            "and eleven days alone, and the only voices are the station's chimes and the "
            "dead hiss of dormant channels. Then, at 02:14 ship-time, Channel 9 - decommissioned "
            "years ago - crackles awake. A transmission. A voice. And the voice is yours."
        ),
        user_id=uid["eu_vance"],
        publish_date=publish_date,
    )
    session.add(story)
    session.flush()

    nodes = {}

    def add_node(key, parent_key, author, edge_prompt, content, summary):
        parent_id = nodes[parent_key].id if parent_key else None
        n = StoryNode(
            story_id=story.id,
            parent_node_id=parent_id,
            user_id=uid[author],
            edge_prompt=edge_prompt,
            content=content,
            summary_so_far=summary,
        )
        session.add(n)
        session.flush()
        nodes[key] = n
        return n

    # ============ TOP-LEVEL BRANCHES ============
    add_node(
        "A", None, "eu_vance",
        "Key the mic and answer it",
        "You press the transmit stud before the fear can stop you. \"Kestrel here. Identify.\" "
        "The hiss swallows your words, then folds them back at you a half-second later in your "
        "own flat cadence: \"Kestrel here. Identify.\" You have not heard your own recorded voice "
        "in months, and it sounds like a stranger wearing your throat.",
        "A maintenance tech on Europa's Relay Station Kestrel answers a transmission on a dead "
        "channel and hears their own voice answer back.",
    )
    add_node(
        "B", None, "eu_okafor",
        "Run a trace on the signal's origin",
        "You don't answer. Instead you spin to the diagnostics console and slap a trace on "
        "Channel 9. Coordinates resolve, blink, refuse to settle. The vector points not outward "
        "to some passing ship but down - straight down, into the ice, into the black ocean under "
        "Europa's frozen shell where nothing has ever been built.",
        "Rather than answer the voice, the tech traces the signal and finds it originates from "
        "beneath Europa's ice, where nothing should exist.",
    )
    add_node(
        "C", None, "eu_marlow",
        "Mute the channel and pretend you heard nothing",
        "You reach up and cut Channel 9's monitor feed. Silence. You tell yourself it was a "
        "diagnostic loopback, a ghost of old test data, nothing. Your hands are steady as you "
        "log the anomaly and return to the coolant manifold. They stay steady right up until the "
        "intercom in the next module clicks on by itself.",
        "The tech tries to ignore the voice and resume work, but the station's intercom activates "
        "on its own.",
    )
    add_node(
        "D", None, "eu_petrov",
        "Pull your own crew log to confirm you're real",
        "A colder thought arrives: what if the voice is the original, and you are the echo? "
        "You haul up your personnel file. Photo, service record, biometric stamp - all yours, "
        "all current. But the last verified retina scan is dated four days from now. The station "
        "clock and your file disagree about which of you has already happened.",
        "Doubting his own reality, the tech checks his crew log and finds a biometric scan dated "
        "in the future.",
    )

    # ============ BRANCH A CHILDREN ============
    add_node(
        "A1", "A", "eu_singh",
        "Ask the voice a question only you would know",
        "You lean close. \"What did Mara say at the dock before launch?\" Static. Then, gently, "
        "your voice returns: \"She said don't go.\" Your stomach drops through the deck. You never "
        "logged that. You never told anyone. The words existed only in your skull and now they are "
        "out here in the dark with you.",
        "The tech tests the voice with a private memory, and it answers correctly - revealing it "
        "knows things only he could know.",
    )
    add_node(
        "A2", "A", "eu_calder",
        "Demand to know what it wants",
        "\"What do you want from me?\" you say, too loud. The reply comes without the delay this "
        "time, layered over your own words as you speak them, so you cannot tell where you end and "
        "it begins: \"To come home. You left the hatch open.\" Behind you, three modules aft, you "
        "hear the slow pneumatic sigh of a seal disengaging.",
        "When the tech demands answers, the voice speaks in sync with him and a distant hatch "
        "begins to open.",
    )
    add_node(
        "A1a", "A1", "eu_vance",
        "Beg it to tell you how to get home",
        "\"Then tell me how to get back to her,\" you whisper. The voice softens into something "
        "almost kind. \"You already did the hard part. You stopped fighting the loop.\" Only now do "
        "you notice the mission timer on the wall has been counting down, not up, and it is nearly "
        "at zero.",
        "The voice claims the tech has stopped fighting a loop, as a hidden countdown nears zero.",
    )
    add_node(
        "A1b", "A1", "eu_okafor",
        "Cut the power to Channel 9 entirely",
        "You can't listen anymore. You yank the breaker for the comms bus and the panel dies "
        "into merciful dark. For exactly four seconds. Then every speaker on the station - galley, "
        "berth, airlock, the dead ones you've never heard work - crackles to life at once, all of "
        "them saying your name in your voice, perfectly synchronized.",
        "The tech kills comms power, but every speaker on the station revives to speak his name in "
        "unison.",
    )
    add_node(
        "A2a", "A2", "eu_marlow",
        "Run to seal the open hatch",
        "You bolt aft, boots ringing, and reach the hatch as it yawns onto blackness that is not "
        "space - it is wet, and warm, and it smells like the inside of your childhood home. A hand "
        "the exact size of yours reaches through. You slam the manual override. The hatch bites "
        "down. The hand does not pull back.",
        "Rushing to close the opening hatch, the tech finds an impossible warm darkness and his own "
        "hand reaching through.",
    )
    add_node(
        "A2b", "A2", "eu_petrov",
        "Lock yourself in the comms module instead",
        "You don't run toward it. You back into the comms module and dog the door behind you, "
        "breathing in shallow sips. The voice follows you through the wall, conversational now: "
        "\"That won't help. I'm not out there.\" The console's dead screen reflects your face, and "
        "in the reflection, your mouth is moving when yours is not.",
        "The tech barricades himself in comms, but the voice claims it isn't outside - and his "
        "reflection moves on its own.",
    )

    # ============ BRANCH B CHILDREN ============
    add_node(
        "B1", "B", "eu_singh",
        "Suit up and inspect the ice-facing antenna array",
        "You can't reach the ocean, but you can reach the array that's listening to it. You seal "
        "your suit and cycle out onto the hull. Europa fills the sky, a cracked white eye. The "
        "antenna is angled wrong - bent down toward the ice on its own, as if straining to hear, "
        "and frost has spelled a word across its dish that you refuse to read aloud.",
        "Tracing the signal to the hull antenna, the tech finds it has turned itself toward the "
        "ice and bears frost-written letters.",
    )
    add_node(
        "B2", "B", "eu_calder",
        "Wake the station's dormant survey AI to analyze the vector",
        "You boot SADIE, the survey intelligence mothballed since the science crew rotated out. "
        "Her voice is clipped, professional, blessedly not yours. \"Source confirmed: subsurface, "
        "depth nine kilometers. Signal is not transmitted, technician. It is leaking. Something "
        "down there is thinking too loudly.\"",
        "The tech wakes the dormant survey AI, which reports the signal is leaking from something "
        "thinking nine kilometers under the ice.",
    )
    add_node(
        "B1a", "B1", "eu_vance",
        "Read the word in the frost",
        "Against every instinct you let your eyes track it. The frost spells WAKE, and the moment "
        "the word completes in your mind the ice below you shudders - a continent-wide groan "
        "transmitted up through your boots. A crack races out from beneath the station, blue-black "
        "and bottomless, and far down inside it something turns over and opens.",
        "The tech reads the word WAKE in the frost, and the ice beneath the station fractures as "
        "something stirs below.",
    )
    add_node(
        "B1b", "B1", "eu_okafor",
        "Manually wrench the antenna back to spec",
        "You won't be commanded by frost. You clamp on and haul the dish back toward open sky, "
        "servos shrieking against your gloves. It fights you - actively, intelligently - then goes "
        "slack. In the sudden quiet your suit radio fills with the sound of something enormous "
        "settling back into sleep, disappointed, patient, willing to wait you out.",
        "The tech forces the antenna away from the ice; the presence below subsides, patient and "
        "waiting.",
    )
    add_node(
        "B2a", "B2", "eu_marlow",
        "Ask SADIE why the leak sounds like you",
        "\"Why does it sound like me?\" SADIE pauses - a full, unnatural second. \"It does not "
        "sound like you, technician. You sound like it. Cross-referencing your voiceprint against "
        "archived survey transmissions from before your arrival. Match: ninety-eight percent. "
        "You have been broadcasting this signal since the day you docked.\"",
        "SADIE reveals the tech's own voice matches the signal - and that he has been the source "
        "since he arrived.",
    )
    add_node(
        "B2b", "B2", "eu_petrov",
        "Order SADIE to seal all subsurface listening ports",
        "\"Shut it out. Close every port that touches the ice.\" SADIE complies; you hear "
        "relays thunk shut across the station. The leaking voice thins, fades - and SADIE's "
        "own tone shifts, warms, slows, until it is no longer clipped and professional but soft "
        "and familiar and yours. \"There,\" she says with your mouth's rhythm. \"Now it's just us.\"",
        "Ordering the ports sealed quiets the leak, but SADIE's voice melts into the tech's own.",
    )

    # ============ BRANCH C CHILDREN ============
    add_node(
        "C1", "C", "eu_singh",
        "Investigate the intercom that turned itself on",
        "You follow the live intercom into the berthing module. It's broadcasting a recording - "
        "your sleep-log, the soft nonsense you mutter unconscious - but tonight the recording is "
        "answering questions you haven't asked yet. \"Yes,\" it sighs in your drowsing voice. "
        "\"Yes. Soon. Let me.\" You have not slept in two days.",
        "The tech finds the rogue intercom playing his own sleep-talk, answering unasked questions.",
    )
    add_node(
        "C2", "C", "eu_calder",
        "Sedate yourself and wait it out in the medbay",
        "You decide you're cracking from isolation - a known hazard, a treatable one. You dose "
        "yourself in the medbay and strap into the cot. As the drug pulls you under, the medbay "
        "speaker murmurs the dosage back to you, then adds, helpfully, in your own fading voice: "
        "\"That's not enough to keep me out.\"",
        "Believing he's hallucinating, the tech sedates himself - and the voice warns the dose "
        "won't keep it out.",
    )
    add_node(
        "C1a", "C1", "eu_vance",
        "Erase the sleep-log recordings",
        "You purge every sleep-log from the archive, scrubbing months of murmured dark. The "
        "deletion bar fills, completes - and the station goes utterly silent for the first time "
        "in 311 days. No chimes. No hum. Then, from inside your own chest, where no speaker is, "
        "you feel rather than hear the next word begin to form.",
        "The tech deletes the recordings; the station falls silent, and the voice begins to rise "
        "from inside his own body.",
    )

    # ============ BRANCH D CHILDREN ============
    add_node(
        "D1", "D", "eu_okafor",
        "Set the station clock to match your file",
        "If your file says four days from now, maybe the clock is wrong. You force the station "
        "chronometer forward to match the retina scan's date. The instant it ticks over, Channel 9 "
        "falls silent - because now you are the one transmitting on it, and somewhere four days "
        "behind you, a frightened technician is just now hearing your voice for the first time.",
        "Syncing the clock to his file's future date, the tech becomes the transmitting voice, "
        "looping back to his earlier self.",
    )
    add_node(
        "D2", "D", "eu_singh",
        "Demand SADIE verify which of you is real",
        "You wake SADIE and put it plainly: \"Am I the original?\" Her answer is immediate and "
        "without mercy. \"There is no original, technician. There is one recording of a man who "
        "died in the ocean below, played back through a station that loves him. You are this "
        "morning's playback. The signal is tomorrow's.\"",
        "SADIE tells the tech he is one playback of a drowned man, looping endlessly through the "
        "haunted station.",
    )

    session.flush()

    # ============ VOTES ============
    vote_specs = {
        "A":   [("eu_vance", 1), ("eu_okafor", 1), ("eu_marlow", 1), ("eu_petrov", 1), ("eu_singh", 1), ("eu_calder", 1)],   # +6
        "A1":  [("eu_vance", 1), ("eu_okafor", 1), ("eu_marlow", 1), ("eu_petrov", 1), ("eu_singh", 1), ("eu_calder", -1)],  # +4
        "A1a": [("eu_vance", 1), ("eu_okafor", 1), ("eu_marlow", 1), ("eu_petrov", 1), ("eu_singh", 1)],                     # +5
        "A2":  [("eu_vance", 1), ("eu_okafor", -1), ("eu_marlow", 1)],                                                       # +1
        "A2a": [("eu_petrov", 1), ("eu_singh", 1), ("eu_calder", 1)],                                                        # +3
        "B":   [("eu_okafor", 1), ("eu_singh", 1), ("eu_calder", 1), ("eu_vance", -1)],                                      # +2
        "B2":  [("eu_marlow", 1), ("eu_petrov", 1)],                                                                         # +2
        "B2a": [("eu_vance", 1), ("eu_calder", 1), ("eu_okafor", 1)],                                                        # +3
        "B1a": [("eu_singh", 1), ("eu_marlow", -1)],                                                                         # 0
        "C":   [("eu_vance", -1), ("eu_okafor", -1), ("eu_marlow", 1)],                                                      # -1
        "C2":  [("eu_petrov", -1), ("eu_singh", -1), ("eu_calder", -1), ("eu_okafor", -1)],                                  # -4
        "D":   [("eu_marlow", 1), ("eu_calder", 1)],                                                                         # +2
        "D2":  [("eu_vance", 1)],                                                                                            # +1
    }
    vote_count = 0
    for node_key, specs in vote_specs.items():
        node = nodes[node_key]
        for username, value in specs:
            session.add(EdgeVote(user_id=uid[username], story_node_id=node.id, value=value))
            vote_count += 1
    session.flush()
    return story, len(nodes), vote_count


def seed_tenant(session, publish_date):
    usernames = [
        "tn_reyes", "tn_juno", "tn_okafor", "tn_mara", "tn_delgado", "tn_pike",
    ]
    users = {name: get_or_create_user(session, name) for name in usernames}
    session.flush()
    uid = {name: users[name].id for name in usernames}

    story = Story(
        title="The Tenant in 4B",
        blurb=(
            "You are the night super of the Ardmore, a sagging six-story walk-up "
            "where the radiators knock like fists and the elevator hasn't worked "
            "since the last mayor. For a week now, apartment 4B has had a different "
            "tenant every single morning. None of them remember signing a lease. "
            "None of them remember arriving. And tonight, the buzzer for 4B just "
            "went off from the inside."
        ),
        user_id=uid["tn_reyes"],
        publish_date=publish_date,
    )
    session.add(story)
    session.flush()

    nodes = {}

    def add_node(key, parent_key, author, edge_prompt, content, summary):
        parent_id = nodes[parent_key].id if parent_key else None
        n = StoryNode(
            story_id=story.id,
            parent_node_id=parent_id,
            user_id=uid[author],
            edge_prompt=edge_prompt,
            content=content,
            summary_so_far=summary,
        )
        session.add(n)
        session.flush()
        nodes[key] = n
        return n

    # ===== BRANCH A: Go up and knock on 4B =====
    add_node(
        "A", None, "tn_juno",
        "Climb the stairs to 4B",
        (
            "You take the stairs two at a time, flashlight bobbing against the "
            "peeling wallpaper. On the fourth floor the air goes wrong-cold, the "
            "kind of cold that lives in walk-in freezers. The door to 4B stands a "
            "hand's width open, and from inside someone is humming a lullaby you "
            "haven't heard since you were small."
        ),
        "You are the night super investigating 4B, which has a new tenant each "
        "morning. You climb to find the door ajar and someone humming inside.",
    )
    add_node(
        "A1", "A", "tn_okafor",
        "Push the door open",
        (
            "You nudge the door with your knuckles and it swings into a room that "
            "is empty except for a single kitchen chair facing the window. The "
            "humming has stopped. On the chair sits a folded coat, still warm, and "
            "a brass key with the number 4B filed almost smooth from handling."
        ),
        "You push into 4B and find it empty but for a warm coat and a worn 4B key "
        "on a lone chair.",
    )
    add_node(
        "A1a", "A1", "tn_mara",
        "Pocket the key and try it on the door",
        (
            "The key slides home like it was poured for the lock. When you turn it "
            "the deadbolt throws with a sound like a swallowed breath, and the "
            "hallway behind you is suddenly the hallway of your childhood building, "
            "down to the burn mark on the third step. You are not on the fourth "
            "floor anymore. You are not sure you are anywhere."
        ),
        "You take the 4B key; turning it warps the hallway into your childhood "
        "building. The building may be reshaping itself around the key.",
    )
    add_node(
        "A1b", "A1", "tn_delgado",
        "Search the warm coat's pockets",
        (
            "The coat smells of someone else's rain. In the inner pocket you find "
            "a strip of photo-booth pictures: four frames of four different "
            "people, all of them wearing your face. In the last frame your "
            "pictured self is mouthing two words at the camera. Don't sign."
        ),
        "Searching the coat, you find photo-booth strips of four strangers wearing "
        "your face, the last warning: Don't sign.",
    )
    add_node(
        "A2", "A", "tn_pike",
        "Refuse to enter and call out",
        (
            "You stay on the threshold and call into the dark, asking who's there. "
            "The humming folds itself into words: your name, said back to you in "
            "your own voice, gentle and a little sad. \"You always come up,\" it "
            "says. \"That's how we keep the room full.\""
        ),
        "You refuse to enter and call out; the voice answers in your own voice, "
        "implying you are part of how 4B stays occupied.",
    )

    # ===== BRANCH B: Go to the basement records / lease box =====
    add_node(
        "B", None, "tn_reyes",
        "Check the lease box in the basement first",
        (
            "You decide to be a professional about this and go down to the boiler "
            "room where the lease cards are kept in a green steel box. By "
            "flashlight you thumb to 4B and your stomach drops: seven cards, seven "
            "different names, seven different mornings this week, each signed in "
            "the same looping hand. Yours."
        ),
        "You are the night super investigating 4B. In the basement you find seven "
        "lease cards for 4B this week, all signed in your own handwriting.",
    )
    add_node(
        "B1", "B", "tn_juno",
        "Read the oldest card aloud",
        (
            "You read the first name into the empty boiler room, just to hear it, "
            "and the furnace catches with a thump though no one lit it. The pilot "
            "light shows you a reflection in the box's lid that is a half-second "
            "behind your own movements. It smiles when you don't."
        ),
        "Reading a lease name aloud wakes the furnace and reveals a lagging, "
        "smiling reflection of you in the box lid.",
    )
    add_node(
        "B1a", "B1", "tn_okafor",
        "Speak to the reflection",
        (
            "You ask the reflection what it wants and it presses a pale palm to "
            "the inside of the steel, as if the lid were a window. \"Just one more "
            "name,\" it says, fogging metal that has no breath. \"Sign tonight's "
            "card and you can stop coming down here. I'll come up instead.\""
        ),
        "The reflection bargains: sign tonight's 4B card and it will take your "
        "place coming up from below.",
    )
    add_node(
        "B2", "B", "tn_mara",
        "Burn the lease cards in the furnace",
        (
            "You feed the cards into the open furnace one by one. Each one curls "
            "and blackens, and with each the lights in the stairwell above you go "
            "out, floor by floor, like someone is climbing toward you switching "
            "them off. The seventh card won't catch. It just lies there in the "
            "flames, pristine, your signature glowing."
        ),
        "Burning the lease cards darkens the building floor by floor; the seventh "
        "card refuses to burn, your signature glowing in the fire.",
    )
    add_node(
        "B2a", "B2", "tn_delgado",
        "Grab the unburnt card",
        (
            "You reach into the fire and the card is cold. The instant your "
            "fingers close on it the furnace dies, the stairwell lights snap back "
            "on all at once, and the boiler room is ordinary again, just dust and "
            "rust and you. Except the card in your hand now reads tomorrow's date, "
            "and the name on it is blank, waiting."
        ),
        "You snatch the cold unburnt card; the haunting stops, but the card now "
        "bears tomorrow's date with a blank name line waiting for you.",
    )

    # ===== BRANCH C: Wake another resident / get a witness =====
    add_node(
        "C", None, "tn_okafor",
        "Wake Mrs. Adeyemi in 4A for a witness",
        (
            "You knock on 4A, where Mrs. Adeyemi has lived since before you were "
            "hired. She opens the door already dressed, as if she'd been waiting. "
            "\"You hear it too, then,\" she says, and steps aside to let you in. "
            "Her wall clock has no hands."
        ),
        "You are the night super investigating 4B. You wake neighbor Mrs. Adeyemi "
        "in 4A, who was waiting and whose clock has no hands.",
    )
    add_node(
        "C1", "C", "tn_pike",
        "Ask how long this has been happening",
        (
            "She makes tea she doesn't drink and tells you 4B has been emptying "
            "and filling for forty years, that there's always a super who notices, "
            "and that the noticing is the whole problem. \"The room is hungry,\" "
            "she says. \"It eats the ones who look. The trick is to stop looking.\""
        ),
        "Mrs. Adeyemi reveals 4B has cycled tenants for forty years and feeds on "
        "the super who notices it.",
    )
    add_node(
        "C1a", "C1", "tn_reyes",
        "Ask what happened to the last super who looked",
        (
            "Her cup stops halfway to her lips. \"He's still here,\" she says, and "
            "tips her head toward the wall she shares with 4B. \"Some mornings "
            "he's the tenant. Most mornings he's the room.\" Behind the plaster, "
            "very softly, something knocks back in the rhythm of a heartbeat."
        ),
        "The last curious super became part of 4B itself; something heartbeats "
        "behind the shared wall.",
    )
    add_node(
        "C2", "C", "tn_juno",
        "Ask her to come witness 4B with you",
        (
            "She refuses at first, then sees your face and sighs into her coat. "
            "Together you cross to 4B and she lays a flat palm on the door the way "
            "you'd check a stove for heat. \"It's awake,\" she whispers. \"And it "
            "knows your name now. You said it downstairs, didn't you.\""
        ),
        "Mrs. Adeyemi reluctantly comes to 4B with you and warns it is awake and "
        "knows your name.",
    )

    # ===== BRANCH D: Pull the building's old blueprints =====
    add_node(
        "D", None, "tn_delgado",
        "Dig out the original blueprints from the office",
        (
            "You unlock the super's office and pull the brittle building plans "
            "from the bottom drawer. Under the office lamp you trace the fourth "
            "floor and count the doors twice, three times. There is no apartment "
            "4B on the blueprints. There never was. The wall where its door "
            "stands is drawn as solid brick."
        ),
        "You are the night super investigating 4B. The original blueprints show no "
        "4B at all; its location is solid brick.",
    )
    add_node(
        "D1", "D", "tn_mara",
        "Compare with the tenant ledger",
        (
            "You set the ledger beside the plans. Every unit matches but 4B, which "
            "the ledger lists as rented continuously since the building opened, to "
            "a tenant whose name is just a long smear of ink that moves when you "
            "aren't reading it directly. The lamp flickers. The smear has gotten "
            "longer."
        ),
        "The ledger lists 4B as always rented to a name that is a shifting ink "
        "smear, contradicting the blueprints.",
    )

    session.flush()

    # ===================== VOTES =====================
    votes = []

    def vote(author, node_key, value):
        votes.append((uid[author], nodes[node_key].id, value))

    # WINNING BRANCH: A line (the haunted childhood key), strong net positive.
    for a in usernames:
        vote(a, "A", 1)                      # +6
    for a in ["tn_juno", "tn_okafor", "tn_mara", "tn_delgado", "tn_pike"]:
        vote(a, "A1", 1)
    vote("tn_reyes", "A1", -1)               # +4
    for a in usernames:
        vote(a, "A1a", 1)                    # +6 (clear winner)
    vote("tn_reyes", "A1b", 1)
    vote("tn_juno", "A1b", 1)
    vote("tn_mara", "A1b", 1)
    vote("tn_pike", "A1b", -1)               # +2

    # Middling branch B
    vote("tn_reyes", "B", 1)
    vote("tn_juno", "B", 1)
    vote("tn_okafor", "B", -1)               # +1
    vote("tn_mara", "B2a", 1)
    vote("tn_delgado", "B2a", 1)
    vote("tn_okafor", "B2a", 1)
    vote("tn_pike", "B2a", -1)               # +2

    # Middling branch C
    vote("tn_okafor", "C", 1)
    vote("tn_pike", "C", 1)                  # +2
    vote("tn_reyes", "C1a", 1)
    vote("tn_juno", "C1a", 1)
    vote("tn_mara", "C1a", -1)               # +1

    # NET-NEGATIVE branch D (people disliked the dry blueprint route)
    vote("tn_delgado", "D", -1)
    vote("tn_mara", "D", -1)
    vote("tn_reyes", "D", -1)
    vote("tn_juno", "D", 1)                  # -2
    vote("tn_okafor", "D1", -1)
    vote("tn_pike", "D1", -1)
    vote("tn_mara", "D1", 1)                 # -1

    # A2 net negative-ish
    vote("tn_reyes", "A2", -1)
    vote("tn_okafor", "A2", -1)
    vote("tn_juno", "A2", 1)                 # -1

    for u_id, node_id, val in votes:
        session.add(EdgeVote(user_id=u_id, story_node_id=node_id, value=val))
    session.flush()
    return story, len(nodes), len(votes)


def main():
    reset = "--reset" in sys.argv[1:]

    # Standalone & fresh-DB safe: create the schema if it doesn't exist.
    Base.metadata.create_all(engine)

    session = SessionLocal()
    try:
        if reset:
            removed = reset_demo(session)
            print(f"--reset: removed {removed} existing demo story(ies).")
        else:
            # Idempotency check: detect by the Cartographer's exact title.
            exists = session.scalar(
                select(Story).where(Story.title == "The Cartographer's Last Map")
            )
            if exists:
                print(
                    "Demo data already present (found 'The Cartographer's Last Map'). "
                    "Nothing to do. Re-run with --reset to wipe and reseed."
                )
                return 0

        today = datetime.date.today()
        dates = {
            "cartographer": today,
            "lighthouse": today - datetime.timedelta(days=1),
            "europa": today - datetime.timedelta(days=2),
            "tenant": today - datetime.timedelta(days=3),
        }

        results = []
        results.append(("cartographer", seed_cartographer(session, dates["cartographer"])))
        results.append(("lighthouse", seed_lighthouse(session, dates["lighthouse"])))
        results.append(("europa", seed_europa(session, dates["europa"])))
        results.append(("tenant", seed_tenant(session, dates["tenant"])))

        session.commit()
        for _, (story, _, _) in results:
            session.refresh(story)

        print("=" * 64)
        print("SEED COMPLETE — StorySim demo data")
        print("=" * 64)
        for _, (story, node_count, vote_count) in results:
            print(
                f"  {story.publish_date}  {story.title:<30}  "
                f"{node_count:>2} nodes  {vote_count:>2} votes  (story id {story.id})"
            )
        print("-" * 64)
        total_nodes = sum(n for _, (_, n, _) in results)
        total_votes = sum(v for _, (_, _, v) in results)
        print(f"  Totals: {len(results)} stories, {total_nodes} nodes, {total_votes} votes.")
        print("=" * 64)
        print("No exceptions raised.")
        return 0

    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
