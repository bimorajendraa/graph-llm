# Graph Schema AlumniGraph AI

Schema ini disusun setelah Tahap 0 membaca dataset aktual dari repository:

```text
https://github.com/burhansa25/graph
```

Dataset utama yang dipakai untuk preprocessing:

```text
data/raw/normalized_alumni_dataset.csv
```

## Kolom Dataset Aktual

Kolom yang tersedia:

- `univLabel`
- `alumniLabel`
- `occupationLabel`
- `employerLabel`
- `positionLabel`
- `wiki`

Tidak ditemukan kolom `description`, `source`, `alumniId`, `clusterId`, atau
`embedding` pada CSV mentah.

## Node

### Alumni

Properti:

| Properti | Sumber |
| --- | --- |
| `alumniId` | Dibuat dari hash stabil `alumniLabel + univLabel` |
| `name` | `alumniLabel` |
| `normalizedName` | Turunan dari `alumniLabel` |
| `description` | Kosong/null karena tidak tersedia pada dataset |
| `source` | `wiki` jika tersedia, selain itu repository sumber |
| `clusterId` | Kosong sampai tahap graph machine learning |
| `embedding` | Kosong sampai tahap embedding/Graph-RAG |

### University

Properti:

| Properti | Sumber |
| --- | --- |
| `name` | `univLabel` |
| `normalizedName` | Turunan dari `univLabel` |
| `source` | Repository sumber |

### Occupation

Properti:

| Properti | Sumber |
| --- | --- |
| `name` | `occupationLabel` |
| `normalizedName` | Turunan dari `occupationLabel` |
| `source` | Repository sumber |

### Employer

Properti:

| Properti | Sumber |
| --- | --- |
| `name` | `employerLabel` |
| `normalizedName` | Turunan dari `employerLabel` |
| `source` | Repository sumber |

### Position

Properti:

| Properti | Sumber |
| --- | --- |
| `name` | `positionLabel` |
| `normalizedName` | Turunan dari `positionLabel` |
| `source` | Repository sumber |

## Relationship

Relationship yang dapat dibuat dari dataset aktual:

| Relationship | Sumber |
| --- | --- |
| `(:Alumni)-[:LULUSAN_DARI]->(:University)` | `alumniLabel`, `univLabel` |
| `(:Alumni)-[:BEKERJA_SEBAGAI]->(:Occupation)` | `alumniLabel`, `occupationLabel` |
| `(:Alumni)-[:BEKERJA_DI]->(:Employer)` | `alumniLabel`, `employerLabel` |
| `(:Alumni)-[:MENJABAT_SEBAGAI]->(:Position)` | `alumniLabel`, `positionLabel` |

Relationship `(:Alumni)-[:MIRIP_DENGAN]->(:Alumni)` tidak berasal langsung
dari CSV mentah. Relationship tersebut dibuat pada tahap graph analytics atau
graph machine learning.

## Output Preprocessing

File hasil preprocessing disimpan ke `data/processed`:

- `clean_rows.csv`
- `alumni.csv`
- `universities.csv`
- `occupations.csv`
- `employers.csv`
- `positions.csv`
- `rel_alumni_university.csv`
- `rel_alumni_occupation.csv`
- `rel_alumni_employer.csv`
- `rel_alumni_position.csv`
