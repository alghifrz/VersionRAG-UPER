from pathlib import Path
import os
import sys
from dotenv import load_dotenv

# Load env as early as possible so constants can depend on .env values.
_SRC_DIR = Path(__file__).resolve().parents[1]  # .../src
_ENV_PATH = _SRC_DIR / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()

# Resolve paths relative to the repository root (works regardless of current working directory)
_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DB_DIR = _REPO_ROOT / "data" / "db"
_DATA_DB_DIR.mkdir(parents=True, exist_ok=True)

KNOWLEDGE_GRAPH_PATH = str(_DATA_DB_DIR / "knowledge_graph_index.pkl")

# Milvus connection:
# - On Linux/macOS you *can* use Milvus Lite with a local db file (pymilvus extra `milvus-lite`).
# - On Windows, pymilvus explicitly does NOT support Milvus Lite (see pymilvus metadata marker `sys_platform != "win32"`),
#   so you must run a Milvus server (e.g., Docker) and connect via URI.
#
# You can always override with env var `MILVUS_URI`.
MILVUS_DB_PATH = str(_DATA_DB_DIR / "milvus.db")  # kept for backward-compat / non-Windows
MILVUS_URI = os.getenv("MILVUS_URI")
if not MILVUS_URI:
    MILVUS_URI = "http://localhost:19530" if sys.platform == "win32" else MILVUS_DB_PATH
MILVUS_TOKEN = os.getenv("MILVUS_TOKEN", "").strip()
MILVUS_COLLECTION_NAME_BASELINE = "baseline_collection"
MILVUS_COLLECTION_NAME_VERSIONRAG = "VersionRAG_collection"
MILVUS_MAX_TOKEN_COUNT = 512 # Maximum tokens per chunk
MILVUS_META_ATTRIBUTE_TEXT = "text"
MILVUS_META_ATTRIBUTE_PAGE = "page"
MILVUS_META_ATTRIBUTE_FILE = "file"
MILVUS_META_ATTRIBUTE_CATEGORY = "category"
MILVUS_META_ATTRIBUTE_DOCUMENTATION = "documentation"
MILVUS_META_ATTRIBUTE_VERSION = "version"
MILVUS_META_ATTRIBUTE_TYPE = "type" # file / node
MILVUS_BASELINE_SOURCE_COUNT = 15
LLM_MODE = os.getenv("LLM_MODE", "openai")  # openai / groq / offline
LLM_OFFLINE_MODEL = os.getenv("LLM_OFFLINE_MODEL", "")  # local llm model (offline mode)

# Embeddings
# - openai: requires OPENAI_API_KEY
# - local: uses sentence-transformers (free)
EMBEDDING_PROVIDER = os.getenv("EMBEDDING_PROVIDER", "openai")  # openai / local

if EMBEDDING_PROVIDER == "local":
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "384"))
else:
    EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
    EMBEDDING_DIMENSIONS = int(os.getenv("EMBEDDING_DIMENSIONS", "512"))

BASELINE_MODEL = "Baseline"
KG_MODEL = "GraphRAG"
VERSIONRAG_MODEL = "VersionRAG"
AVAILABLE_MODELS = [BASELINE_MODEL, KG_MODEL, VERSIONRAG_MODEL]