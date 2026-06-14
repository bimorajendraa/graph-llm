# Analisis Dataset AlumniGraph AI

Dibuat: `2026-06-14 16:54:29`
Folder dataset: `data\raw`

## Ringkasan

- Total file CSV: 3
- Total baris: 7168
- Total kolom unik: 6

## File: `cleaned_full_data_v3.csv`

- Nama file: `cleaned_full_data_v3.csv`
- Jumlah baris: 1870
- Jumlah kolom: 5
- Duplikasi baris penuh: 74

### Nama Kolom

`univLabel`, `alumniLabel`, `occupationLabel`, `employerLabel`, `positionLabel`

### Missing Value

| Kolom | Missing | Persentase |
| --- | --- | --- |
| univLabel | 0 | 0.00% |
| alumniLabel | 0 | 0.00% |
| occupationLabel | 826 | 44.17% |
| employerLabel | 1523 | 81.44% |
| positionLabel | 811 | 43.37% |

### Contoh 5 Baris Pertama

| univLabel | alumniLabel | occupationLabel | employerLabel | positionLabel |
| --- | --- | --- | --- | --- |
| Airlangga University | Abdul Kadir Jailani | - | - | - |
| Airlangga University | Achmad Yurianto | - | - | - |
| Airlangga University | Ardi Hermawan | - | - | - |
| Airlangga University | Ari Lasso | - | - | - |
| Airlangga University | Ari Lasso | Singer, songwriter, actor | - | - |

### Catatan Kualitas Data

- Kolom dengan nilai kosong sebagian: `occupationLabel`, `employerLabel`, `positionLabel`
- Ditemukan 74 baris duplikat penuh.

## File: `merged_alumni_data.csv`

- Nama file: `merged_alumni_data.csv`
- Jumlah baris: 2649
- Jumlah kolom: 6
- Duplikasi baris penuh: 82

### Nama Kolom

`univLabel`, `alumniLabel`, `occupationLabel`, `employerLabel`, `positionLabel`, `wiki`

### Missing Value

| Kolom | Missing | Persentase |
| --- | --- | --- |
| univLabel | 0 | 0.00% |
| alumniLabel | 0 | 0.00% |
| occupationLabel | 826 | 31.18% |
| employerLabel | 1523 | 57.49% |
| positionLabel | 811 | 30.62% |
| wiki | 2239 | 84.52% |

### Contoh 5 Baris Pertama

| univLabel | alumniLabel | occupationLabel | employerLabel | positionLabel | wiki |
| --- | --- | --- | --- | --- | --- |
| Airlangga University | Abdul Kadir Jailani | - | - | - | - |
| Airlangga University | Achmad Yurianto | - | - | - | - |
| Airlangga University | Ardi Hermawan | - | - | - | - |
| Airlangga University | Ari Lasso | - | - | - | - |
| Airlangga University | Ari Lasso | Singer, songwriter, actor | - | - | - |

### Catatan Kualitas Data

- Kolom dengan nilai kosong sebagian: `occupationLabel`, `employerLabel`, `positionLabel`, `wiki`
- Ditemukan 82 baris duplikat penuh.

## File: `normalized_alumni_dataset.csv`

- Nama file: `normalized_alumni_dataset.csv`
- Jumlah baris: 2649
- Jumlah kolom: 6
- Duplikasi baris penuh: 82

### Nama Kolom

`univLabel`, `alumniLabel`, `occupationLabel`, `employerLabel`, `positionLabel`, `wiki`

### Missing Value

| Kolom | Missing | Persentase |
| --- | --- | --- |
| univLabel | 0 | 0.00% |
| alumniLabel | 0 | 0.00% |
| occupationLabel | 826 | 31.18% |
| employerLabel | 1523 | 57.49% |
| positionLabel | 812 | 30.65% |
| wiki | 2239 | 84.52% |

### Contoh 5 Baris Pertama

