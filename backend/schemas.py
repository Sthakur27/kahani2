"""Pydantic request bodies. Fields are intentionally lenient (optional with
defaults) so handlers can reproduce the original validation messages/codes
rather than emitting FastAPI's default 422 validation envelope."""
from pydantic import BaseModel


class Credentials(BaseModel):
    username: str | None = None
    password: str | None = None


class NodeCreate(BaseModel):
    content: str | None = None
    edge_prompt: str | None = None
    parent_node_id: int | None = None


class DraftRequest(BaseModel):
    bullets: str | None = None
    story_id: int | None = None
    parent_node_id: int | None = None


class DraftRollRequest(BaseModel):
    idea: str | None = None
    story_id: int | None = None
    parent_node_id: int | None = None


class RollOutcomeIn(BaseModel):
    content: str | None = None
    hp: int = 0
    kind: str = "story"


class RollEdgeCreate(BaseModel):
    parent_node_id: int | None = None
    label: str | None = None
    check_stat: str | None = None
    check_dc: int | None = None
    outcomes: dict[str, RollOutcomeIn] = {}


class VoteRequest(BaseModel):
    value: int = 1


class PromoteRequest(BaseModel):
    story_id: int | None = None  # promote one story; None = all


class StartRunRequest(BaseModel):
    option_id: int | None = None   # a story's CharacterOption (curated cast)
    char_class: str | None = None  # warrior | rogue | mage (classes fallback)
    name: str | None = None
