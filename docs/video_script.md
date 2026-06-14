# Video Script AlumniGraph AI

## 1. Pembukaan

Perkenalkan AlumniGraph AI sebagai aplikasi analisis jejaring alumni berbasis
Neo4j, Graph Data Science, Python, dan LLM.

## 2. Dataset Inspection

Tampilkan bahwa dataset diambil dari:

```text
https://github.com/burhansa25/graph
```

Jelaskan bahwa sistem tidak mengasumsikan nama kolom. Tahap pertama membaca
CSV aktual dan menghasilkan `docs/dataset_analysis.md`.

## 3. Preprocessing

Tampilkan perintah:

```powershell
python -m src.data_loader --raw-dir data/raw --output-dir data/processed
```

Jelaskan output node dan relationship CSV.

## 4. Neo4j Import

Tampilkan Docker Compose:

```powershell
docker compose up -d
```

Lalu import:

```powershell
python -m src.graph_builder --processed-dir data/processed
```

## 5. Graph Analytics

Demo query:

- Top connected alumni
- Jumlah alumni per universitas
- Jumlah alumni per occupation

## 6. Graph Machine Learning

Jelaskan:

- Louvain untuk cluster
- FastRP untuk embedding
- KNN untuk relationship `MIRIP_DENGAN`

## 7. Text-to-Cypher

Contoh pertanyaan:

```text
Universitas mana yang memiliki alumni paling banyak?
```

Tampilkan query Cypher yang dihasilkan dan hasil retrieval.

## 8. Graph-RAG

Tampilkan bahwa sistem mengeluarkan:

- Query Cypher
- Data retrieval
- Jawaban akhir

## 9. Penutup

Tekankan bahwa schema mengikuti dataset aktual dan tidak mengarang kolom.
