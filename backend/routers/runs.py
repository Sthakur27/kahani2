"""RPG run lifecycle: start a playthrough (pick a class), read its state, and
take a (plain) edge applying its effects. Roll edges arrive in a later phase."""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

import game
from auth import current_user
from db import get_db
from models import (
    CharacterOption,
    Edge,
    EdgeOutcome,
    Requirement,
    Run,
    RunCharacter,
    RunFlag,
    RunInventory,
    RunStep,
    Story,
    StoryNode,
    User,
)

_STAT_VIEW = {
    "str": "strength", "dex": "dexterity", "con": "constitution",
    "int": "intelligence", "wis": "wisdom", "cha": "charisma",
}
_SYSTEM_BLURB = {
    "warrior": "Strong & tough — STR/CON.",
    "rogue": "Nimble & clever — DEX/INT.",
    "mage": "Keen & wise — INT/WIS.",
}
_SYSTEM_ICON = {"warrior": "🛡", "rogue": "🗡", "mage": "✨"}


def _archetype_view(archetype: str) -> dict:
    preset = game.CLASS_PRESETS.get(archetype, game.CLASS_PRESETS["warrior"])
    return {
        "archetype": archetype,
        "hp": preset["hp"],
        "stats": {short: preset[col] for short, col in _STAT_VIEW.items()},
    }
from schemas import StartRunRequest

router = APIRouter(prefix="/api", tags=["runs"])

STAT_KEYS = ("strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma")


def _edge_brief(e: Edge) -> dict:
    return {
        "edge_id": e.id,
        "label": e.label,
        "kind": e.kind,
        "check_stat": e.check_stat,
        "check_dc": e.check_dc,
    }


def _run_state(session: Session, run: Run) -> dict:
    """Everything the play UI needs: current node, party snapshot, and the
    choices (active edges) available from where the run stands."""
    node = session.get(StoryNode, run.current_node_id) if run.current_node_id else None
    edges = session.scalars(
        select(Edge)
        .where(Edge.story_id == run.story_id)
        .where(
            Edge.from_node_id.is_(None)
            if run.current_node_id is None
            else Edge.from_node_id == run.current_node_id
        )
        .order_by(Edge.id)
    ).all()
    return {
        "id": run.id,
        "story_id": run.story_id,
        "status": run.status,
        "current_node_id": run.current_node_id,
        "node": (
            {
                "id": node.id,
                "content": node.content,
                "kind": node.kind,
                "is_ending": node.is_ending,
            }
            if node
            else None
        ),
        "snapshot": game.build_snapshot(session, run),
        "choices": [_edge_brief(e) for e in edges],
    }


def _owned_run(session: Session, run_id: int, user: User) -> Run:
    run = session.get(Run, run_id)
    if run is None or run.user_id != user.id:
        raise HTTPException(404, "run not found")
    return run


def _check_requirements(session: Session, run: Run, char: RunCharacter, edge: Edge) -> None:
    for r in session.scalars(select(Requirement).where(Requirement.edge_id == edge.id)):
        if r.type == "stat_min":
            col = game.STAT_COLS.get(r.key)
            if col and getattr(char, col) < (r.amount or 0):
                raise HTTPException(409, f"requires {r.key} {r.amount}")
        elif r.type == "flag":
            if session.scalar(
                select(RunFlag).where(RunFlag.run_id == run.id, RunFlag.key == r.key)
            ) is None:
                raise HTTPException(409, f"requires flag '{r.key}'")
        # item requirements arrive with the items phase


