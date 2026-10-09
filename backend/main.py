"""FIREBOX AI API with MongoDB persistence and real provider-backed answers."""
from __future__ import annotations

import hashlib
import base64
import hmac
import logging
import os
import re
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from bson import ObjectId
from dotenv import load_dotenv
from fastapi import FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field
from pymongo.errors import PyMongoError
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from .db import MongoStore, mongo_error_message
from .model_adapter import FireboxModelAdapter, ModelUnavailable
from .repositories import Repositories
from .schemas import ConversationCreate, MessageCreate, SettingsUpdate
from .teacher_supervisor import GroqTeacher

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
logger = logging.getLogger("firebox.api")
store = MongoStore.from_environment()
repositories = Repositories(store)
model_adapter = FireboxModelAdapter()
teacher = GroqTeacher()
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
ALLOWED_EXTENSIONS = {".pdf", ".txt", ".md", ".csv", ".json", ".py", ".js", ".ts"}


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.connect()
    yield
    store.close()


app = FastAPI(title="FIREBOX AI API", version="0.2.0", lifespan=lifespan)
origins = [item.strip() for item in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",") if item.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=False, allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type"])


@app.middleware("http")
async def protect_workspace(request, call_next):
    """Keep single-owner data private until a full identity system is added."""
    if request.url.path == "/api/health" or request.method == "OPTIONS":
        return await call_next(request)
    expected_user = os.getenv("APP_USERNAME", "").strip()
    expected_password = os.getenv("APP_PASSWORD", "")
    if not expected_user or not expected_password:
        return JSONResponse(status_code=503, content={"detail": "Workspace access is disabled until APP_USERNAME and APP_PASSWORD are configured on the server."})
    auth = request.headers.get("authorization", "")
    scheme, _, encoded = auth.partition(" ")
    try:
        decoded = base64.b64decode(encoded, validate=True).decode("utf-8") if scheme.lower() == "basic" else ""
    except (ValueError, UnicodeDecodeError):
        decoded = ""
    supplied_user, separator, supplied_password = decoded.partition(":")
    if not separator or not (hmac.compare_digest(supplied_user, expected_user) and hmac.compare_digest(supplied_password, expected_password)):
        return JSONResponse(status_code=401, content={"detail": "Authentication required"}, headers={"WWW-Authenticate": 'Basic realm="FIREBOX AI", charset="UTF-8"'})
    return await call_next(request)


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
    message: str = Field(min_length=1, max_length=100_000)
    model: str | None = None
    webSearch: bool = False
    conversation_id: str | None = None
    document_ids: list[str] = Field(default_factory=list, max_length=50)


class FeedbackRequest(BaseModel):
    prompt: str = Field(min_length=1, max_length=100_000)
    response: str = Field(min_length=1, max_length=100_000)
    rating: str = Field(pattern="^(good|incorrect|needs_detail|unsafe|good_code|bad_code|citation_correct|citation_incorrect)$")
    correction: str = Field(default="", max_length=100_000)
    source_ids: list[str] = Field(default_factory=list, max_length=50)


class LessonRequest(BaseModel):
    topic: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=20_000)
    expected_answer: str = Field(min_length=1, max_length=50_000)
    explanation: str = Field(default="", max_length=50_000)
    difficulty: str = Field(default="beginner", max_length=40)


class KnowledgeRequest(BaseModel):
    subject: str = Field(min_length=1, max_length=200)
    fact: str = Field(min_length=1, max_length=20_000)
    source: str = Field(default="owner", max_length=500)


class ToolRequest(BaseModel):
    tool: str = Field(pattern="^(python_syntax|json_validate|calculator)$")
    input: str = Field(min_length=1, max_length=20_000)


def owner_id(_: str | None = None) -> str:
    """Single-workspace owner. Client-supplied owner IDs are deliberately ignored."""
    return os.getenv("FIREBOX_OWNER_ID", "local-owner").strip()[:120] or "local-owner"


def require_database() -> Repositories:
    if not store.connected:
        raise HTTPException(status_code=503, detail=mongo_error_message(RuntimeError("MongoDB is unavailable; the operation was not completed")))
    return repositories


def now() -> datetime:
    return datetime.now(timezone.utc)


def safe_storage_root() -> Path:
    value = Path(os.getenv("STORAGE_DIR", "storage/uploads"))
    return value if value.is_absolute() else ROOT / value


