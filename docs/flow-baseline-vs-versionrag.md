# Flow Proses: Baseline vs VersionRAG (Indexing / Retrieval / Generation)

Dokumen ini menjelaskan **apa saja yang terjadi** pada tiap proses di repo ini untuk:
- **Baseline**
- **VersionRAG**

Sumber utama flow ada di `src/main.py` (console mode).

---

## Gambaran besar (entrypoint)

Di `src/main.py`:
- **Mode Indexing** → `indexer.index_data(file_paths)`
- **Mode Retrieval** → `retriever.retrieve(query)`
- **Mode Generation** → `retriever.retrieve(query)` lalu `generator.generate(retrieved_data, query)`

Input data indexing diambil dari folder `data/raw/**` (semua file non-hidden).

---

## Komponen yang dipakai (shared)

- **Chunking dokumen**: `src/util/chunker.py`
  - PDF diubah dulu ke markdown via `pymupdf4llm.to_markdown()`
  - Lalu dipecah jadi chunk via `MarkdownChunkingStrategy`
  - Saat ini `page` diset `-1` (page number belum dipakai).

- **Embeddings**: `src/util/embedding_client.py`
  - `EMBEDDING_PROVIDER=local` → `sentence-transformers`
  - Default → OpenAI embeddings (`OPENAI_API_KEY` dibutuhkan)

- **Vector DB (Milvus)**:
  - Collection baseline: `baseline_collection`
  - Collection versionrag: `VersionRAG_collection`
  - Default URI Windows: `http://localhost:19530` (lihat `src/util/constants.py`)

- **LLM**: `src/util/llm_client.py`
  - Dipakai untuk: ekstraksi metadata (VersionRAG indexing), parsing query (VersionRAG retrieval), dan generation.

---

## Baseline

### 1) Indexing (Baseline)

**Entry**: `src/indexing/baseline/baseline_indexer.py` → `BaselineIndexer.index_data()`

**Flow**:
- Ambil semua file dari `data/raw/**` (di `src/main.py`)
- Buat collection Milvus kalau belum ada (`BaseIndexer.createCollectionIfRequired()`)
- Untuk setiap file:
  - Cek sudah pernah di-index atau belum (`BaseIndexer.is_file_indexed()`)
  - Kalau belum / reindex:
    - Chunk dokumen (`Chunker.chunk_document()`)
    - Embed tiap chunk (`embedding_fn.encode_documents()`)
    - Insert ke Milvus (`MilvusClient.insert()`)
      - Metadata yang disimpan per chunk (lihat `BaseIndexer.index()`):
        - `text`, `page`, `file` (absolute path)
        - `category`, `documentation`, `version`, `type` (di baseline biasanya kosong, `type="file"`)

**Output**:
- Data vector (chunks + metadata) tersimpan di **Milvus** collection `baseline_collection`.

---

### 2) Retrieval (Baseline)

**Entry**: `src/retrieval/baseline/baseline_retriever.py` → `BaselineRetriever.retrieve(query)`

**Flow**:
- Embed query (`encode_queries([query])`)
- `MilvusClient.search()` ke collection `baseline_collection`
  - `limit = MILVUS_BASELINE_SOURCE_COUNT` (default 15)
  - output fields: `text`, `page`, `file`
- Kembalikan `RetrievedData(chunks, page_nrs, source_files)`

**Output**:
- Top-K chunk paling mirip dari Milvus (baseline tidak punya konsep version/category/doc di retrieval).

---

### 3) Generation (Baseline)

**Entry**: `src/generation/baseline/baseline_generator.py` → `BaselineGenerator.generate(retrieved_data, query)`

**Flow**:
- Buat `user_prompt`:
  - `Question: ...`
  - `Retrieved Data: ...` (hasil `RetrievedData.__str__()` menampilkan source file + page + chunk)
- Panggil LLM (`LLMClient.generate(system_prompt, user_prompt)`)
- Return `Response(answer=llm_response)`

