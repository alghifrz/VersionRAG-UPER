# Interface (Web UI)

Folder ini berisi **website UI** (mirip ChatGPT) untuk:
- pilih model (**Baseline** / **VersionRAG**)
- chat (retrieval + generation)
- tombol settings untuk menjalankan **Index Baseline** dan **Index VersionRAG**

## Struktur

- `src/interface/backend/` → FastAPI server (API + serve static web)
- `src/interface/web/` → HTML/CSS/JS (tanpa build tool)

## Cara menjalankan (Windows / PowerShell)

Masuk ke folder project root lalu:

```powershell
cd "D:\UNIVERSITAS PERTAMINA\TA (Skripsi)\VersionRAG\versionRAG-UPER"

# Pastikan dependency web terinstall (di venv kamu)
.\.venv\Scripts\python.exe -m pip install -r src\interface\requirements.txt

# Jalankan web server
.\.venv\Scripts\python.exe src\interface\backend\app.py
```

Lalu buka browser ke:
- `http://127.0.0.1:8000`

## Catatan penting

- Indexing & retrieval tetap butuh service yang sama seperti mode console:
  - **Milvus** harus jalan
  - **Neo4j** (untuk VersionRAG) harus reachable & tidak paused
- `.env` (jika dipakai) idealnya berada di `src/.env` (sesuai loader di `src/util/constants.py`)

## Font (Creato Display)

UI diset memakai font **Creato Display**. Supaya tampil, taruh file font `.woff2` di:
- `src/interface/web/fonts/CreatoDisplay-Regular.woff2`
- `src/interface/web/fonts/CreatoDisplay-Bold.woff2`

Kalau kamu cuma punya font `.otf`, taruh ini (akan dipakai sebagai fallback):
- `src/interface/web/fonts/CreatoDisplay-Regular.otf`
- `src/interface/web/fonts/CreatoDisplay-Bold.otf`

Kalau font belum ada, UI akan otomatis fallback ke font sistem.


