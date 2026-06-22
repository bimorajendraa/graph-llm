# AlumniGraph AI

Proyek ini dimulai dari Tahap 0 - Dataset Inspection. Tahap ini wajib selesai
sebelum membuat koneksi Neo4j, query import, graph analytics, Text-to-Cypher,
atau Graph-RAG.

## Tujuan Tahap 0

- Mengambil dataset dari repository sumber.
- Menyimpan file CSV mentah ke `data/raw`.
- Membaca seluruh CSV tanpa mengasumsikan nama kolom.
- Menampilkan nama file, jumlah baris, jumlah kolom, daftar kolom, missing
  value, duplikasi, dan contoh 5 baris pertama.
- Membuat laporan inspeksi di `docs/dataset_analysis.md`.
- Memberi rekomendasi awal schema graph berdasarkan kolom yang benar-benar
  ditemukan.

## Cara Mengambil Dataset

Jalankan dari folder proyek `alumni-graph-ai`.

```powershell
git clone https://github.com/burhansa25/graph.git data/source_repo
Get-ChildItem .\data\source_repo -Recurse -Filter *.csv | Copy-Item -Destination .\data\raw
```

Jika ada file CSV dengan nama sama di subfolder berbeda, salin secara manual
agar nama file tidak tertimpa.

## Instalasi

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Menjalankan Inspeksi Dataset

```powershell
python -m src.dataset_inspector --data-dir data/raw --output docs/dataset_analysis.md
```

Output laporan akan tersimpan di:

```text
docs/dataset_analysis.md
```

Notebook juga tersedia di:

```text
notebooks/00_dataset_inspection.ipynb
```

## Menjalankan Preprocessing

Setelah laporan dataset selesai dibuat dan mapping kolom sudah sesuai, jalankan:

```powershell
python -m src.data_loader --raw-dir data/raw --output-dir data/processed
```

Script ini membuat CSV node dan relationship di `data/processed` berdasarkan
kolom aktual:

- `alumniLabel`
- `univLabel`
- `occupationLabel`
- `employerLabel`
- `positionLabel`
- `wiki`

## Struktur Folder

```text
alumni-graph-ai/
|-- README.md
|-- requirements.txt
|-- .env.example
|-- .gitignore
|-- docker-compose.yml
|-- data/
|   |-- raw/
|   |-- processed/
|   `-- biographies/
|-- notebooks/
|   |-- 00_dataset_inspection.ipynb
|   |-- 01_database_connection.ipynb
|   |-- 02_data_preprocessing.ipynb
|   |-- 03_import_to_neo4j.ipynb
|   |-- 04_llm_graph_builder.ipynb
|   |-- 05_graph_analytics.ipynb
|   |-- 06_graph_machine_learning.ipynb
|   |-- 07_text_to_cypher.ipynb
|   `-- 08_graph_rag_demo.ipynb
|-- src/
|   |-- __init__.py
|   |-- cache_manager.py
|   |-- chat_cli.py
|   |-- config.py
|   |-- cypher_guard.py
|   |-- database.py
|   |-- data_loader.py
|   |-- dataset_inspector.py
|   |-- entity_resolver.py
|   |-- graph_analytics.py
|   |-- graph_builder.py
|   |-- graph_ml.py
|   |-- graph_rag.py
|   |-- llm_client.py
|   |-- logger.py
|   `-- text_to_cypher.py
`-- docs/
    |-- ai_usage.md
    |-- architecture.md
    |-- chat_usage.md
    |-- dataset_analysis.md
    |-- evaluation.md
    |-- graph_schema.md
    `-- video_script.md