**Output**:
- Jawaban LLM berbasis konteks retrieved (RAG sederhana).

---

## VersionRAG

VersionRAG menyimpan:
- **Struktur & relasi versi** di **Neo4j** (graph)
- **Embeddings untuk search** di **Milvus**

### 1) Indexing (VersionRAG)

**Entry**: `src/indexing/versionrag/versionrag_indexer.py` → `VersionRAGIndexer.index_data(data_files)`

**Flow ringkas**:

#### A. Ekstraksi atribut (metadata)
**File**: `src/indexing/versionrag/versionrag_indexer_extract_attributes.py`

Untuk tiap file:
- Infer `category` dari nama folder parent (mis. `data/raw/kalender-akademik/*.pdf` → `category="kalender-akademik"`)
- Ambil teks awal dokumen:
  - PDF: baca 1 page & sampai ~10 page pertama (via chunker)
- LLM ekstrak:
  - `topic` (nama dokumentasi)
  - `description`
- LLM klasifikasi tipe file:
  - `WithoutChangelog` vs `Changelog`
- `version` diekstrak dari **nama file** (tanpa extension)

Hasilnya jadi `FileAttributes` berisi: `documentation`, `display_name`, `description`, `category`, `version`, `type`, dll.

#### B. Cluster documentation (menyatukan nama doc yang mirip)
**File**: `src/indexing/versionrag/versionrag_indexer_clustering.py` → `cluster_documentation()`

LLM mengelompokkan `documentation` yang mirip → lalu:
- `documentation` diseragamkan jadi `cluster_name`
- `description` diseragamkan jadi `cluster_description`

#### C. Tulis “basic graph” ke Neo4j

**File**: `src/indexing/versionrag/versionrag_indexer_graph.py` → `generate_basic_graph()`

Untuk tiap file, Neo4j diisi (pakai `session.execute_write(...)`):
- `(:Documentation {name})` + set `description`, `display_name`
- `(:Version {version, documentation})`
- `(:Content {file})` + set `type` (WithoutChangelog/Changelog)
- Relasi:
  - `(Documentation)-[:HAS_VERSION]->(Version)`
  - `(Version)-[:HAS_CONTENT]->(Content)`

Lalu:
- Buat relasi chain versi `(v1)-[:NEXT_VERSION]->(v2)` berdasarkan sorting versi (numeric / year-range / year / date / string).
- Buat kategori:
  - Jika metadata `category` tersedia → buat `(:Category {name})` lalu `(Category)-[:CONTAINS]->(Documentation)` (via `link_categories_from_attributes_tx`)
  - Jika tidak ada → lakukan clustering kategori otomatis (`cluster_categories_tx()`), lalu buat node Category + relasi CONTAINS.

#### D. Bangun “change level” (Change nodes) di Neo4j

**File**: `src/indexing/versionrag/versionrag_indexer_graph.py` → `generate_change_level()`
**Logika ekstraksi changes**: `src/indexing/versionrag/versionrag_indexer_extract_changes.py`

Step:
- Ambil daftar konten changelog dari graph (`get_changelog_contents()`)
- Ambil pasangan dokumen antar versi berurutan untuk diff (`get_diff_contents()`), berdasarkan `NEXT_VERSION`
- Buat list `Change` dari:
  - **Changelog**: chunk changelog → LLM ekstrak daftar perubahan (`extract_changes_from_changelog`)
  - **Diff**: `DeepDiff` antar dokumen → LLM rangkum jadi change log (`generate_changes_from_diff`)
- Simpan changes ke Neo4j (`store_changes()`):
  - `(Version)-[:HAS_CHANGES]->(:Changes)-[:INCLUDES]->(:Change {name, description, ...})`

#### E. Index content + changes ke Milvus (untuk search)

