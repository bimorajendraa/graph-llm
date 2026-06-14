# Cara Ngobrol dengan LLM

Proyek ini menyediakan CLI chat di:

```text
src/chat_cli.py
```

## 1. Siapkan API Key

Salin `.env.example` menjadi `.env`.

```powershell
copy .env.example .env
```

Isi nilai berikut:

```text
OPENROUTER_API_KEY=isi_api_key_openrouter_kamu
OPENROUTER_MODEL=nex-agi/nex-n2-pro:free
```

## 2. Chat LLM Biasa

Mode ini belum memakai Neo4j. Cocok untuk tanya umum tentang proyek,
penjelasan konsep, atau bantuan coding.

```powershell
python -m src.chat_cli --mode llm
```

## 3. Chat dengan Data Alumni

Mode ini memakai Neo4j, Text-to-Cypher, retrieval graph, lalu LLM membuat
jawaban akhir.

Jalankan Neo4j dan import data lebih dulu:

```powershell
docker compose up -d
python -m src.graph_builder --processed-dir data/processed
```

Lalu jalankan:

```powershell
python -m src.chat_cli --mode rag
```

Contoh pertanyaan:

```text
Universitas mana yang memiliki alumni paling banyak?
Siapa saja alumni dari Airlangga University?
Pekerjaan apa yang paling banyak muncul?
Tampilkan alumni yang memiliki employer.
```

Output mode Graph-RAG menampilkan:

- Query Cypher
- Data retrieval
- Jawaban akhir

## 4. Mode Cypher

Mode ini hanya menampilkan query Cypher dan data retrieval, tanpa membuat
jawaban akhir dari LLM.

```powershell
python -m src.chat_cli --mode cypher
```

## 5. Keluar dari Chat

Ketik salah satu:

```text
exit
quit
keluar
q
```
