from __future__ import annotations

import io
import os
import sys
import time
import uuid
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from threading import Lock
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field


# ---- Make `src/` importable -------------------------------------------------
# File location: <repo>/src/interface/backend/app.py
# We want to import from <repo>/src (e.g., generation.*, retrieval.*, util.*)
_THIS_FILE = Path(__file__).resolve()
SRC_DIR = _THIS_FILE.parents[2]  # .../<repo>/src
REPO_ROOT = SRC_DIR.parent       # .../<repo>
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


# ---- Import core logic ------------------------------------------------------
from generation.baseline.baseline_generator import BaselineGenerator  # noqa: E402
from generation.versionrag.versionrag_generator import VersionRAGGenerator  # noqa: E402
from indexing.baseline.baseline_indexer import BaselineIndexer  # noqa: E402
from indexing.versionrag.versionrag_indexer import VersionRAGIndexer  # noqa: E402
from retrieval.baseline.baseline_retriever import BaselineRetriever  # noqa: E402
from retrieval.versionrag.versionrag_retriever import VersionRAGRetriever  # noqa: E402
from util.constants import (  # noqa: E402
    BASELINE_MODEL,
    VERSIONRAG_MODEL,
    MILVUS_URI,
    MILVUS_TOKEN,
    MILVUS_COLLECTION_NAME_BASELINE,
    MILVUS_COLLECTION_NAME_VERSIONRAG,
)
from util.milvus_client_factory import get_milvus_client  # noqa: E402


# ---- App -------------------------------------------------------------------
app = FastAPI(title="VersionRAG-UPER Interface", version="0.1.0")

WEB_DIR = Path(__file__).resolve().parents[1] / "web"
app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")


@app.get("/")
def index() -> FileResponse:
    return FileResponse(str(WEB_DIR / "index.html"))


# ---- Models ----------------------------------------------------------------
class ChatRequest(BaseModel):
    model: str = Field(..., description="Baseline | VersionRAG")
    message: str = Field(..., min_length=1)


class ChatResponse(BaseModel):
    model: str
    answer: str
    context: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class IndexRequest(BaseModel):
    model: str = Field(..., description="Baseline | VersionRAG")


class IndexStartResponse(BaseModel):
    job_id: str
    model: str
    status: str


class JobStatusResponse(BaseModel):
    job_id: str
    model: str
    status: str  # queued | running | done | error
    progress: int = 0  # 0..100 (approximation based on processed files)
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    error: Optional[str] = None
    logs_tail: str = ""


# ---- Simple component cache -------------------------------------------------
_components_lock = Lock()
_components: Dict[str, Dict[str, Any]] = {}


def _get_components(model: str) -> Dict[str, Any]:
    """
    Lazily build retriever+generator per model so we don't reconnect on every request.
    """
    model = model.strip()
    if model not in (BASELINE_MODEL, VERSIONRAG_MODEL, "VersionRAG", "Baseline"):
        raise HTTPException(status_code=400, detail=f"Unknown model: {model}")

    # normalize to constants
    norm = BASELINE_MODEL if model.lower() == "baseline" else VERSIONRAG_MODEL

    with _components_lock:
        if norm in _components:
            return _components[norm]

        if norm == BASELINE_MODEL:
            obj = {"retriever": BaselineRetriever(), "generator": BaselineGenerator(), "indexer": BaselineIndexer()}
        else:
            obj = {"retriever": VersionRAGRetriever(), "generator": VersionRAGGenerator(), "indexer": VersionRAGIndexer()}

        _components[norm] = obj
        return obj


# ---- Helpers ----------------------------------------------------------------
def _raw_data_dir() -> str:
    # matches src/main.py logic
    return str(REPO_ROOT / "data" / "raw")


def _get_files_from_directory(directory: str) -> list[str]:
    if not os.path.exists(directory):
        raise FileNotFoundError(f"Directory not found: {directory}")
    if not os.path.isdir(directory):
        raise NotADirectoryError(f"Path is not a directory: {directory}")

    file_paths: list[str] = []
    for root, _, files in os.walk(directory):
        for file in files:
            if not file.startswith("."):
                file_paths.append(os.path.abspath(os.path.join(root, file)))
    return file_paths


def _retrieved_context_to_string(retrieved: Any) -> str:
    try:
        return str(retrieved)
    except Exception:
        return ""


def _strip_answer_prefix(text: str) -> str:
    """
    Some generators/LLMs may return a prefixed answer like:
    - "Answer: ..."
    - "Jawaban: ..."
    We remove these for a cleaner chat UI.
    """
    if not isinstance(text, str):
        return str(text)
    s = text.strip()
    for prefix in ("answer:", "answer -", "answer—", "jawaban:", "jawaban -", "jawaban—"):
        if s.lower().startswith(prefix):
            s = s[len(prefix) :].lstrip()
            break
    return s


