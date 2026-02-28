# Flow VersionRAG (Sangat Detail, untuk Orang Awam)

Dokumen ini menjelaskan apa yang terjadi saat kamu memilih **VersionRAG** di aplikasi ini, untuk 3 mode:
- **Indexing**
- **Retrieval**
- **Generation**

VersionRAG bisa kamu bayangkan sebagai:
> “Saya bukan cuma simpan potongan teks untuk search (Milvus), tapi juga bikin peta hubungan dokumen-versi-perubahan (Neo4j).  
> Jadi sistem bisa tahu: dokumen apa, punya versi apa saja, versi mana yang berikutnya, dan perubahan apa yang terjadi antar versi.”

---

## 0) Istilah yang perlu kamu tahu (versi gampang)

- **Versi**: penanda versi dokumen. Di repo ini, versi diambil dari **nama file** (mis. `2024-2025.pdf` → versi `2024-2025`).
- **Documentation**: “nama dokumen stabil” (mis. “Kalender Akademik Universitas Pertamina”).
- **Category**: kelompok dokumen (di repo ini biasanya diambil dari **nama folder** di `data/raw/`).
- **Change**: catatan perubahan (bisa diekstrak dari changelog, atau dibuat dari diff antar versi).

---

## 1) Apa bedanya VersionRAG dengan Baseline?

- **Baseline**: hanya Milvus (vector search) + LLM untuk jawab.
- **VersionRAG**: Milvus + **Neo4j graph** + LLM.

Dengan VersionRAG kamu dapat:
- lihat daftar versi yang tersedia per dokumen,
- lihat hubungan “versi berikutnya”,
- simpan dan retrieve “perubahan” antar versi,
- melakukan retrieval dengan filter (category / documentation / version).

---

## 2) Komponen yang dipakai VersionRAG

- **Entry point (menu console)**: `src/main.py`
- **Indexer**: `src/indexing/versionrag/versionrag_indexer.py`
- **Graph builder (Neo4j writer/reader)**: `src/indexing/versionrag/versionrag_indexer_graph.py`
- **Metadata extractor**: `src/indexing/versionrag/versionrag_indexer_extract_attributes.py`
- **Change extractor**: `src/indexing/versionrag/versionrag_indexer_extract_changes.py`
- **Clustering**:
  - cluster documentation: `src/indexing/versionrag/versionrag_indexer_clustering.py` → `cluster_documentation()`
  - cluster categories (jika tidak ada category): `cluster_categories_tx()`
- **Retriever wrapper**: `src/retrieval/versionrag/versionrag_retriever.py`
- **Retriever (Neo4j + Milvus)**: `src/retrieval/versionrag/versionrag_retriever_db.py`
- **Query parser (LLM classifier)**: `src/retrieval/versionrag/versionrag_retriever_parser.py`
- **Generator**: `src/generation/versionrag/versionrag_generator.py`
- **Graph client (Neo4j connect)**: `src/util/graph_client.py`
- **Vector DB (Milvus)**:
  - collection: `VersionRAG_collection` (lihat `src/util/constants.py`)

---

## 3) Mode Indexing (VersionRAG) — step-by-step

### 3.1. Tujuan indexing VersionRAG

Indexing VersionRAG menghasilkan 2 hal sekaligus:
- **A. Neo4j graph**: struktur dokumen → versi → content → changes → kategori
- **B. Milvus vectors**: supaya konten dan changes bisa dicari pakai kemiripan makna

### 3.2. Input indexing

Sama seperti baseline:
- semua file di `data/raw/**`

Namun VersionRAG menganggap:
- **nama folder** ≈ **category**
  - contoh: `data/raw/kalender-akademik/2024-2025.pdf`
    - category = `kalender-akademik`
- **nama file tanpa extension** ≈ **version**
  - `2024-2025.pdf` → version `2024-2025`

### 3.3. Langkah detail indexing

Saat kamu pilih:
- Mode: **Indexing**
- Model: **VersionRAG**

Maka flow besarnya:

#### A. Ekstrak atribut (metadata) tiap file
**File**: `src/indexing/versionrag/versionrag_indexer_extract_attributes.py`

Untuk setiap file:
- **A1. Tentukan category**
  - kalau category tidak diberikan, diambil dari nama folder parent.

- **A2. Ambil teks awal untuk dianalisis**
  - PDF:
    - sistem baca 1 halaman pertama → untuk “topic + description”
    - sistem baca sampai 10 halaman pertama → untuk “klasifikasi file type”

