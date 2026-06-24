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


class VoteRequest(BaseModel):
    value: int = 1


class StartRunRequest(BaseModel):
    char_class: str | None = None  # warrior | rogue | mage (default warrior)
    name: str | None = None
