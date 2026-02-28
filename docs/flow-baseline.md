# Flow Baseline (Sangat Detail, untuk Orang Awam)

Dokumen ini menjelaskan apa yang terjadi saat kamu memilih **Baseline** di aplikasi ini, untuk 3 mode:
- **Indexing**
- **Retrieval**
- **Generation**

Baseline bisa kamu bayangkan sebagai:
> “Saya ubah dokumen jadi potongan-potongan kecil (chunk), saya buat ‘sidik jari angka’ (embedding) untuk tiap potongan, saya simpan di database vektor (Milvus).  
> Nanti ketika ada pertanyaan, saya cari potongan yang paling mirip, lalu saya minta LLM menjawab berdasarkan potongan itu.”

---

## 0) Istilah yang perlu kamu tahu (versi gampang)

- **Dokumen**: file PDF/Markdown yang kamu taruh di `data/raw/`.
- **Chunk**: potongan kecil dari isi dokumen (misalnya 1–2 paragraf).
- **Embedding**: “sidik jari” berbentuk angka untuk teks. Dipakai supaya komputer bisa cari kemiripan makna.
- **Vector database (Milvus)**: tempat menyimpan embedding + teks chunk + metadata, supaya bisa dicari cepat.
- **Retriever**: bagian yang “mencari” chunk yang relevan.
- **Generator**: bagian yang “menjawab” pakai LLM berdasarkan chunk yang ditemukan.

---

## 1) Komponen yang dipakai Baseline

- **Entry point (menu console)**: `src/main.py`
- **Indexer**: `src/indexing/baseline/baseline_indexer.py`
- **Retriever**: `src/retrieval/baseline/baseline_retriever.py`
- **Generator**: `src/generation/baseline/baseline_generator.py`
- **Chunking dokumen**: `src/util/chunker.py`
  - PDF → diubah jadi markdown (teks) pakai `pymupdf4llm.to_markdown()`
  - Lalu dipecah jadi chunk pakai `MarkdownChunkingStrategy`
- **Embedding**: `src/util/embedding_client.py`
- **Konfigurasi**: `src/util/constants.py`
  - Collection Milvus baseline: `baseline_collection`
  - Default Milvus di Windows: `http://localhost:19530`

---

## 2) Mode Indexing (Baseline) — apa yang terjadi step-by-step

### 2.1. Tujuan indexing

Tujuan indexing adalah membuat dokumen kamu **bisa dicari berdasarkan makna**, bukan cuma keyword.

### 2.2. Input indexing

- File-file yang di-index diambil dari folder:
  - `data/raw/**` (rekursif ke subfolder)
- Semua file non-hidden akan diproses (yang namanya tidak diawali titik).

### 2.3. Langkah detail indexing

Saat kamu pilih:
- Mode: **Indexing**
- Model: **Baseline**

Maka yang terjadi:

- **Langkah A — Kumpulkan semua file**
  - Program meng-scan folder `data/raw/` dan mengumpulkan list path file absolut.

- **Langkah B — Pastikan Milvus collection ada**
  - Program konek ke Milvus.
  - Kalau collection `baseline_collection` belum ada, program membuatnya (dengan dimension embedding sesuai config).

- **Langkah C — Loop per file**
  - Untuk tiap file, program mengecek: “file ini sudah pernah di-index belum?”
    - Deteksinya berdasarkan field metadata `file` (absolute path) yang sudah tersimpan di Milvus.

  - Kalau **belum pernah** (atau kamu paksa reindex), program melakukan:

    - **C1. Chunking**
      - Kalau file `.pdf`:
        - PDF dibaca dan diubah jadi markdown (teks).
      - Kalau `.md`:
        - Dibaca langsung sebagai teks.
      - Teks dipecah jadi chunk (potongan).
      - Catatan: saat ini page number belum dipakai, jadi `page = -1`.

    - **C2. Embedding**
      - Setiap chunk dibuat embedding-nya (list angka).
      - Provider embedding ditentukan oleh environment:
        - `EMBEDDING_PROVIDER=local` → gratis, pakai `sentence-transformers`
        - default (openai) → butuh `OPENAI_API_KEY`

    - **C3. Simpan ke Milvus**
      - Program memasukkan data per chunk ke Milvus:
        - `vector`: embedding
        - `text`: isi chunk
        - `page`: nomor halaman (sementara -1)
        - `file`: path file absolut
        - metadata tambahan: `category`, `documentation`, `version`, `type`
          - Di Baseline, biasanya kosong (karena baseline tidak “mengerti versi/dokumentasi”), dan `type` diset `"file"`.