- **A3. LLM ekstrak “topic” dan “description”**
  - `topic` = nama dokumentasi (judul pendek, tanpa info versi)
  - `description` = ringkasan singkat dokumen (bahasa mengikuti dokumen)

- **A4. LLM klasifikasi tipe file**
  - `WithoutChangelog` (dokumen biasa)
  - `Changelog` (dokumen yang berisi daftar perubahan)

- **A5. Ambil version dari nama file**
  - versi tidak diambil dari LLM, tapi dari nama file.

Output tahap ini adalah list `FileAttributes`:
- `documentation` (id doc)
- `display_name` (nama tampilan)
- `description`
- `category`
- `version`
- `type` (With/Without changelog)
- `data_file` (path file)

#### B. Cluster documentation (menyatukan doc yang mirip)
**File**: `src/indexing/versionrag/versionrag_indexer_clustering.py` → `cluster_documentation()`

Masalah yang diselesaikan:
- Kadang LLM memberi nama doc sedikit beda antar file (padahal dokumen sama).

Solusinya:
- LLM mengelompokkan dokumentasi yang mirip,
- lalu `documentation` dan `description` diseragamkan untuk semua file dalam cluster.

#### C. Tulis “basic graph” ke Neo4j
**File**: `src/indexing/versionrag/versionrag_indexer_graph.py` → `generate_basic_graph()`

Untuk tiap file, sistem membuat node & relasi di Neo4j:

- **Node**
  - `Documentation`
  - `Version`
  - `Content`
  - `Category` (jika ada)

- **Relasi**
  - `(:Documentation)-[:HAS_VERSION]->(:Version)`
  - `(:Version)-[:HAS_CONTENT]->(:Content)`

Lalu sistem juga:
- membuat chain versi `(:Version)-[:NEXT_VERSION]->(:Version)` berdasarkan sorting versi,
- membuat relasi category:
  - `(:Category)-[:CONTAINS]->(:Documentation)`

#### D. Bangun “change level” di Neo4j (Change nodes)
**File**: `src/indexing/versionrag/versionrag_indexer_graph.py` → `generate_change_level()`
**Logika**: `src/indexing/versionrag/versionrag_indexer_extract_changes.py`

Sistem menghasilkan changes dari 2 sumber:

- **D1. Dari changelog (kalau ada file changelog)**
  - Changelog di-chunk
  - LLM mengekstrak daftar perubahan (`name`, `description`)

- **D2. Dari diff antar versi berurutan**
  - Sistem ambil pasangan versi berurutan berdasarkan `NEXT_VERSION`
  - Konten v1 vs v2 dibandingkan pakai `DeepDiff`
  - Hasil diff (JSON) diberikan ke LLM supaya berubah jadi “change log” yang manusiawi

Setelah dapat list changes:
- disimpan ke Neo4j sebagai:
  - `(Version)-[:HAS_CHANGES]->(Changes)-[:INCLUDES]->(Change)`
  - `Change` punya atribut seperti `name`, `description`, `source_file`, `origin`, dll.

#### E. Index ke Milvus (content + changes)
**File**: `src/indexing/versionrag/versionrag_indexer.py`

Setelah graph jadi, sistem mengambil semua context dari Neo4j:
- `file` content + `category/documentation/version`
- change + `category/documentation/version`

Lalu masuk ke Milvus `VersionRAG_collection`:
- **E1. Index Content**
  - sama seperti baseline: chunk dokumen → embedding → insert
  - bedanya metadata diisi penuh:
    - `category`, `documentation`, `version`, `type="file"`

- **E2. Index Change**
  - setiap change jadi 1 text chunk:
    - `name + "\n" + description`
  - metadata:
    - `category`, `documentation`, `version`, `type="change"`

### 3.4. Output indexing (VersionRAG)

- **Neo4j**: berisi graph struktur versi + changes
- **Milvus**: berisi vector index untuk `file` dan `change`

---

## 4) Mode Retrieval (VersionRAG) — step-by-step

### 4.1. Konsep utama retrieval VersionRAG

Retrieval VersionRAG tidak selalu “vector search”.
Pertama-tama sistem menentukan: pertanyaanmu itu tipe apa?

Ada 3 tipe:
- **VersionRetrieval**: “tampilkan versi apa saja yang tersedia”
- **ChangeRetrieval**: “tampilkan perubahan apa di versi X / di dokumen Y”
- **ContentRetrieval**: “jawab pertanyaan berdasarkan isi dokumen”