def extract_document(path: Path, extension: str) -> list[dict[str, Any]]:
    """Extract text with page metadata where available; fail rather than fake success."""
    pages: list[dict[str, Any]] = []
    if extension == ".pdf":
        reader = PdfReader(str(path))
        if reader.is_encrypted:
            try:
                if reader.decrypt("") == 0:
                    raise ValueError("Encrypted PDFs are not supported")
            except Exception as exc:
                raise ValueError("Encrypted PDFs are not supported") from exc
        for index, page in enumerate(reader.pages, start=1):
            text = (page.extract_text() or "").strip()
            if text:
                pages.append({"page": index, "text": text})
    else:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
        if text:
            pages.append({"page": None, "text": text})
    if not pages:
        raise ValueError("No extractable text was found in this document")
    return pages


def chunk_pages(pages: list[dict[str, Any]], size: int = 1400, overlap: int = 180) -> list[dict[str, Any]]:
    chunks: list[dict[str, Any]] = []
    for page in pages:
        text = page["text"]
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            snippet = text[start:end].strip()
            if snippet:
                chunks.append({"text": snippet, "page": page["page"]})
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks


def retrieve_chunks(repo: Repositories, owner: str, query: str, document_ids: list[str]) -> list[dict[str, Any]]:
    terms = {term for term in re.findall(r"[\w'-]{3,}", query.lower())}
    if not terms:
        return []
    selector: dict[str, Any] = {"owner_id": owner}
    if document_ids:
        selector["document_id"] = {"$in": document_ids}
    candidates = list(store.collection("document_chunks").find(selector).limit(2000))
    scored = []
    for chunk in candidates:
        text = str(chunk.get("text", ""))
        words = set(re.findall(r"[\w'-]{3,}", text.lower()))
        score = len(terms & words) / max(1, len(terms))
        if score > 0:
            scored.append((score, chunk))
    scored.sort(key=lambda pair: pair[0], reverse=True)
    results = []
    for score, chunk in scored[:5]:
        if not ObjectId.is_valid(str(chunk.get("document_id", ""))):
            continue
        document = store.collection("documents").find_one({"_id": ObjectId(chunk["document_id"]), "owner_id": owner})
        if document:
            results.append({"type": "document", "title": document.get("filename", "Document"), "document_id": chunk["document_id"], "page": chunk.get("page"), "snippet": chunk["text"], "score": round(score, 3)})
    return results


def answer_is_unusable(answer: str, query: str, sources: list[dict[str, Any]]) -> bool:
    """Detect obvious tiny-model output failures before returning an answer."""
    words = re.findall(r"[a-zA-Z0-9']+", answer.lower())
    if len(words) < 8:
        return True
    if len(set(words)) / len(words) < 0.55:
        return True
    query_terms = set(re.findall(r"[a-zA-Z0-9']{3,}", query.lower()))
    answer_terms = set(words)
    source_terms = set(re.findall(r"[a-zA-Z0-9']{3,}", " ".join(str(item.get("snippet", "")) for item in sources).lower()))
    if query_terms and not (query_terms & answer_terms) and not (answer_terms & source_terms):
        return True
    return any(marker in answer.lower() for marker in ("context:", "instruction:", "response:"))


def extractive_answer(sources: list[dict[str, Any]]) -> str:
    """Return retrieved evidence directly when the tiny model cannot explain it."""
    source = sources[0]
    return f"Here is the relevant information from the uploaded knowledge:\n\n{source['snippet']}"


async def search_web(query: str) -> list[dict[str, str]]:
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise HTTPException(status_code=503, detail="Web search is unavailable: configure TAVILY_API_KEY on the server")
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post("https://api.tavily.com/search", json={"api_key": api_key, "query": query, "search_depth": "basic", "max_results": 5, "include_answer": False})
            response.raise_for_status()
            data = response.json()
    except (httpx.HTTPError, ValueError) as exc:
        logger.warning("Web search provider failed: %s", exc.__class__.__name__)
        raise HTTPException(status_code=503, detail="The web-search provider could not complete this request") from exc
    results = []
    for item in data.get("results", []):
        url = item.get("url")
        title = item.get("title")
        if isinstance(url, str) and url.startswith(("https://", "http://")) and isinstance(title, str):
            results.append({"type": "web", "title": title[:300], "url": url, "snippet": str(item.get("content", ""))[:3000]})
    if not results:
        raise HTTPException(status_code=404, detail="The web-search provider returned no results")
    return results


@app.get("/api/health", response_model=HealthResponse)
def health() -> HealthResponse:
    storage_dir = safe_storage_root()
    model_status = model_adapter.status()
    ready = store.connected and bool(model_status.get("configured"))
    return HealthResponse(status="ready" if ready else "degraded", mongodb=store.status(), storage={"available": storage_dir.exists() and storage_dir.is_dir(), "configured": bool(os.getenv("STORAGE_DIR"))}, model=model_status)


