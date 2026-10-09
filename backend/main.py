"""FIREBOX AI backend entry point.

Run with:
    uvicorn backend.main:app --host 0.0.0.0 --port 3000
"""

from __future__ import annotations

import hashlib
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from pymongo.errors import PyMongoError

from .db import MongoStore, mongo_error_message
from .model_adapter import ModelUnavailable, OllamaAdapter
from .repositories import Repositories
from .schemas import ConversationCreate, MessageCreate, SettingsUpdate

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("firebox.api")

store = MongoStore.from_environment()
repositories = Repositories(store)
model_adapter = OllamaAdapter()


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.connect()
    yield
    store.close()


app = FastAPI(title="FIREBOX AI API", version="0.1.0", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["*"], allow_headers=["*"])


@app.exception_handler(PyMongoError)
async def mongo_failure_handler(_, exc: PyMongoError) -> JSONResponse:
    logger.exception("MongoDB operation failed", exc_info=exc)
    return JSONResponse(status_code=503, content={"detail": "MongoDB is unavailable; the operation was not completed"})


class HealthResponse(BaseModel):
    status: str
    mongodb: dict[str, Any]
    storage: dict[str, Any]
    model: dict[str, Any]


class ChatRequest(BaseModel):
    message: str
    model: str | None = None
    webSearch: bool = False
    conversation_id: str | None = None


def owner_id(header_owner: str | None) -> str:
    """Single-user ownership boundary until authentication is added."""
    return (header_owner or os.getenv("FIREBOX_OWNER_ID", "local-owner")).strip()[:120] or "local-owner"


def require_database() -> Repositories:
    if not store.connected:
        raise HTTPException(status_code=503, detail=mongo_error_message(RuntimeError("MongoDB is unavailable; the operation was not completed")))
    return repositories


def now() -> datetime:
    return datetime.now(timezone.utc)


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    storage_dir = Path(os.getenv("STORAGE_DIR", "storage/uploads"))
    if not storage_dir.is_absolute():
        storage_dir = ROOT / storage_dir
    return HealthResponse(
        status="ready" if store.connected else "degraded",
        mongodb=store.status(),
        storage={"available": storage_dir.exists() and storage_dir.is_dir(), "path_configured": str(storage_dir)},
        model=model_adapter.status(),
    )


@app.post("/api/chat")
async def chat(payload: ChatRequest, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    """Generate from a configured model using persisted conversation context.

    Persistence is handled by the conversation/message endpoints so a model failure
    cannot be mistaken for a successful database write.
    """
    repo = require_database()
    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")

    context: list[dict[str, str]] = []
    if payload.conversation_id:
        conversation = repo.get_conversation(owner_id(x_owner_id), payload.conversation_id)
        if conversation is not None:
            context = [
                {"role": item["role"], "content": item["content"]}
                for item in conversation.get("messages", [])[-20:]
                if item.get("role") in {"user", "assistant", "system"} and item.get("content")
            ]
    context.append({"role": "user", "content": prompt})

    try:
        answer = await model_adapter.chat(context, payload.model)
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"answer": answer, "conversation_id": payload.conversation_id, "model": payload.model or model_adapter.model_name, "web_search_requested": payload.webSearch, "source": "model"}


@app.get("/api/conversations")
def list_conversations(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    return {"items": repo.list_conversations(owner_id(x_owner_id))}


@app.post("/api/conversations", status_code=201)
def create_conversation(payload: ConversationCreate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    try:
        return repo.create_conversation(owner_id(x_owner_id), payload.title)
    except Exception as exc:
        logger.exception("Conversation creation failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    conversation = repo.get_conversation(owner_id(x_owner_id), conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.post("/api/conversations/{conversation_id}/messages", status_code=201)
def add_message(conversation_id: str, payload: MessageCreate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    try:
        message = repo.append_message(owner_id(x_owner_id), conversation_id, payload.role, payload.content, payload.metadata)
    except Exception as exc:
        logger.exception("Message persistence failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found; message was not saved")
    return message


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    try:
        deleted = repo.delete_conversation(owner_id(x_owner_id), conversation_id)
    except Exception as exc:
        logger.exception("Conversation deletion failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}


@app.get("/api/settings")
def get_settings(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    return repo.get_settings(owner_id(x_owner_id))


@app.patch("/api/settings")
def update_settings(payload: SettingsUpdate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    values = payload.model_dump(exclude_none=True)
    try:
        return repo.update_settings(owner_id(x_owner_id), values)
    except Exception as exc:
        logger.exception("Settings update failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api/documents")
def list_documents(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    return {"items": repo.list_documents(owner_id(x_owner_id))}


@app.post("/api/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...), x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    allowed_extensions = {".pdf", ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts"}
    filename = Path(file.filename).name
    if Path(filename).suffix.lower() not in allowed_extensions:
        raise HTTPException(status_code=415, detail="Unsupported document type")

    owner = owner_id(x_owner_id)
    base_dir = Path(os.getenv("STORAGE_DIR", "storage/uploads"))
    if not base_dir.is_absolute():
        base_dir = ROOT / base_dir
    owner_dir = base_dir / owner.replace("/", "_")
    owner_dir.mkdir(parents=True, exist_ok=True)
    storage_path = owner_dir / f"{uuid4().hex}_{filename}"
    digest = hashlib.sha256()
    size = 0
    max_bytes = 25 * 1024 * 1024

    try:
        with storage_path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail="Documents must be 25 MB or smaller")
                digest.update(chunk)
                output.write(chunk)

        document = repo.insert_document({
            "owner_id": owner,
            "filename": filename,
            "content_type": file.content_type or "application/octet-stream",
            "size_bytes": size,
            "sha256": digest.hexdigest(),
            "storage_key": str(storage_path.relative_to(ROOT)),
            "status": "uploaded",
            "processing_status": "pending",
            "created_at": now(),
            "updated_at": now(),
        })
        return document
    except HTTPException:
        storage_path.unlink(missing_ok=True)
        raise
    except Exception as exc:
        storage_path.unlink(missing_ok=True)
        logger.exception("Document metadata persistence failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc
    finally:
        await file.close()


@app.delete("/api/documents/{document_id}")
def delete_document(document_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    try:
        document = repo.delete_document(owner_id(x_owner_id), document_id)
        if document is None:
            raise HTTPException(status_code=404, detail="Document not found")
        storage_path = ROOT / str(document.get("storage_key", ""))
        if storage_path.is_file() and ROOT in storage_path.parents:
            storage_path.unlink(missing_ok=True)
        return {"deleted": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document deletion failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api")
def api_index() -> dict[str, Any]:
    return {"name": "FIREBOX AI API", "version": app.version, "docs": "/docs"}


# Safe static serving: frontend files only, never dotfiles, .env, backend code, or storage.
PUBLIC_FILES = {"index.html", "styles.css", "app.js", "firebox-ai-icon.svg", "manus-routes.json"}


@app.get("/{path:path}")
def frontend(path: str = ""):
    clean_path = path.strip("/")
    if not clean_path:
        return FileResponse(ROOT / "index.html")
    if clean_path in PUBLIC_FILES:
        return FileResponse(ROOT / clean_path)
    if clean_path.startswith("public/"):
        relative = clean_path.removeprefix("public/")
        if relative in {"firebox-ai-icon.svg", "manus-routes.json"}:
            return FileResponse(ROOT / "public" / relative)
    return FileResponse(ROOT / "index.html")
