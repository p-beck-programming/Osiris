from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import database as db
from .voice import transcribe_bytes, whisper_available
from .ingestion import ingest_quick_note

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "app" / "static"


@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(
    title="Osiris",
    version="0.0.1",
    description="Personal context system — V0 idea capture.",
    lifespan=lifespan,
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class IdeaCreate(BaseModel):
    initial_note: str = Field(min_length=1, max_length=20_000)
    title: str | None = Field(default=None, max_length=180)
    source: str = Field(default="text", max_length=32)


class IdeaUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=180)
    status: str | None = None


class NoteCreate(BaseModel):
    content: str = Field(min_length=1, max_length=20_000)
    source: str = Field(default="text", max_length=32)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.webmanifest", include_in_schema=False)
def manifest():
    return FileResponse(STATIC_DIR / "manifest.webmanifest", media_type="application/manifest+json")


@app.get("/service-worker.js", include_in_schema=False)
def service_worker():
    return FileResponse(
        STATIC_DIR / "service-worker.js",
        media_type="application/javascript",
        headers={"Cache-Control": "no-cache"},
    )


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "0.0.1"}


@app.get("/api/dashboard")
def get_dashboard():
    return db.dashboard()


@app.get("/api/ideas")
def get_ideas(
    search: str = "",
    status: str = Query(default="active", pattern="^(active|archived|all)$"),
    limit: int = Query(default=100, ge=1, le=500),
):
    return db.list_ideas(search=search, status=status, limit=limit)


@app.post("/api/ideas", status_code=201)
def create_idea(payload: IdeaCreate):
    return ingest_quick_note(
        initial_note=payload.initial_note,
        title=payload.title,
        source=payload.source,
    )

@app.get("/api/ideas/{idea_id}")
def get_idea(idea_id: str):
    try:
        return db.get_idea(idea_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc


@app.patch("/api/ideas/{idea_id}")
def update_idea(idea_id: str, payload: IdeaUpdate):
    try:
        return db.update_idea(idea_id, title=payload.title, status=payload.status)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ideas/{idea_id}/notes", status_code=201)
def add_note(idea_id: str, payload: NoteCreate):
    try:
        return db.add_note(idea_id, content=payload.content, source=payload.source)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Idea not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/voice/status")
def voice_status():
    return {"available": whisper_available(), "engine": "faster-whisper"}


@app.post("/api/transcribe")
async def transcribe(file: UploadFile = File(...)):
    if not whisper_available():
        raise HTTPException(
            status_code=501,
            detail="Voice transcription is optional in V0. Install requirements-voice.txt to enable local Whisper.",
        )

    audio = await file.read()
    if not audio:
        raise HTTPException(status_code=400, detail="Empty audio file")
    if len(audio) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large")

    try:
        text = transcribe_bytes(audio, file.content_type)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {exc}") from exc

    if not text:
        raise HTTPException(status_code=422, detail="No speech detected")
    return {"text": text}
