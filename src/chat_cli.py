from __future__ import annotations

import argparse
import json
from typing import Any


DEFAULT_SYSTEM_PROMPT = """
Anda adalah asisten AlumniGraph AI.
Jawab dalam bahasa Indonesia yang jelas, ringkas, dan membantu.
Jika pengguna bertanya tentang data alumni aktual, sarankan mode Graph-RAG.
"""


def _print_header(mode: str) -> None:
    print("=" * 72)
    print(f"AlumniGraph AI Chat - mode: {mode}")
    print("Ketik 'exit', 'quit', 'keluar', atau 'q' untuk berhenti.")
    print("Ketik '/clear' untuk menghapus riwayat percakapan.")
    print("=" * 72)


def _should_exit(text: str) -> bool:
    return text.strip().casefold() in {"exit", "quit", "keluar", "q"}


def _should_clear(text: str) -> bool:
    return text.strip().casefold() in {"/clear", "clear"}


def _print_table(rows: list[dict[str, Any]]) -> None:
    """Pretty-print query result rows as a plain text table."""
    if not rows:
        print("  (tidak ada hasil)")
        return

    # Collect all column keys in insertion order
    cols: list[str] = []
    for row in rows:
        for k in row:
            if k not in cols:
                cols.append(k)

    # Calculate column widths
    widths = {c: len(c) for c in cols}
    for row in rows:
        for c in cols:
            widths[c] = max(widths[c], len(str(row.get(c, ""))))

    sep = "+-" + "-+-".join("-" * widths[c] for c in cols) + "-+"
    header = "| " + " | ".join(c.ljust(widths[c]) for c in cols) + " |"

    print(sep)
    print(header)
    print(sep)
    for row in rows:
        line = "| " + " | ".join(str(row.get(c, "")).ljust(widths[c]) for c in cols) + " |"
        print(line)
    print(sep)


def run_llm_chat(system_prompt: str = DEFAULT_SYSTEM_PROMPT) -> None:
    from src.llm_client import OpenRouterClient, build_system_message, build_user_message

    llm = OpenRouterClient()
    messages = [build_system_message(system_prompt)]
    _print_header("llm")

    while True:
        question = input("\nAnda: ").strip()
        if _should_exit(question):
            print("Selesai.")
            return
        if _should_clear(question):
            messages = [build_system_message(system_prompt)]
            print("Riwayat percakapan dihapus.")
            continue
        if not question:
            continue

        messages.append(build_user_message(question))
        try:
            answer = llm.chat(messages)
        except Exception as exc:
            print(f"\nError LLM: {exc}")
            print("Pastikan OPENROUTER_API_KEY sudah diisi di file .env.")
            continue

        messages.append({"role": "assistant", "content": answer})
        print(f"\nLLM: {answer}")


def run_rag_chat(show_rows: bool = True, stream: bool = False) -> None:
    from src.database import Neo4jConnection
    from src.graph_rag import GraphRAG

    db = Neo4jConnection()
    rag = GraphRAG(db, stream=stream)
    _print_header("rag")

    try:
        db.verify()
        alumni_count = db.run_query("MATCH (a:Alumni) RETURN count(a) AS total")
        total = alumni_count[0]["total"] if alumni_count else 0
        if total == 0:
            print(
                "\nPERINGATAN: Tidak ada node Alumni di database Neo4j saat ini.\n"
                "Jalankan import terlebih dahulu sebelum chat:\n"
                "  python -m src.graph_builder --processed-dir data/processed\n"
            )
        else:
            print(f"\nSiap! {total} alumni tersedia di graph.\n")

        while True:
            question = input("\nAnda: ").strip()
            if _should_exit(question):
                print("Selesai.")
                return
            if _should_clear(question):
                rag.conversation_manager.clear()
                print("Riwayat percakapan dihapus.")
                continue
            if not question:
                continue

            try:
                result = rag.answer(question)
            except Exception as exc:
                print(f"\nError Graph-RAG: {exc}")
                continue

            if result.get("cypher"):
                print("\nCypher:")
                print(result["cypher"])

            if show_rows and result.get("queries"):
                print("\nData retrieval:")
                for item in result["queries"]:
                    if item.get("rows"):
                        _print_table(item["rows"])
                    else:
                        print("  (tidak ada hasil untuk query ini)")

            print("\nJawaban:")
            print(result["answer"])
    finally:
        db.close()


def run_cypher_chat(show_rows: bool = True) -> None:
    from src.database import Neo4jConnection
    from src.text_to_cypher import TextToCypher

    db = Neo4jConnection()
    agent = TextToCypher(db=db)
    history: list[dict[str, str]] = []
    _print_header("cypher")

    try:
        db.verify()
        while True:
            question = input("\nAnda: ").strip()
            if _should_exit(question):
                print("Selesai.")
                return
            if _should_clear(question):
                history.clear()
                print("Riwayat percakapan dihapus.")
                continue
            if not question:
                continue

            try:
                result: dict[str, Any] = agent.ask(question, history=history)
                history.append({"role": "user", "content": question})
                if result.get("queries"):
                    query_text = "\n---\n".join(item["query"] for item in result["queries"])
                    history.append({"role": "assistant", "content": query_text})
                else:
                    history.append({"role": "assistant", "content": ""})
            except Exception as exc:
                print(f"\nError Text-to-Cypher: {exc}")
                continue

            print("\nCypher:")
            if result.get("queries"):
                for item in result["queries"]:
                    print(item["query"])
            else:
                print("<Tidak ada query>")

            if show_rows and result.get("queries"):
                print("\nData retrieval:")
                for item in result["queries"]:
                    print(f"\n  Query: {item['query'][:60]}...")
                    if item.get("rows"):
                        _print_table(item["rows"])
                    else:
                        print("  (tidak ada hasil)")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat CLI untuk AlumniGraph AI.")
    parser.add_argument(
        "--mode",
        default="rag",
        choices=("llm", "rag", "cypher"),
        help="llm = chat umum, rag = chat dengan graph, cypher = query dan data retrieval.",
    )
    parser.add_argument(
        "--hide-rows",
        action="store_true",
        help="Sembunyikan data retrieval pada mode rag/cypher.",
    )
    parser.add_argument(
        "--stream",
        action="store_true",
        help="Aktifkan streaming output token-by-token pada mode rag.",
    )
    args = parser.parse_args()

    if args.mode == "llm":
        run_llm_chat()
    elif args.mode == "rag":
        run_rag_chat(show_rows=not args.hide_rows, stream=args.stream)
    elif args.mode == "cypher":
        run_cypher_chat(show_rows=not args.hide_rows)


if __name__ == "__main__":
    main()