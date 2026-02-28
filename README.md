# LexUP — Universitas Pertamina Legal & Regulation Assistant (VersionRAG)

Project ini adalah **RAG (Retrieval-Augmented Generation)** untuk membantu tanya-jawab dokumen (PDF/MD) dengan 2 mode:
- **Baseline**: vector search (Milvus) → LLM jawab berdasarkan context.
- **VersionRAG**: **Neo4j graph (versi + relasi + changes)** + Milvus vector search → LLM jawab versi-aware.

Folder dokumen input ada di: `data/raw/`

---

## Fitur utama

- **Indexing dokumen** (PDF/MD) ke Milvus (Baseline & VersionRAG).
- **Version-aware graph** (VersionRAG) di Neo4j:
  - `Category → Documentation → Version → Content`
  - `NEXT_VERSION` untuk chain antar versi
  - `Change` dari changelog dan/atau diff antar versi
- **Retrieval**:
  - Baseline: Top-K chunk dari Milvus
  - VersionRAG: parser LLM memilih mode (Version/Change/Content) + filter metadata (category/doc/version)
- **Web UI** mirip ChatGPT:
  - pilih model
  - chat
  - tombol indexing + progress + logs
  - dark/light mode

---

## Struktur folder penting

- `src/`
  - `main.py` → console app (Indexing/Retrieval/Generation)
  - `indexing/` → logic indexing
  - `retrieval/` → logic retrieval
  - `generation/` → logic generation
  - `util/` → constants, chunker, graph client, embedding client, tools Milvus
  - `interface/` → Web UI (FastAPI + static HTML/CSS/JS)
- `data/raw/` → tempat taruh file PDF/MD yang akan di-index
- `data/db/` → folder data lokal (mis. milvus.db untuk non-Windows, dsb.)
- `docs/` → dokumentasi flow

---

## Prasyarat

### 1) Python

Disarankan Python **3.11+**.

### 2) Milvus (WAJIB)

App ini memakai Milvus untuk vector database.

- Di Windows, default akan connect ke:
  - `MILVUS_URI=http://localhost:19530`
- Kamu bisa pakai:
  - Milvus self-hosted (Docker), atau
  - Zilliz Cloud (gunakan `MILVUS_URI` + `MILVUS_TOKEN`)

### 3) Neo4j (WAJIB untuk VersionRAG)

VersionRAG butuh Neo4j (Neo4j Aura / self-hosted).

Env var yang dipakai:
- `NEO4J_URI`
- `NEO4J_USER`
- `NEO4J_PASSWORD`

> Catatan: kalau pakai Aura Free, instance bisa auto **paused**. Resume via Neo4j console.

---

## Setup

### 1) Buat virtual environment

```powershell
cd "D:\UNIVERSITAS PERTAMINA\TA (Skripsi)\VersionRAG\versionRAG-UPER"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r src\requirements.txt
```

### 2) Buat `.env`

Disarankan taruh file `.env` di:
- `src/.env`

Contoh minimal:

```env
# Milvus
MILVUS_URI=http://localhost:19530
# (opsional, kalau Zilliz Cloud)
MILVUS_TOKEN=

# Neo4j (untuk VersionRAG)
NEO4J_URI=neo4j+s://<id>.databases.neo4j.io
NEO4J_USER=<username>
NEO4J_PASSWORD=<password>

# Embeddings
# EMBEDDING_PROVIDER=local   # gratis (sentence-transformers)
# atau default openai (butuh OPENAI_API_KEY)

# LLM
# LLM_MODE=openai
# OPENAI_API_KEY=...
```

---

## Jalankan via Console (CLI)

```powershell
cd "D:\UNIVERSITAS PERTAMINA\TA (Skripsi)\VersionRAG\versionRAG-UPER\src"
..\.\.venv\Scripts\python.exe main.py
```

Lalu pilih:
- Mode: **Indexing / Retrieval / Generation**
- Model: **Baseline / VersionRAG**

---

## Jalankan via Web UI (mirip ChatGPT)

Web interface ada di: `src/interface/`

Install dependency web (sekali):

```powershell
cd "D:\UNIVERSITAS PERTAMINA\TA (Skripsi)\VersionRAG\versionRAG-UPER"
.\.venv\Scripts\python.exe -m pip install -r src\interface\requirements.txt
```

Start server:

```powershell
.\.venv\Scripts\python.exe src\interface\backend\app.py
```

Open:
- `http://127.0.0.1:8000`

---

## Workflow penggunaan (recommended)

1) Taruh dokumen ke `data/raw/<category>/...`
2) Jalankan **Indexing** (Baseline atau VersionRAG)
3) Setelah indexing selesai, mulai **Chat/Generation**

---

## Troubleshooting cepat

- **Milvus tidak connect**
  - Pastikan Milvus server jalan dan `MILVUS_URI` benar.
  - Cek `src/util/inspect_milvus.py`:
    - `python src/util/inspect_milvus.py`

- **Neo4j error `ReadServiceUnavailable` / `SessionExpired`**
  - Biasanya Aura paused / belum siap.
  - Resume instance di `Neo4j Aura Console`, tunggu 1–2 menit, coba lagi.

- **Favicon / UI cache tidak berubah**
  - Hard refresh: **Ctrl+F5**
  - Kalau masih, coba incognito (favicon sering ke-cache agresif).

---

## Dokumen flow

- `docs/flow-baseline.md`
- `docs/flow-versionrag.md`
- `docs/flow-baseline-vs-versionrag.md`


