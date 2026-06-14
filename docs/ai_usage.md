# Penggunaan AI

Proyek ini memakai OpenRouter API untuk fitur LLM.

## Konfigurasi

Salin `.env.example` menjadi `.env`, lalu isi:

```text
OPENROUTER_API_KEY=isi-api-key-anda
OPENROUTER_MODEL=meta-llama/llama-3.1-8b-instruct:free
```

Model dapat diganti selama kompatibel dengan endpoint chat completions
OpenRouter.

## Text-to-Cypher

Text-to-Cypher menggunakan schema aktual:

- `Alumni`
- `University`
- `Occupation`
- `Employer`
- `Position`

Query yang dihasilkan divalidasi oleh `src.cypher_guard` agar hanya query
read-only yang dieksekusi.

Contoh pertanyaan:

```text
Siapa saja alumni dari Airlangga University?
Universitas mana yang memiliki alumni paling banyak?
Alumni apa saja yang bekerja sebagai singer?
```

## Graph-RAG

Graph-RAG menjalankan alur:

```text
Pertanyaan user
  -> Text-to-Cypher
  -> Neo4j retrieval
  -> LLM answer generation
  -> Query, data retrieval, dan jawaban akhir
```

Graph-RAG tidak boleh mengarang data. Jika retrieval kosong, jawaban harus
menjelaskan bahwa data tidak tersedia pada graph.