@router.get("/stories/{story_id}/characters")
def story_characters(story_id: int, db: Session = Depends(get_db)):
    """The selectable cast for a story: its curated CharacterOptions if any, else
    the generic Warrior/Rogue/Mage classes. Each carries the archetype's stats."""
    if db.get(Story, story_id) is None:
        raise HTTPException(404, "story not found")
    opts = db.scalars(
        select(CharacterOption)
        .where(CharacterOption.story_id == story_id)
        .order_by(CharacterOption.sort_order, CharacterOption.id)
    ).all()
    if opts:
        return [
            {"id": o.id, "name": o.name, "blurb": o.blurb, "icon": o.icon,
             **_archetype_view(o.archetype)}
            for o in opts
        ]
    # fallback: generic classes (no option id — picked by char_class)
    return [
        {"id": None, "name": a.capitalize(), "blurb": _SYSTEM_BLURB[a],
         "icon": _SYSTEM_ICON[a], **_archetype_view(a)}
        for a in game.CLASS_PRESETS
    ]


@router.post("/stories/{story_id}/runs", status_code=201)
def start_run(
    story_id: int,
    body: StartRunRequest,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Begin a playthrough. Pick a curated CharacterOption (option_id) or a generic
    class (char_class). Spawns a party-of-1 and logs the seq-0 snapshot."""
    story = db.get(Story, story_id)
    if story is None:
        raise HTTPException(404, "story not found")

    if body.option_id is not None:
        opt = db.get(CharacterOption, body.option_id)
        if opt is None or opt.story_id != story_id:
            raise HTTPException(400, "invalid character option")
        archetype = opt.archetype
        char_name = opt.name
    else:
        archetype = (body.char_class or "warrior").lower()
        char_name = (body.name or "Adventurer").strip()[:60] or "Adventurer"
    preset = game.CLASS_PRESETS.get(archetype)
    if preset is None:
        raise HTTPException(400, f"unknown archetype '{archetype}'")

    run = Run(user_id=user.id, story_id=story_id, current_node_id=None, status="active")
    db.add(run)
    db.flush()

    char = RunCharacter(
        run_id=run.id,
        name=char_name,
        char_class=archetype,
        hp=preset["hp"],
        max_hp=preset["hp"],
        **{k: preset[k] for k in STAT_KEYS},
    )
    db.add(char)
    db.flush()

    db.add(RunStep(run_id=run.id, seq=0, arrived_node_id=None,
                   snapshot=game.build_snapshot(db, run)))
    db.commit()
    db.refresh(run)
    return _run_state(db, run)


@router.get("/runs/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    return _run_state(db, _owned_run(db, run_id, user))


@router.post("/runs/{run_id}/take/{edge_id}")
def take_edge(
    run_id: int,
    edge_id: int,
    db: Session = Depends(get_db),
    user: User = Depends(current_user),
):
    """Take a plain edge: validate it's reachable, apply its outcome's effects to
    the character, advance the run, and append a snapshotted step."""
    run = _owned_run(db, run_id, user)
    if run.status != "active":
        raise HTTPException(409, "run is not active")

    edge = db.get(Edge, edge_id)
    if edge is None or edge.story_id != run.story_id:
        raise HTTPException(404, "edge not found")
    if edge.from_node_id != run.current_node_id:
        raise HTTPException(409, "that choice isn't available from here")

    char = db.scalar(select(RunCharacter).where(RunCharacter.run_id == run.id))
    if char is None:
        raise HTTPException(409, "run has no character")
    _check_requirements(db, run, char, edge)

    # Resolve the outcome: a plain edge has one; a roll edge rolls a d20 + the
    # character's stat modifier vs the DC and picks the band (with fallback).
    roll_info = None
    if edge.kind == "roll":
        roll_info = game.roll_check(char, edge.check_stat, edge.check_dc)
        outcomes = {
            o.band: o
            for o in db.scalars(select(EdgeOutcome).where(EdgeOutcome.edge_id == edge.id))
        }
        outcome = next(
            (outcomes[b] for b in game.BAND_FALLBACK.get(roll_info["band"], [roll_info["band"]]) if b in outcomes),
            None,
        )
        if outcome is None:
            raise HTTPException(409, "roll edge has no usable outcome")
        roll_info["effective_band"] = outcome.band
    else:
        outcome = db.scalar(
            select(EdgeOutcome).where(
                EdgeOutcome.edge_id == edge.id, EdgeOutcome.band == "plain"
            )
        )
        if outcome is None:
            raise HTTPException(409, "edge has no plain outcome")

    applied = game.apply_effects(db, run, char, outcome.effects)
    run.current_node_id = outcome.to_node_id
    seq = (db.scalar(select(func.max(RunStep.seq)).where(RunStep.run_id == run.id)) or 0) + 1
    db.add(RunStep(
        run_id=run.id, seq=seq, edge_id=edge.id,
        arrived_node_id=outcome.to_node_id,
        roll_d20=roll_info["d20"] if roll_info else None,
        modifier=roll_info["modifier"] if roll_info else None,
        dc=roll_info["dc"] if roll_info else None,
        band_result=roll_info["band"] if roll_info else None,
        effects_applied=applied, snapshot=game.build_snapshot(db, run),
    ))
    db.commit()
    db.refresh(run)

    state = _run_state(db, run)
    state["applied_effects"] = applied
    if roll_info:
        state["roll"] = roll_info
    return state


@router.get("/runs/{run_id}/summary")
def run_summary(run_id: int, db: Session = Depends(get_db), user: User = Depends(current_user)):
    """A recap of the playthrough built from the step log: the journey (choices,
    rolls, effects, HP), aggregate stats, the final character, and the ending."""
    run = _owned_run(db, run_id, user)
    steps = db.scalars(
        select(RunStep).where(RunStep.run_id == run.id).order_by(RunStep.seq)
    ).all()
    edge_ids = [s.edge_id for s in steps if s.edge_id]
    labels = {}
    if edge_ids:
        labels = dict(
            db.execute(select(Edge.id, Edge.label).where(Edge.id.in_(edge_ids))).all()
        )

    journey, damage, rolls, successes = [], 0, 0, 0
    for s in steps:
        if s.edge_id is None:
            continue  # the initial spawn step
        effs = s.effects_applied or []
        for e in effs:
            if e.get("type") == "hp_delta" and (e.get("amount") or 0) < 0:
                damage += -e["amount"]
        roll = None
        if s.roll_d20 is not None:
            rolls += 1
            if s.band_result in ("success", "crit_success"):
                successes += 1
            roll = {"d20": s.roll_d20, "modifier": s.modifier, "dc": s.dc, "band": s.band_result}
        hp_after = None
        if s.snapshot and s.snapshot.get("characters"):
            hp_after = s.snapshot["characters"][0]["hp"]
        journey.append({
            "seq": s.seq, "label": labels.get(s.edge_id),
            "roll": roll, "effects": effs, "hp_after": hp_after,
        })

    node = db.get(StoryNode, run.current_node_id) if run.current_node_id else None
    char = db.scalar(select(RunCharacter).where(RunCharacter.run_id == run.id))
    return {
        "run_id": run.id,
        "status": run.status,  # active | dead | won
        "is_ending": bool(node and node.is_ending),
        "ending_text": node.content if (node and node.is_ending) else None,
        "character": game.character_dict(char) if char else None,
        "stats": {
            "turns": len(journey),
            "damage_taken": damage,
            "rolls": rolls,
            "successes": successes,
        },
        "journey": journey,
    }


@router.get("/me/runs")
def my_runs(db: Session = Depends(get_db), user: User = Depends(current_user)):
    """List this user's playthroughs, newest first."""
    runs = db.scalars(
        select(Run).where(Run.user_id == user.id).order_by(Run.started_at.desc())
    ).all()
    out = []
    for r in runs:
        story = db.get(Story, r.story_id)
        char = db.scalar(select(RunCharacter).where(RunCharacter.run_id == r.id))
        out.append({
            "id": r.id,
            "story_id": r.story_id,
            "story_title": story.title if story else None,
            "status": r.status,
            "current_node_id": r.current_node_id,
            "character": game.character_dict(char) if char else None,
            "started_at": r.started_at.isoformat() if r.started_at else None,
        })
    return out
