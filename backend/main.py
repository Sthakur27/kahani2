"""StorySim API (FastAPI). Routes live in routers/; this module wires up the
app, CORS, a Flask-compatible {"error": ...} error envelope, and startup seeding."""
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from routers import admin, ai, auth, leaderboard, nodes, stories
from seeds import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()  # create tables + seed the first daily story (idempotent)
    yield


app = FastAPI(title="StorySim API", lifespan=lifespan)

# Dev: allow any origin. Auth is via Bearer header (no cookies), so credentials
# stay off. X-Total-Count must be exposed for the paginated list endpoints.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Total-Count"],
)


@app.exception_handler(StarletteHTTPException)
async def error_envelope(request, exc: StarletteHTTPException):
    """Preserve the original Flask shape: a string detail becomes {"error": ...};
    a dict detail (e.g. the moderation rejection) is returned verbatim."""
    detail = exc.detail
    content = detail if isinstance(detail, dict) else {"error": detail}
    return JSONResponse(status_code=exc.status_code, content=content, headers=exc.headers)


@app.get("/api/health")
def health():
    return {"status": "ok"}


for r in (auth, admin, stories, nodes, ai, leaderboard):
    app.include_router(r.router)


def _free_port(port: int) -> None:
    """Kill any stale process still listening on `port` (e.g. an orphaned reload
    worker from a previous run) so we can rebind cleanly."""
    import signal
    import subprocess

    try:
        out = subprocess.run(
            ["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"],
            capture_output=True,
            text=True,
        ).stdout
    except FileNotFoundError:
        return
    for pid in {int(p) for p in out.split() if p.strip()}:
        if pid == os.getpid():
            continue
        try:
            os.kill(pid, signal.SIGKILL)
            print(f" * Freed port {port} (killed stale pid {pid})")
        except ProcessLookupError:
            pass


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", os.environ.get("FLASK_PORT", 5051)))
    _free_port(port)
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
