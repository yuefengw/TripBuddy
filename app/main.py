"""FastAPI entrypoint for the TripBuddy travel agent."""

from __future__ import annotations

import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from loguru import logger

from app.api import aiops, chat, file, health
from app.config import config
from app.core.milvus_client import milvus_manager
from app.skills import load_skills


@asynccontextmanager
async def lifespan(_: FastAPI):
    logger.info("=" * 60)
    logger.info(f"Starting {config.app_name} v{config.app_version}")
    logger.info(f"Listening on http://{config.host}:{config.port}")

    try:
        milvus_manager.connect()
        logger.info("Milvus connected")
    except Exception as exc:
        logger.warning(f"Milvus connection failed, knowledge retrieval may be degraded: {exc}")

    await load_skills()
    logger.info("Skills initialized")
    logger.info("=" * 60)

    yield

    try:
        milvus_manager.close()
    except Exception as exc:
        logger.warning(f"Failed to close Milvus cleanly: {exc}")
    logger.info(f"Stopped {config.app_name}")


app = FastAPI(
    title=config.app_name,
    version=config.app_version,
    description="Travel planning and re-planning assistant powered by unified routing and tools",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router, tags=["Health"])
app.include_router(chat.router, prefix="/api", tags=["Travel Chat"])
app.include_router(file.router, prefix="/api", tags=["Knowledge Upload"])
app.include_router(aiops.router, prefix="/api", tags=["Legacy AIOps Demo"])

STATIC_DIR = "static"
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _build_index_html() -> str:
    """Inject cache-busting asset versions into the static HTML shell."""

    static_dir = Path(STATIC_DIR)
    index_path = static_dir / "index.html"
    html = index_path.read_text(encoding="utf-8")

    asset_versions = {
        "/static/styles.css": f"/static/styles.css?v={(static_dir / 'styles.css').stat().st_mtime_ns}",
        "/static/app.js": f"/static/app.js?v={(static_dir / 'app.js').stat().st_mtime_ns}",
    }

    for asset_path, versioned_path in asset_versions.items():
        html = html.replace(asset_path, versioned_path)

    return html


@app.get("/")
async def root():
    """Serve the static frontend."""

    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return HTMLResponse(
            content=_build_index_html(),
            headers={
                "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
                "Pragma": "no-cache",
                "Expires": "0",
            },
        )
    return {"message": f"Welcome to {config.app_name}", "version": config.app_version, "docs": "/docs"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=config.host,
        port=config.port,
        reload=config.debug,
        log_level="info",
    )
