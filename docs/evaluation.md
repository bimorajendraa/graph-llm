# Evaluasi AlumniGraph AI

## Evaluasi Dataset

Hasil inspeksi awal:

- Total file CSV: 3
- Total baris mentah: 7.168
- Kolom unik: 6
- Dataset utama preprocessing: `normalized_alumni_dataset.csv`

Hasil preprocessing:

- Clean rows: 2.567
- Alumni: 772
- Universities: 113
- Occupations: 289
- Employers: 185
- Positions: 304
- Relasi alumni-university: 772
- Relasi alumni-occupation: 894
- Relasi alumni-employer: 364
- Relasi alumni-position: 613

## Evaluasi Graph

Setelah import Neo4j, jalankan:

```cypher
MATCH (n)
RETURN labels(n)[0] AS label, count(*) AS count
ORDER BY label;
```

Validasi relationship:

```cypher
MATCH ()-[r]->()
RETURN type(r) AS relationship, count(*) AS count
ORDER BY relationship;
```

## Evaluasi Text-to-Cypher

Gunakan daftar pertanyaan uji:

- Siapa saja alumni dari Airlangga University?
- Universitas mana yang memiliki alumni paling banyak?
- Pekerjaan apa yang paling sering muncul?
- Siapa alumni yang memiliki employer?
- Tampilkan alumni yang menjabat sebagai minister.

Kriteria:

- Query hanya memakai schema aktual.
- Query read-only.
- Query memiliki `LIMIT` jika hasil bisa banyak.
- Jawaban sesuai hasil retrieval.

## Evaluasi Graph Machine Learning

Kriteria:

- Proyeksi GDS berhasil dibuat.
- Louvain menulis `clusterId`.
- FastRP menulis `embedding`.
- KNN membuat relationship `MIRIP_DENGAN`.
- Similarity yang muncul dapat dijelaskan dari koneksi graph.
