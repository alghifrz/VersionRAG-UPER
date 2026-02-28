import argparse
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ensure `src/` is on sys.path so imports like `from util...` work even when run from repo root.
_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from util.constants import (
    MILVUS_URI,
    MILVUS_COLLECTION_NAME_BASELINE,
    MILVUS_COLLECTION_NAME_VERSIONRAG,
)
from util.milvus_client_factory import get_milvus_client


def _load_env() -> None:
    # Load from src/.env if present, otherwise fallback to default behavior.
    src_dir = Path(__file__).resolve().parents[1]
    env_path = src_dir / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path)
    else:
        load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser(description="Reset Milvus collections used by this repo.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Drop ALL collections in the connected Milvus instance (dangerous).",
    )
    args = parser.parse_args()

    _load_env()

    client = get_milvus_client()
    print(f"Connected to Milvus: {MILVUS_URI}")

    if args.all:
        names = client.list_collections()
    else:
        names = [MILVUS_COLLECTION_NAME_BASELINE, MILVUS_COLLECTION_NAME_VERSIONRAG]

    for name in names:
        if client.has_collection(collection_name=name):
            client.drop_collection(collection_name=name)
            print(f"Dropped collection: {name}")
        else:
            print(f"Collection not found (skip): {name}")

    print("✅ Milvus reset done")


if __name__ == "__main__":
    main()


