# Arsitektur AlumniGraph AI

AlumniGraph AI terdiri dari lima lapisan utama:

1. Dataset inspection
2. Preprocessing
3. Graph database import
4. Graph analytics dan graph machine learning
5. AI layer untuk Text-to-Cypher, LLM Graph Builder, dan Graph-RAG

## Alur Data

```text
GitHub CSV
  -> data/raw
  -> src.dataset_inspector
  -> docs/dataset_analysis.md
  -> src.data_loader
  -> data/processed
  -> src.graph_builder
  -> Neo4j
  -> GDS analytics / ML
  -> Text-to-Cypher dan Graph-RAG
```

## Dataset Aktual

Dataset repository `https://github.com/burhansa25/graph` menyediakan kolom:

- `univLabel`
- `alumniLabel`
- `occupationLabel`
- `employerLabel`
- `positionLabel`
- `wiki`

Karena tidak ada kolom deskripsi naratif, fitur LLM Graph Builder dari biodata
baru bisa dijalankan jika file teks tambahan ditempatkan di `data/biographies`.

## Modul

| Modul | Fungsi |
| --- | --- |
| `src.dataset_inspector` | Membaca semua CSV mentah dan membuat laporan dataset |
| `src.data_loader` | Membersihkan dataset dan membuat CSV node/relationship |
| `src.database` | Wrapper koneksi Neo4j |
| `src.graph_builder` | Membuat constraint dan import data ke Neo4j |
| `src.graph_analytics` | Query analitik dan proyeksi GDS |
| `src.graph_ml` | Louvain, FastRP embedding, dan KNN similarity |
| `src.text_to_cypher` | Mengubah pertanyaan Indonesia menjadi Cypher |
| `src.graph_rag` | Retrieval dari graph dan jawaban akhir memakai LLM |
| `src.cypher_guard` | Validasi query read-only sebelum dieksekusi |

## Neo4j

Neo4j dijalankan dengan Docker Compose:

```powershell
docker compose up -d
```

Browser Neo4j:

```text
http://localhost:7474
```

Bolt URI:

```text
bolt://localhost:7687
```
