_REPO_ROOT = Path(__file__).resolve().parents[2]
_DATA_DB_DIR = _REPO_ROOT / "data" / "db"
_DATA_DB_DIR.mkdir(parents=True, exist_ok=True)

KNOWLEDGE_GRAPH_PATH = str(_DATA_DB_DIR / "knowledge_graph_index.pkl")