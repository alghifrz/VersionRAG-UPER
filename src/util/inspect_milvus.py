"""
Lihat data yang sudah tersimpan di Milvus: daftar collection + sample isi.
Jalankan dari folder src: python util/inspect_milvus.py
Atau dari repo root: python src/util/inspect_milvus.py
"""
import sys
from pathlib import Path

from dotenv import load_dotenv

_SRC_DIR = Path(__file__).resolve().parents[1]
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))

from util.constants import (
    MILVUS_URI,
    MILVUS_COLLECTION_NAME_BASELINE,
    MILVUS_COLLECTION_NAME_VERSIONRAG,
    MILVUS_META_ATTRIBUTE_TEXT,
    MILVUS_META_ATTRIBUTE_PAGE,
    MILVUS_META_ATTRIBUTE_FILE,
    MILVUS_META_ATTRIBUTE_CATEGORY,
    MILVUS_META_ATTRIBUTE_DOCUMENTATION,
    MILVUS_META_ATTRIBUTE_VERSION,
    MILVUS_META_ATTRIBUTE_TYPE,
)
from util.milvus_client_factory import get_milvus_client

# Load .env from src/
_ENV_PATH = _SRC_DIR / ".env"
if _ENV_PATH.exists():
    load_dotenv(dotenv_path=_ENV_PATH)
else:
    load_dotenv()

# Fields to show per collection type
BASELINE_FIELDS = ["id", MILVUS_META_ATTRIBUTE_TEXT, MILVUS_META_ATTRIBUTE_PAGE, MILVUS_META_ATTRIBUTE_FILE]
VERSIONRAG_FIELDS = [
    "id",
    MILVUS_META_ATTRIBUTE_TEXT,
    MILVUS_META_ATTRIBUTE_PAGE,
    MILVUS_META_ATTRIBUTE_FILE,
    MILVUS_META_ATTRIBUTE_CATEGORY,
    MILVUS_META_ATTRIBUTE_DOCUMENTATION,
    MILVUS_META_ATTRIBUTE_VERSION,
    MILVUS_META_ATTRIBUTE_TYPE,
]

TEXT_MAX = 120  # truncate text preview
SAMPLE_LIMIT = 20


def _truncate(s: str, max_len: int = TEXT_MAX) -> str:
    if not s or not isinstance(s, str):
        return str(s)
    s = s.replace("\n", " ")
    return (s[: max_len] + "…") if len(s) > max_len else s


def _show_collection(client, collection_name: str, output_fields: list, limit: int = SAMPLE_LIMIT):
    """Query collection and print sample rows."""
    try:
        # filter empty string = no filter, get first `limit` entities
        rows = client.query(
            collection_name=collection_name,
            filter="",
            output_fields=output_fields,
            limit=limit,
        )
    except Exception as e:
        print(f"  Error querying: {e}")
        return

    if not rows:
        print("  (kosong)")
        return

    print(f"  Total sample: {len(rows)} baris\n")
    for i, row in enumerate(rows, 1):
        print(f"  --- Baris {i} ---")
        for key in output_fields:
            val = row.get(key)
            if key == MILVUS_META_ATTRIBUTE_TEXT:
                val = _truncate(val)
            print(f"    {key}: {val}")
        print()


def main():
    client = get_milvus_client()
    print(f"Milvus URI: {MILVUS_URI}\n")

    collections = client.list_collections()
    if not collections:
        print("Tidak ada collection di server ini.")
        return

    print("Daftar collection:", collections)
    print()

    for name in [MILVUS_COLLECTION_NAME_BASELINE, MILVUS_COLLECTION_NAME_VERSIONRAG]:
        if name not in collections:
            continue
        print("=" * 60)
        print(f"Collection: {name}")
        print("=" * 60)
        if name == MILVUS_COLLECTION_NAME_BASELINE:
            _show_collection(client, name, BASELINE_FIELDS)
        else:
            _show_collection(client, name, VERSIONRAG_FIELDS)

    # Show any other collections (no schema assumption)
    others = [c for c in collections if c not in (MILVUS_COLLECTION_NAME_BASELINE, MILVUS_COLLECTION_NAME_VERSIONRAG)]
    if others:
        print("=" * 60)
        print("Collection lain (sample dengan output_fields=['*']):")
        for name in others:
            print(f"\n  {name}:")
            _show_collection(client, name, ["*"], limit=5)

    print("Selesai.")


if __name__ == "__main__":
    main()



