"""
Main FastAPI application for Model gAItor.
"""
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from contextlib import asynccontextmanager
import asyncio
import uvicorn
import logging
import json
import sys
import os
from pathlib import Path

from . import config
from .routers import settings, library, models, destinations, retrieve
from .services.tasks import task_manager


def get_app_version() -> str:
    """Read version from APP_VERSION env var, or VERSION file, or fallback."""
    env_ver = os.getenv("APP_VERSION", "").strip()
    if env_ver:
        return env_ver
    for path in ["VERSION", "/app/VERSION"]:
        try:
            with open(path) as f:
                return f.read().strip()
        except FileNotFoundError:
            continue
    return "0.0.0"


# Configure logging
logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL, logging.INFO),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)

logger = logging.getLogger(__name__)


class AccessLogFilter(logging.Filter):
    """Filter to suppress routine GET requests from access logs at INFO level."""

    def filter(self, record: logging.LogRecord) -> bool:
        if record.levelno == logging.INFO:
            message = record.getMessage()
            if '"GET /health' in message:
                return False
            if '"GET /assets/' in message:
                return False
        return True


uvicorn_access_logger = logging.getLogger("uvicorn.access")
uvicorn_access_logger.addFilter(AccessLogFilter())


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    # Ensure library and dest paths exist (they should be volume mounts)
    config.LIBRARY_PATH.mkdir(parents=True, exist_ok=True)
    config.DESTINATIONS_ROOT.mkdir(parents=True, exist_ok=True)

    # Auto-initialize library if not yet initialized
    from .services.metadata import is_library_initialized, initialize_library, ensure_metadata_dir
    ensure_metadata_dir()
    if not is_library_initialized():
        initialize_library()
        logger.info("Library auto-initialized on first startup")

    logger.info(f"Model gAItor v{app.version} starting")
    logger.info(f"Library path: {config.LIBRARY_PATH}")
    logger.info(f"Destinations root: {config.DESTINATIONS_ROOT}")
    logger.info(f"Log level: {config.LOG_LEVEL}")

    yield

    logger.info("Model gAItor shutting down")


app = FastAPI(
    title="Model gAItor",
    description="AI model library manager and sync tool",
    version=get_app_version(),
    lifespan=lifespan,
    redirect_slashes=False,
    redoc_url=None,
)

# CORS - same-origin for security; loosen in dev if needed
app.add_middleware(
    CORSMiddleware,
    allow_origins=[],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response: Response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; connect-src 'self' ws: wss:; font-src 'self'"
        )
        if request.url.path.startswith("/assets/"):
            response.headers["Cache-Control"] = "public, max-age=86400"
        return response


app.add_middleware(SecurityHeadersMiddleware)

# Include API routers
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(library.router, prefix="/api/library", tags=["library"])
app.include_router(models.router, prefix="/api/models", tags=["models"])
app.include_router(destinations.router, prefix="/api/destinations", tags=["destinations"])
app.include_router(retrieve.router, prefix="/api/retrieve", tags=["retrieve"])


# --- WebSocket for real-time task progress ---

@app.websocket("/ws/tasks")
async def websocket_tasks(websocket: WebSocket):
    """WebSocket endpoint for real-time task progress updates."""
    await websocket.accept()
    queue = task_manager.subscribe()
    try:
        # Send current active tasks on connect
        active = task_manager.get_active_tasks()
        if active:
            await websocket.send_text(json.dumps({"type": "init", "tasks": active}))
        # Stream updates
        while True:
            msg = await queue.get()
            await websocket.send_text(json.dumps({"type": "update", **msg}))
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        task_manager.unsubscribe(queue)


@app.get("/api/tasks")
async def list_active_tasks():
    """List currently active background tasks."""
    return {"tasks": task_manager.get_active_tasks()}


@app.post("/api/tasks/{task_id}/cancel")
async def cancel_task(task_id: str):
    """Cancel a running background task."""
    if task_manager.cancel_task(task_id):
        return {"status": "cancelled", "task_id": task_id}
    return JSONResponse(
        status_code=404,
        content={"detail": "Task not found or already completed"},
    )

# Serve built frontend static assets
FRONTEND_DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist"
if FRONTEND_DIST.exists():
    app.mount("/assets", StaticFiles(directory=str(FRONTEND_DIST / "assets")), name="assets")


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": app.version,
    }


@app.get("/{path:path}")
async def frontend_catchall(path: str):
    """Serve the SPA for all non-API routes."""
    index_file = FRONTEND_DIST / "index.html"
    if index_file.exists():
        return FileResponse(str(index_file), media_type="text/html")
    return HTMLResponse(
        "<html><body><h1>Model gAItor</h1>"
        "<p>Frontend not built yet. Run <code>cd frontend && npm run build</code></p>"
        "</body></html>",
        status_code=200,
    )


if __name__ == "__main__":
    uvicorn.run("backend.app:app", host="0.0.0.0", port=8487, reload=True)