```

## Menjalankan Neo4j dan Import Graph

```powershell
docker compose up -d
python -m src.graph_builder --processed-dir data/processed
```

## Ngobrol dengan LLM

Salin `.env.example` menjadi `.env`, lalu isi `OPENROUTER_API_KEY`.

```powershell
copy .env.example .env
```

Chat LLM biasa:

```powershell
python -m src.chat_cli --mode llm
```

Chat dengan data alumni dari Neo4j atau Graph-RAG:

```powershell
docker compose up -d
python -m src.graph_builder --processed-dir data/processed
python -m src.chat_cli --mode rag
```

Mode untuk melihat query Cypher dan data retrieval saja:

```powershell
python -m src.chat_cli --mode cypher
```

## Urutan Notebook

Jalankan notebook sesuai nomor:

1. `00_dataset_inspection.ipynb`
2. `01_database_connection.ipynb`
3. `02_data_preprocessing.ipynb`
4. `03_import_to_neo4j.ipynb`
5. `04_llm_graph_builder.ipynb`
6. `05_graph_analytics.ipynb`
7. `06_graph_machine_learning.ipynb`
8. `07_text_to_cypher.ipynb`
9. `08_graph_rag_demo.ipynb`

## Catatan Penting

Jangan membuat properti graph seperti `alumniId`, `alumniLabel`,
`univLabel`, `occupationLabel`, `employerLabel`, `positionLabel`,
`description`, atau `source` sebelum kolom tersebut benar-benar ditemukan
atau dipetakan dari dataset aktual.

Tahap berikutnya baru boleh dibuat setelah `docs/dataset_analysis.md`
menjelaskan struktur dataset dan mapping kolom ke schema target.

## Troubleshooting

### Jawaban selalu kosong / "Data retrieval tidak ada hasil"

Penyebab paling umum: database Neo4j kosong, biasanya setelah container
atau volume Docker direset (mis. `docker compose down -v`, container baru,
atau pertama kali setup). Tanda di log: warning seperti
`label does not exist: Alumni` atau `relationship type does not exist:
LULUSAN_DARI`.

**Solusi**, jalankan ulang import setelah Neo4j aktif:

```powershell
docker compose up -d
python -m src.graph_builder --processed-dir data/processed
```

Mode `--mode rag` sekarang otomatis memberi peringatan di awal sesi chat
jika node `Alumni` masih nol, jadi masalah ini akan terlihat segera tanpa
perlu menunggu jawaban kosong berulang kali.

### `Error Graph-RAG: 'choices'`

Ini terjadi saat OpenRouter mengembalikan HTTP 200 tapi body response
berisi `{"error": {...}}` alih-alih `{"choices": [...]}`, biasanya saat
provider upstream model gratis sedang overload. `src/llm_client.py` sudah
menangani kondisi ini secara eksplisit dan akan menampilkan pesan error
yang jelas, bukan crash. Coba ulangi pertanyaan, atau ganti
`OPENROUTER_MODEL` di `.env`.

### `Error: Query harus memiliki RETURN clause.`

Terjadi saat LLM tidak mengembalikan Cypher yang valid, biasanya untuk
pertanyaan chit-chat atau di luar scope data alumni (mis. "Apa yang bisa
kita lakukan di sini?"). `GraphRAG.answer()` sekarang menangani kondisi
ini secara otomatis dan memberi jawaban yang membantu daripada
menampilkan error mentah.

### `429 Rate limit exceeded: free-models-per-day`

Kuota harian model gratis OpenRouter sudah habis (umumnya terbatas dan
diprioritaskan lebih rendah dibanding request berbayar). Solusi:

- Tunggu reset kuota harian, atau
- Tambahkan kredit di akun OpenRouter dan ganti `OPENROUTER_MODEL` ke
  model berbayar (lihat harga terkini di openrouter.ai/models), atau
- Aktifkan cache LLM (`LLM_CACHE_ENABLED=true`, default aktif) supaya
  pertanyaan yang identik tidak memanggil API lagi.

### Respons terasa lambat

Setiap pertanyaan di `--mode rag` bisa memicu hingga 3 pemanggilan LLM
berurutan: rewrite pertanyaan follow-up, generate Cypher, dan generate
jawaban akhir. Beberapa hal yang membantu:

- Cache LLM aktif secara default (`src/cache_manager.py` via
  `src/llm_client.py`) sehingga pertanyaan yang identik tidak memanggil
  API lagi.
- `src/query_rewriter.py` sekarang skip pemanggilan LLM untuk pertanyaan
  yang terlihat berdiri sendiri (bukan follow-up vague seperti
  "Lainnya?" atau "Kalau dari UGM?").
- Model gratis (`:free`) cenderung lebih lambat karena prioritas
  routing lebih rendah dibanding model berbayar.