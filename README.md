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