# ---- Friendly error formatting ----------------------------------------------
def _format_chat_exception(e: Exception) -> str:
    """
    Convert common deployment misconfigurations into a readable message.
    This is especially helpful on hosted platforms where a long/hung request
    may otherwise show up as a generic 502 page.
    """
    msg = f"{type(e).__name__}: {e}"
    lower = msg.lower()

    hints: list[str] = []

    if "openai_api_key" in lower or "api key" in lower and "openai" in lower:
        hints.append("Set `OPENAI_API_KEY` (or switch `EMBEDDING_PROVIDER=local`) for embeddings.")
        hints.append("If you use Groq for chat, also set `LLM_MODE=groq` + `GROQ_API_KEY`.")

    if "groq_api_key" in lower or ("api key" in lower and "groq" in lower):
        hints.append("Set `GROQ_API_KEY` and (optionally) `GROQ_MODEL`.")

    if "neo4j_uri" in lower or "neo4j_user" in lower or "neo4j_password" in lower:
        hints.append("For VersionRAG, set `NEO4J_URI`, `NEO4J_USER`, `NEO4J_PASSWORD` (Neo4j Aura may be paused).")

    if "milvus" in lower or "zilliz" in lower:
        hints.append("Set `MILVUS_URI` (and `MILVUS_TOKEN` if using Zilliz Cloud).")
        hints.append("On Linux/Render you can use Milvus Lite (local file) with `pymilvus[... ,milvus-lite]`.")

    if "collection" in lower and "not found" in lower:
        hints.append("It looks like you haven't indexed yet. Run Indexing first, then chat again.")

    if not hints:
        return msg

    hint_text = "\n".join(f"- {h}" for h in hints)
    return f"{msg}\n\nPossible fix:\n{hint_text}"


# ---- Background indexing jobs ----------------------------------------------
_jobs_lock = Lock()
_jobs: Dict[str, Dict[str, Any]] = {}


class _JobLogBuffer(io.TextIOBase):
    def __init__(self, job_id: str) -> None:
        self.job_id = job_id
        self._lock = Lock()
        self._buf = ""

    def write(self, s: str) -> int:
        with self._lock, _jobs_lock:
            job = _jobs.get(self.job_id)
            if job is not None:
                job["logs"] += s
                # keep logs bounded
                if len(job["logs"]) > 200_000:
                    job["logs"] = job["logs"][-200_000:]

                # Update progress by parsing log lines ("Indexed:" / "Skipping:")
                self._buf += s
                if len(self._buf) > 50_000:
                    self._buf = self._buf[-50_000:]

                lines = self._buf.splitlines(keepends=False)
                if not self._buf.endswith("\n"):
                    self._buf = lines[-1] if lines else self._buf
                    lines = lines[:-1]
                else:
                    self._buf = ""

                if lines:
                    _update_job_progress_from_lines(job, lines)
        return len(s)

    def flush(self) -> None:  # pragma: no cover
        return


def _run_index_job(job_id: str, model: str) -> None:
    with _jobs_lock:
        _jobs[job_id]["status"] = "running"
        _jobs[job_id]["started_at"] = time.time()
        _jobs[job_id]["progress"] = 0

    log_buf = _JobLogBuffer(job_id)
    try:
        comps = _get_components(model)
        indexer = comps["indexer"]
        files = _get_files_from_directory(_raw_data_dir())
        with _jobs_lock:
            _jobs[job_id]["total_files"] = len(files)
            _jobs[job_id]["done_files"] = 0
            _jobs[job_id]["started_files"] = 0
            _jobs[job_id]["progress"] = 0

        with redirect_stdout(log_buf), redirect_stderr(log_buf):
            indexer.index_data(files)

        with _jobs_lock:
            _jobs[job_id]["status"] = "done"
            _jobs[job_id]["finished_at"] = time.time()
            _jobs[job_id]["progress"] = 100
    except Exception as e:
        with _jobs_lock:
            _jobs[job_id]["status"] = "error"
            _jobs[job_id]["finished_at"] = time.time()
            _jobs[job_id]["error"] = f"{type(e).__name__}: {e}"