### 4.2. Langkah detail retrieval

#### A. Parser (LLM) mengklasifikasikan pertanyaan
**File**: `src/retrieval/versionrag/versionrag_retriever_parser.py`

Sistem memberi LLM konteks:
- daftar kategori yang ada (hasil query Neo4j)
- daftar documentation yang ada (hasil query Neo4j)

LLM mengeluarkan JSON seperti:
- `{"retrieval":"ContentRetrieval","parameters":{"query":"...","category":"...","documentation":"...","version":"..."}}`

#### B. Normalisasi parameter (opsional)
**File**: `src/retrieval/versionrag/versionrag_retriever_db.py` → `preprocess_params()`

Kalau user nulis nama kategori/doc/version “agak beda”:
- sistem mencoba “menyamakan” ke yang paling cocok (pakai LLM) supaya query ke DB pas.

#### C. Eksekusi sesuai tipe
**File**: `src/retrieval/versionrag/versionrag_retriever_db.py`

- **VersionRetrieval**
  - Query ke Neo4j:
    - Category → Documentation → Version
  - Output: list versi (string)

- **ContentRetrieval**
  - Vector search ke Milvus `VersionRAG_collection`
  - Bisa pakai filter metadata:
    - category
    - documentation
    - version prefix (`version like "2025%"`)
    - type (`file` atau `change`)
  - Output: `RetrievedData` (chunks + file + version)

- **ChangeRetrieval**
  - Biasanya gabungan:
    - vector search Milvus untuk changes (type="change")
    - query Neo4j untuk list changes yang tersimpan (by category/doc/version)
  - Output: dibungkus jadi `RetrievedData(chunks="...")` (string panjang)

---

## 5) Mode Generation (VersionRAG) — step-by-step

Generation sama konsepnya seperti baseline:
- retrieval dulu
- hasil retrieval dijadikan context
- LLM menjawab dari context

Bedanya:
- system prompt VersionRAG lebih “version-aware”
  - kalau ada beberapa versi di context, LLM boleh membandingkan / menyebut versi tertentu.

---

## 6) Cara melihat graph-nya di Neo4j (website)

### 6.1. Buka Neo4j Browser (Aura)

- Buka Neo4j Aura Console: `https://console.neo4j.io/`
- Pilih instance → klik **Open / Query** (Neo4j Browser)

### 6.2. Query sederhana untuk melihat graph

Pakai query ini:

1) Lihat sebagian node + relasi:

```cypher
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 50
```

2) Lihat struktur utama:

```cypher
MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CONTENT]->(c:Content)
RETURN d, v, c
LIMIT 20
```

3) Lihat chain versi:

```cypher
MATCH path = (v1:Version)-[:NEXT_VERSION*]->(v2:Version)
RETURN path
LIMIT 10
```

---

## 7) “Data saya tersimpan di mana?” (VersionRAG)

- **Neo4j** (graph)
  - Node: `Category`, `Documentation`, `Version`, `Content`, `Changes`, `Change`
  - Relasi utama:
    - `CONTAINS`, `HAS_VERSION`, `HAS_CONTENT`, `NEXT_VERSION`, `HAS_CHANGES`, `INCLUDES`

- **Milvus** (vector)
  - Collection: `VersionRAG_collection`
  - Menyimpan:
    - chunk isi dokumen (type="file")
    - chunk text perubahan (type="change")
  - Metadata penting:
    - `category`, `documentation`, `version`, `file`, `type`

---

## 8) Checklist sebelum jalan (VersionRAG)

- **Neo4j harus bisa diakses**
  - Pastikan instance Aura **tidak paused**
  - Pastikan URI/username/password benar

- **Milvus harus jalan**
  - Default Windows: `http://localhost:19530`

- **LLM & Embedding siap**
  - LLM dipakai untuk:
    - ekstrak metadata
    - klasifikasi query retrieval
    - merangkum changes dari diff
    - generation

---

## 9) Troubleshooting yang sering kejadian (VersionRAG)

- **`ReadServiceUnavailable` / `SessionExpired`**
  - Biasanya karena Aura instance paused / belum siap.
  - Solusi: resume di `https://console.neo4j.io/` lalu tunggu 1–2 menit.

- **Indexing berhasil tapi retrieval “no data indexed”**
  - Itu berarti Milvus collection `VersionRAG_collection` belum ada atau kosong.
  - Pastikan indexing selesai sampai “content indexed”.