@app.post("/api/chat")
async def chat(payload: ChatRequest, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    prompt = payload.message.strip()
    if not prompt:
        raise HTTPException(status_code=422, detail="Message cannot be empty")
    owner = owner_id(x_owner_id)
    context: list[dict[str, str]] = []
    if payload.conversation_id:
        conversation = repo.get_conversation(owner, payload.conversation_id)
        if conversation is None:
            raise HTTPException(status_code=404, detail="Conversation not found")
        history = conversation.get("messages", [])[-20:]
        context = [{"role": m["role"], "content": m["content"]} for m in history if m.get("role") in {"user", "assistant", "system"} and m.get("content")]
        if not context or context[-1]["role"] != "user" or context[-1]["content"] != prompt:
            context.append({"role": "user", "content": prompt})
    else:
        context = [{"role": "user", "content": prompt}]

    sources: list[dict[str, Any]] = []
    evidence = ""
    teacher_review_id: str | None = None
    try:
        sources.extend(retrieve_chunks(repo, owner, prompt, payload.document_ids))
        if payload.webSearch:
            sources.extend(await search_web(prompt))
        if sources:
            blocks = []
            for index, source in enumerate(sources, start=1):
                label = f"[S{index}] {source['title']}" + (f", page {source['page']}" if source.get("page") else "")
                blocks.append(f"{label}\n{source['snippet']}")
            evidence = "\n\n".join(blocks)
            context.insert(0, {"role": "system", "content": "Use the supplied evidence when relevant, but do not mention source labels, filenames, page numbers, or extracted snippets in the customer-facing answer. Do not claim facts not supported by the context. When a workflow, architecture, comparison, or set of components would genuinely benefit from visual UI, you may emit a card rail using exactly this format:\n:::cards\nTitle | Short description\nAnother title | Short description\n:::\nUse 3 to 8 cards only when they improve understanding; do not use cards for ordinary answers.\n\nEvidence:\n" + evidence})
        else:
            context.insert(0, {"role": "system", "content": "When a workflow, architecture, comparison, or set of components would genuinely benefit from visual UI, you may emit a card rail using exactly this format:\n:::cards\nTitle | Short description\nAnother title | Short description\n:::\nUse 3 to 8 cards only when they improve understanding; do not use cards for ordinary answers."})
        answer = await model_adapter.chat(context, payload.model)
        if sources and answer_is_unusable(answer, prompt, sources):
            answer = extractive_answer(sources)
        if teacher.configured:
            supervised = await teacher.review(prompt, answer, sources)
            if supervised:
                draft = answer
                answer = supervised
                review = repo.insert_training_record("teacher_reviews", owner, {
                    "prompt": prompt,
                    "context": evidence,
                    "draft": draft,
                    "response": supervised,
                    "sources": sources,
                    "approved": False,
                    "teacher_model": teacher.model,
                })
                teacher_review_id = review.get("id")
    except ModelUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {"answer": answer, "conversation_id": payload.conversation_id, "model": payload.model or model_adapter.model_name, "sources": sources, "teacher_used": teacher_review_id is not None, "teacher_review_id": teacher_review_id}


@app.get("/api/conversations")
def list_conversations(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_conversations(owner_id(x_owner_id))}


@app.post("/api/conversations", status_code=201)
def create_conversation(payload: ConversationCreate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return require_database().create_conversation(owner_id(x_owner_id), payload.title)
    except Exception as exc:
        logger.exception("Conversation creation failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api/conversations/{conversation_id}")
def get_conversation(conversation_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    conversation = require_database().get_conversation(owner_id(x_owner_id), conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.patch("/api/conversations/{conversation_id}")
def rename_conversation(conversation_id: str, payload: ConversationCreate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    result = require_database().rename_conversation(owner_id(x_owner_id), conversation_id, payload.title)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return result


@app.post("/api/conversations/{conversation_id}/messages", status_code=201)
def add_message(conversation_id: str, payload: MessageCreate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        message = require_database().append_message(owner_id(x_owner_id), conversation_id, payload.role, payload.content, payload.metadata)
    except Exception as exc:
        logger.exception("Message persistence failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc
    if message is None:
        raise HTTPException(status_code=404, detail="Conversation not found; message was not saved")
    return message


@app.delete("/api/conversations/{conversation_id}")
def delete_conversation(conversation_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    if not require_database().delete_conversation(owner_id(x_owner_id), conversation_id):
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"deleted": True, "conversation_id": conversation_id}


@app.get("/api/settings")
def get_settings(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return require_database().get_settings(owner_id(x_owner_id))


@app.patch("/api/settings")
def update_settings(payload: SettingsUpdate, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    try:
        return require_database().update_settings(owner_id(x_owner_id), payload.model_dump(exclude_none=True))
    except Exception as exc:
        logger.exception("Settings update failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api/documents")
def list_documents(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_documents(owner_id(x_owner_id))}


@app.post("/api/documents/upload", status_code=201)
async def upload_document(file: UploadFile = File(...), x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    if not file.filename:
        raise HTTPException(status_code=400, detail="A filename is required")
    filename = Path(file.filename).name
    extension = Path(filename).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail="Unsupported document type")
    owner = owner_id(x_owner_id)
    safe_owner = re.sub(r"[^A-Za-z0-9_.-]", "_", owner)[:120]
    owner_dir = safe_storage_root() / safe_owner
    owner_dir.mkdir(parents=True, exist_ok=True)
    path = owner_dir / f"{uuid4().hex}_{filename}"
    digest = hashlib.sha256()
    size = 0
    document: dict[str, Any] | None = None
    try:
        with path.open("wb") as output:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > MAX_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="Documents must be 25 MB or smaller")
                digest.update(chunk)
                output.write(chunk)
        if extension == ".pdf" and not path.read_bytes()[:5] == b"%PDF-":
            raise HTTPException(status_code=415, detail="The uploaded file is not a valid PDF")
        extracted = extract_document(path, extension)
        chunks = chunk_pages(extracted)
        document = repo.insert_document({"owner_id": owner, "filename": filename, "content_type": file.content_type or "application/octet-stream", "size_bytes": size, "sha256": digest.hexdigest(), "storage_key": str(path.resolve()), "status": "processing", "processing_status": "processing", "chunk_count": 0, "created_at": now(), "updated_at": now()})
        for index, chunk in enumerate(chunks):
            store.collection("document_chunks").insert_one({"owner_id": owner, "document_id": document["id"], "chunk_index": index, "page": chunk["page"], "text": chunk["text"], "created_at": now()})
        result = store.collection("documents").update_one({"_id": ObjectId(document["id"]), "owner_id": owner}, {"$set": {"status": "completed", "processing_status": "completed", "chunk_count": len(chunks), "updated_at": now()}})
        if result.matched_count != 1:
            raise RuntimeError("Document record disappeared before indexing completed")
        document.update({"status": "completed", "processing_status": "completed", "chunk_count": len(chunks)})
        document.pop("storage_key", None)
        return document
    except HTTPException:
        path.unlink(missing_ok=True)
        raise
    except (ValueError, OSError, PdfReadError) as exc:
        path.unlink(missing_ok=True)
        raise HTTPException(status_code=422, detail=f"Document processing failed: {exc}") from exc
    except Exception as exc:
        path.unlink(missing_ok=True)
        if document is not None:
            try:
                repo.delete_document(owner, document["id"])
            except Exception:
                logger.exception("Could not remove a partially indexed document")
        logger.exception("Document processing or persistence failed")
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
        storage_value = Path(str(document.get("storage_key", "")))
        path = storage_value if storage_value.is_absolute() else ROOT / storage_value
        if path.is_file() and (ROOT in path.parents or safe_storage_root() in path.parents):
            path.unlink(missing_ok=True)
        return {"deleted": True, "document_id": document_id}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Document deletion failed")
        raise HTTPException(status_code=503, detail=mongo_error_message(exc)) from exc


@app.get("/api/learning/status")
def learning_status() -> dict[str, Any]:
    return {"model": model_adapter.status(), "database": store.status(), "teacher": teacher.status(), "external_models": teacher.configured}


@app.get("/api/learning/feedback")
def list_feedback(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_training_records("training_feedback", owner_id(x_owner_id))}


@app.get("/api/learning/teacher-reviews")
def list_teacher_reviews(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_teacher_reviews(owner_id(x_owner_id))}


@app.post("/api/learning/teacher-reviews/{review_id}/approve")
def approve_teacher_review(review_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    if not require_database().approve_teacher_review(owner_id(x_owner_id), review_id):
        raise HTTPException(status_code=404, detail="Teacher review not found")
    return {"approved": True, "id": review_id}


@app.get("/api/learning/teacher-dataset")
def teacher_dataset(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    """Return only owner-approved examples in train_firebox.py JSONL shape."""
    items = require_database().approved_teacher_dataset(owner_id(x_owner_id))
    return {"items": items, "count": len(items)}


@app.post("/api/learning/feedback", status_code=201)
def add_feedback(payload: FeedbackRequest, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return require_database().insert_training_record("training_feedback", owner_id(x_owner_id), payload.model_dump())


@app.get("/api/learning/lessons")
def list_lessons(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_training_records("training_lessons", owner_id(x_owner_id))}


@app.post("/api/learning/lessons", status_code=201)
def add_lesson(payload: LessonRequest, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return require_database().insert_training_record("training_lessons", owner_id(x_owner_id), payload.model_dump())


@app.get("/api/learning/knowledge")
def list_knowledge(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return {"items": require_database().list_training_records("knowledge_items", owner_id(x_owner_id))}


@app.post("/api/learning/knowledge", status_code=201)
def add_knowledge(payload: KnowledgeRequest, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    return require_database().add_knowledge_item(owner_id(x_owner_id), payload.model_dump())


@app.post("/api/learning/knowledge/{item_id}/approve")
def approve_knowledge(item_id: str, x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    if not require_database().approve_knowledge_item(owner_id(x_owner_id), item_id):
        raise HTTPException(status_code=404, detail="Knowledge item not found")
    return {"approved": True, "id": item_id}


@app.get("/api/learning/runs")
def list_training_runs(x_owner_id: str | None = Header(default=None)) -> dict[str, Any]:
    repo = require_database()
    runs = repo.list_training_records("training_runs", owner_id(x_owner_id))
    for run in runs:
        run["metrics"] = repo.list_training_records("training_metrics", owner_id(x_owner_id))
        run["metrics"] = [metric for metric in run["metrics"] if metric.get("run_id") == run["id"]]
    return {"items": runs}


@app.post("/api/tools/verify")
def verify_tool(payload: ToolRequest) -> dict[str, Any]:
    """Run only bounded, non-executing local checks; never execute user code."""
    import ast
    import json
    import operator

    if payload.tool == "python_syntax":
        try:
            ast.parse(payload.input)
            return {"valid": True, "message": "Python syntax is valid. No code was executed."}
        except SyntaxError as exc:
            return {"valid": False, "message": f"Syntax error on line {exc.lineno}: {exc.msg}"}
    if payload.tool == "json_validate":
        try:
            json.loads(payload.input)
            return {"valid": True, "message": "JSON is valid."}
        except json.JSONDecodeError as exc:
            return {"valid": False, "message": f"JSON error at character {exc.pos}: {exc.msg}"}
    try:
        allowed = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.Pow: operator.pow, ast.USub: operator.neg}
        tree = ast.parse(payload.input, mode="eval")
        def calculate(node):
            if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
                return node.value
            if isinstance(node, ast.UnaryOp) and type(node.op) in allowed:
                return allowed[type(node.op)](calculate(node.operand))
            if isinstance(node, ast.BinOp) and type(node.op) in allowed:
                left, right = calculate(node.left), calculate(node.right)
                if type(node.op) is ast.Pow and abs(right) > 12:
                    raise ValueError("Exponent is too large")
                return allowed[type(node.op)](left, right)
            raise ValueError("Only numbers and basic arithmetic are allowed")
        result = calculate(tree.body)
        if abs(result) > 10**12:
            raise ValueError("Result is too large")
        return {"valid": True, "result": result, "message": "Calculated locally."}
    except (ValueError, ZeroDivisionError, SyntaxError) as exc:
        return {"valid": False, "message": str(exc)}


@app.get("/api")
def api_index() -> dict[str, Any]:
    return {"name": "FIREBOX AI API", "version": app.version, "docs": "/docs"}


@app.get("/chat", include_in_schema=False)
@app.get("/chat/", include_in_schema=False)
def user_chat() -> FileResponse:
    """Customer-facing chat page; the training dashboard remains at /."""
    return FileResponse(ROOT / "chat.html")


PUBLIC_FILES = {"index.html", "styles.css", "app.js", "chat.css", "chat.js", "firebox-ai-icon.svg", "manus-routes.json"}


@app.get("/{path:path}")
def frontend(path: str = ""):
    clean_path = path.strip("/")
    if not clean_path:
        return FileResponse(ROOT / "index.html")
    if clean_path in PUBLIC_FILES:
        return FileResponse(ROOT / clean_path)
    if clean_path.startswith("public/") and clean_path.removeprefix("public/") in {"firebox-ai-icon.svg", "manus-routes.json"}:
        return FileResponse(ROOT / "public" / clean_path.removeprefix("public/"))
    return FileResponse(ROOT / "index.html")