### 2.4. Output indexing (Baseline)

Setelah indexing selesai:
- Dokumen kamu **tidak** disimpan ulang sebagai file baru.
- Yang disimpan adalah:
  - chunk-chunk + embedding + metadata di **Milvus** (`baseline_collection`)

### 2.5. Kalau di terminal muncul apa?

Contoh yang umum:
- **`Indexing: <nama file>`** → lagi proses file itu.
- **`Indexed: <nama file> (N chunks)`** → file itu selesai dipecah jadi N chunk dan dimasukkan ke Milvus.
- **`Skipping: <nama file> (already indexed)`** → file sudah ada di Milvus, jadi tidak diulang.

---

## 3) Mode Retrieval (Baseline) — apa yang terjadi step-by-step

### 3.1. Tujuan retrieval

Retrieval itu mencari chunk yang paling relevan dengan pertanyaanmu.

### 3.2. Langkah detail retrieval

Saat kamu pilih:
- Mode: **Retrieval**
- Model: **Baseline**

Lalu kamu input pertanyaan (query), misalnya:  
“Apa isi kalender akademik tahun 2025?”

Maka yang terjadi:

- **Langkah A — Buat embedding untuk pertanyaan**
  - Pertanyaanmu diubah menjadi embedding (sidik jari angka).

- **Langkah B — Search ke Milvus**
  - Program mencari di `baseline_collection`:
    - ambil Top-K chunk paling mirip (default 15)
  - Yang dikembalikan dari Milvus:
    - `text` chunk
    - `file` sumber
    - `page` (sementara -1)

- **Langkah C — Jadikan `RetrievedData`**
  - Hasilnya dibungkus dalam objek `RetrievedData`:
    - `chunks`: list teks chunk
    - `source_files`: list file sumber
    - `page_nrs`: list page (sementara -1)

### 3.3. Output retrieval (Baseline)

Output retrieval adalah “bahan mentah” untuk generation:
- potongan teks yang relevan,
- dari file mana asalnya.

---

## 4) Mode Generation (Baseline) — apa yang terjadi step-by-step

### 4.1. Tujuan generation

Generation adalah membuat jawaban akhir memakai LLM **berdasarkan retrieved chunks**.

### 4.2. Langkah detail generation

Saat kamu pilih:
- Mode: **Generation**
- Model: **Baseline**

Lalu kamu input pertanyaan. Maka:

- **Langkah A — Jalankan retrieval dulu**
  - Sistem melakukan proses retrieval seperti bagian (3).

- **Langkah B — Susun prompt untuk LLM**
  - Sistem membuat prompt berisi:
    - Pertanyaan
    - “Retrieved Data” (teks chunk + sumbernya)

- **Langkah C — Panggil LLM**
  - LLM diminta menjawab **hanya** dari context yang diberikan (sesuai system prompt di base generator).

### 4.3. Output generation (Baseline)

Output generation adalah:
- teks jawaban dari LLM.

---

## 5) “Data saya tersimpan di mana?” (Baseline)

- **Milvus**:
  - Menyimpan embedding + chunk + metadata
  - Collection: `baseline_collection`

Baseline **tidak pakai Neo4j** (tidak ada graph / node / relationship di baseline).

---

## 6) Checklist sebelum jalan (Baseline)

- **Milvus jalan** (karena indexing/retrieval baseline butuh Milvus)
  - Di Windows, defaultnya app akan connect ke `http://localhost:19530`
  - Kalau Milvus belum jalan, indexing/retrieval akan error saat connect.

- **Embedding provider siap**
  - Kalau pakai OpenAI:
    - set `OPENAI_API_KEY`
  - Kalau mau gratis:
    - set `EMBEDDING_PROVIDER=local`
    - pastikan `sentence-transformers` terinstall

- **Dokumen ada di `data/raw/`**

---

## 7) Troubleshooting yang sering kejadian (Baseline)

- **Tidak ada hasil retrieval / jawabannya ngaco**
  - Pastikan dokumen sudah di-index (mode Indexing).
  - Pastikan pertanyaan memang “nyambung” dengan isi dokumen.
  - Coba pertanyaan yang lebih spesifik.

- **Indexing terasa lambat**
  - Normal: embedding + insert banyak chunk memang memakan waktu.
  - Provider OpenAI tergantung koneksi internet & rate limit.


