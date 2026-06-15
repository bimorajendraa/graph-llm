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
    print("=" * 72)


def _should_exit(text: str) -> bool:
    return text.strip().casefold() in {"exit", "quit", "keluar", "q"}


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


def run_rag_chat(show_rows: bool = True) -> None:
    from src.database import Neo4jConnection
    from src.graph_rag import GraphRAG

    db = Neo4jConnection()
    rag = GraphRAG(db)
    _print_header("rag")

    try:
        db.verify()
        while True:
            question = input("\nAnda: ").strip()
            if _should_exit(question):
                print("Selesai.")
                return
            if not question:
                continue

            try:
                result = rag.answer(question)
            except Exception as exc:
                print(f"\nError Graph-RAG: {exc}")
                continue

            print("\nCypher:")
            print(result["cypher"])

            if show_rows:
                print("\nData retrieval:")
                if result.get("queries"):
                    rows_payload = [
                        {"query": item["query"], "rows": item["rows"]}
                        for item in result["queries"]
                    ]
                    print(json.dumps(rows_payload, ensure_ascii=False, indent=2))
                else:
                    print("[]")

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

            if show_rows:
                print("\nData retrieval:")
                if result.get("queries"):
                    print(json.dumps(result["queries"], ensure_ascii=False, indent=2))
                else:
                    print("[]")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Chat CLI untuk AlumniGraph AI.")
    parser.add_argument(
        "--mode",
        choices=("llm", "rag", "cypher"),
        default="llm",
        help="llm = chat umum, rag = chat dengan graph, cypher = query dan data retrieval.",
    )
    parser.add_argument(
        "--hide-rows",
        action="store_true",
        help="Sembunyikan data retrieval pada mode rag/cypher.",
    )
    args = parser.parse_args()

    if args.mode == "llm":
        run_llm_chat()
    elif args.mode == "rag":
        run_rag_chat(show_rows=not args.hide_rows)
    elif args.mode == "cypher":
        run_cypher_chat(show_rows=not args.hide_rows)


if __name__ == "__main__":
    main()