def _update_job_progress_from_lines(job: Dict[str, Any], lines: list[str]) -> None:
    """
    Approximate progress:
    - Count completed files by matching typical BaseIndexer logs:
      - "Indexed:" (file finished indexing)
      - "Skipping:" (file already indexed)
      - "Indexing:" (file started indexing)
    """
    total = int(job.get("total_files") or 0)
    done = int(job.get("done_files") or 0)
    started = int(job.get("started_files") or 0)

    inc_done = 0
    inc_started = 0
    for ln in lines:
        # Start signal: BaseIndexer.index_file prints "Indexing: <file>"
        if ln.strip().startswith("Indexing:"):
            inc_started += 1
        # Done signals
        if "Indexed:" in ln or "Skipping:" in ln:
            inc_done += 1

    if inc_started:
        started = min(total, started + inc_started) if total else started + inc_started
        job["started_files"] = started

    if inc_done:
        done = min(total, done + inc_done) if total else done + inc_done
        job["done_files"] = done

    if total > 0:
        # Give progress movement as soon as a file starts.
        # Each file contributes 2 "ticks": start + done.
        in_progress = max(0, started - done)
        # In normal flow, at most 1 file in progress, but clamp anyway.
        in_progress = min(in_progress, 1)
        ticks_done = done * 2 + in_progress
        pct = int(round((ticks_done / (total * 2)) * 100))
        if job.get("status") == "running":
            pct = min(pct, 99)
        job["progress"] = max(0, min(100, pct))


def _start_thread(target, *args) -> None:
    import threading

    t = threading.Thread(target=target, args=args, daemon=True)
    t.start()


# ---- API -------------------------------------------------------------------
@app.get("/api/models")
def models() -> Dict[str, Any]:
    return {"models": [BASELINE_MODEL, VERSIONRAG_MODEL]}

@app.get("/api/health")
def health() -> Dict[str, Any]:
    """
    Lightweight health check for the web backend + Milvus connectivity.
    (Neo4j is exercised indirectly when user chooses VersionRAG chat/index.)
    """
    milvus_ok = False
    collections: list[str] = []
    error: str | None = None
    try:
        client = get_milvus_client()
        collections = client.list_collections()
        milvus_ok = True
    except Exception as e:
        error = f"{type(e).__name__}: {e}"

    return {
        "ok": True,
        "milvus": {
            "ok": milvus_ok,
            "uri": MILVUS_URI,
            "token_configured": bool(MILVUS_TOKEN),
            "collections": collections,
            "has_baseline_collection": MILVUS_COLLECTION_NAME_BASELINE in collections,
            "has_versionrag_collection": MILVUS_COLLECTION_NAME_VERSIONRAG in collections,
            "error": error,
        },
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    try:
        comps = _get_components(req.model)
        retriever = comps["retriever"]
        generator = comps["generator"]

        retrieved = retriever.retrieve(req.message)
        response = generator.generate(retrieved, req.message)
        answer_text = getattr(response, "answer", None)
        if not isinstance(answer_text, str) or not answer_text.strip():
            answer_text = str(response)
        answer_text = _strip_answer_prefix(answer_text)

        return ChatResponse(
            model=req.model if req.model in (BASELINE_MODEL, VERSIONRAG_MODEL) else (BASELINE_MODEL if req.model.lower() == "baseline" else VERSIONRAG_MODEL),
            answer=answer_text,
            context=_retrieved_context_to_string(retrieved),
            meta={},
        )
    except HTTPException:
        raise
    except Exception as e:
        # Convert to a readable error and use 503 to signal "dependency/config not ready".
        raise HTTPException(status_code=503, detail=_format_chat_exception(e))


@app.post("/api/index", response_model=IndexStartResponse)
def start_index(req: IndexRequest) -> IndexStartResponse:
    model = req.model.strip()
    if model.lower() not in ("baseline", "versionrag"):
        raise HTTPException(status_code=400, detail="model must be Baseline or VersionRAG")

    # Pre-check Milvus so user gets an immediate, readable error (instead of waiting for background logs).
    try:
        _ = get_milvus_client().list_collections()
    except Exception as e:
        raise HTTPException(
            status_code=503,
            detail=f"Milvus is not reachable at {MILVUS_URI}. Error: {type(e).__name__}: {e}",
        )

    job_id = uuid.uuid4().hex
    with _jobs_lock:
        _jobs[job_id] = {
            "job_id": job_id,
            "model": "Baseline" if model.lower() == "baseline" else "VersionRAG",
            "status": "queued",
            "started_at": None,
            "finished_at": None,
            "error": None,
            "logs": "",
        }

    _start_thread(_run_index_job, job_id, model)
    return IndexStartResponse(job_id=job_id, model=_jobs[job_id]["model"], status=_jobs[job_id]["status"])


@app.get("/api/index/{job_id}", response_model=JobStatusResponse)
def index_status(job_id: str) -> JobStatusResponse:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="job_id not found")
        logs = job.get("logs", "")

        return JobStatusResponse(
            job_id=job["job_id"],
            model=job["model"],
            status=job["status"],
            progress=int(job.get("progress") or 0),
            started_at=job["started_at"],
            finished_at=job["finished_at"],
            error=job["error"],
            logs_tail=logs[-4000:],
        )


# ---- Run local --------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    # Railway (and most PaaS) injects the listening port via $PORT.
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host="0.0.0.0", port=port)