| univLabel | alumniLabel | occupationLabel | employerLabel | positionLabel | wiki |
| --- | --- | --- | --- | --- | --- |
| Indonesian Military Academy | A.M. Hendropriyono | - | - | - | - |
| Indonesia University of Education | Aang Hamid Suganda | - | - | - | - |
| Trisakti University | Abcandra Muhammad Akbar Supratman | - | - | - | - |
| State University of Malang | Abdul Halim Iskandar | - | - | - | - |
| Airlangga University | Abdul Kadir Jailani | - | - | - | - |

### Catatan Kualitas Data

- Kolom dengan nilai kosong sebagian: `occupationLabel`, `employerLabel`, `positionLabel`, `wiki`
- Ditemukan 82 baris duplikat penuh.

## Rekomendasi Schema Graph Awal

Rekomendasi berikut bersifat kandidat awal. Verifikasi manual tetap wajib sebelum membuat schema final.
- `Alumni.alumniId`: belum ditemukan kandidat kolom yang jelas.
- `Alumni.name`: kandidat kolom `alumniLabel`.
- `Alumni.description`: belum ditemukan kandidat kolom yang jelas.
- `Alumni.source`: kandidat kolom `wiki`.
- `University.name`: kandidat kolom `univLabel`.
- `Occupation.name`: kandidat kolom `occupationLabel`.
- `Employer.name`: kandidat kolom `employerLabel`.
- `Position.name`: kandidat kolom `positionLabel`.
- Relationship graph baru boleh dibuat jika kolom sumber dan targetnya benar-benar tersedia pada laporan ini.

## Mapping Kolom ke Schema Target

| Target Schema | Kolom Dataset Aktual | Status | Catatan |
| --- | --- | --- | --- |
| `Alumni.alumniId` | _Tidak ada_ | Perlu dibuat | Dataset tidak memiliki ID alumni eksplisit; buat ID stabil dari nama alumni setelah deduplikasi. |
| `Alumni.name` | `alumniLabel` | Tersedia | Gunakan sebagai nama alumni utama. |
| `Alumni.normalizedName` | Turunan dari `alumniLabel` | Perlu dibuat | Hasil trim, lowercase/casefold, dan penghapusan spasi berlebih. |
| `Alumni.description` | _Tidak ada_ | Opsional/null | Dataset saat ini tidak menyediakan biodata/deskripsi naratif. |
| `Alumni.source` | `wiki` | Tersedia | `wiki` dapat dipakai sebagai sumber khusus alumni bila nilainya tersedia. |
| `University.name` | `univLabel` | Tersedia | Buat node University jika nilai tidak kosong. |
| `Occupation.name` | `occupationLabel` | Tersedia sebagian | Buat node Occupation hanya untuk nilai tidak kosong. |
| `Employer.name` | `employerLabel` | Tersedia sebagian | Buat node Employer hanya untuk nilai tidak kosong. |
| `Position.name` | `positionLabel` | Tersedia sebagian | Buat node Position hanya untuk nilai tidak kosong. |

## Rekomendasi Relationship

- `(:Alumni)-[:LULUSAN_DARI]->(:University)`: dapat dibuat dari `alumniLabel` dan `univLabel` bila target tidak kosong.
- `(:Alumni)-[:BEKERJA_SEBAGAI]->(:Occupation)`: dapat dibuat dari `alumniLabel` dan `occupationLabel` bila target tidak kosong.
- `(:Alumni)-[:BEKERJA_DI]->(:Employer)`: dapat dibuat dari `alumniLabel` dan `employerLabel` bila target tidak kosong.
- `(:Alumni)-[:MENJABAT_SEBAGAI]->(:Position)`: dapat dibuat dari `alumniLabel` dan `positionLabel` bila target tidak kosong.
- `(:Alumni)-[:MIRIP_DENGAN]->(:Alumni)`: dibuat pada tahap analytics/ML, bukan dari CSV mentah.

## Keputusan Lanjutan

- [x] Kolom wajib sudah divalidasi pada tahap inspeksi awal.
- [x] Mapping kolom ke schema target sudah dibuat berdasarkan kolom aktual.
- [ ] Aturan preprocessing perlu memakai mapping aktual di atas.
- [ ] Tahap 1 boleh dimulai setelah checklist di atas selesai.