Masih di `VersionRAGIndexer.index_data()`:
- Ambil konteks dari Neo4j:
  - `get_all_content_nodes_with_context()` menghasilkan list `file + (category, documentation, version)`
  - `get_all_change_nodes_with_context()` menghasilkan list `change + konteksnya`
- Index ke Milvus (`VersionRAG_collection`):
  - Semua `Content` (file asli) di-index seperti baseline, tapi metadata penuh (`category`, `documentation`, `version`, `type="file"`)
  - Semua `Change` juga di-index sebagai 1 chunk text (`name + description`) dengan metadata (`type="change"`)
  - Ada mekanisme **skip existing** untuk menghindari duplikat

**Output**:
- Graph struktur versi + changes tersimpan di **Neo4j**
- Vector index (content + changes) tersimpan di **Milvus** collection `VersionRAG_collection`

---

### 2) Retrieval (VersionRAG)

**Entry**: `src/retrieval/versionrag/versionrag_retriever.py` → `VersionRAGRetriever.retrieve(query)`

**Flow**:

#### A. LLM Parser memilih tipe retrieval + parameter

**File**: `src/retrieval/versionrag/versionrag_retriever_parser.py`

- Sistem membuat konteks:
  - daftar kategori dari Neo4j (`retrieve_categories()`)
  - daftar dokumentasi dari Neo4j (`retrieve_documentations()`)
- LLM mengembalikan JSON:
  - `"retrieval"`: `VersionRetrieval | ChangeRetrieval | ContentRetrieval`
  - `"parameters"`: sesuai tipe (mis. `category/documentation/version/query`)

#### B. Normalisasi nama parameter (opsional, pakai LLM)

**File**: `src/retrieval/versionrag/versionrag_retriever_db.py` → `preprocess_params()`

Kalau user nulis kategori/doc/version “nggak persis”, sistem mencoba memetakan ke yang paling cocok:
- `retrieve_category_name()`
- `retrieve_documentation_name()`
- `retrieve_version()`

#### C. Eksekusi retrieval sesuai tipe

**File**: `src/retrieval/versionrag/versionrag_retriever_db.py` → `retrieve()`

- **VersionRetrieval**
  - Query Neo4j: Category → Documentation → Version
  - Output: string list versi yang tersedia

- **ContentRetrieval**
  - Vector search di Milvus `VersionRAG_collection`
  - Filter metadata (jika ada):
    - `category == "..."`
    - `documentation == "..."`
    - `version like "prefix%"`
    - `type == "file"` (kalau dipaksa)
  - Output: `RetrievedData(chunks, page_nrs, source_files, versions)`

- **ChangeRetrieval**
  - Set filter `type="change"` lalu vector search di Milvus (limit lebih besar, default 150) untuk “retrieved content in changes”
  - Di saat yang sama query Neo4j untuk list change yang tersimpan pada version/doc/category
  - Output: gabungan string “retrieved content ...” + “retrieved changes ...” (dibungkus jadi `RetrievedData` via `wrap()`)

---

### 3) Generation (VersionRAG)

**Entry**: `src/generation/versionrag/versionrag_generator.py` → `VersionRAGGenerator.generate(retrieved_data, query)`

**Flow**:
- Sama seperti Baseline:
  - prompt = Question + Retrieved Data
  - panggil `LLMClient.generate()`
- Bedanya: **system prompt** lebih “version-aware” (boleh membandingkan versi, menyebut versi tertentu kalau ada di context).

---

## Cheat sheet: “yang tersimpan di mana?”

- **Baseline**
  - **Indexing** → Milvus (`baseline_collection`)
  - **Retrieval** → Milvus search
  - **Generation** → LLM pakai retrieved chunks

- **VersionRAG**
  - **Indexing** → Neo4j (graph) + Milvus (`VersionRAG_collection`)
  - **Retrieval** → (LLM parser) + Neo4j (lookup/listing) + Milvus (vector search + filter)
  - **Generation** → LLM pakai context, aware terhadap versi

