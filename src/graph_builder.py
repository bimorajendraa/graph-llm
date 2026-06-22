from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

from src.config import settings
from src.database import Neo4jConnection, chunked
from src.data_loader import make_stable_id
from src.entity_resolver import normalize_name, normalize_text
from src.llm_client import OpenRouterClient, build_system_message, build_user_message
from src.logger import get_logger


logger = get_logger(__name__)


CONSTRAINTS = [
    "CREATE CONSTRAINT alumni_id IF NOT EXISTS FOR (a:Alumni) REQUIRE a.alumniId IS UNIQUE",
    "CREATE CONSTRAINT university_name IF NOT EXISTS FOR (u:University) REQUIRE u.normalizedName IS UNIQUE",
    "CREATE CONSTRAINT occupation_name IF NOT EXISTS FOR (o:Occupation) REQUIRE o.normalizedName IS UNIQUE",
    "CREATE CONSTRAINT employer_name IF NOT EXISTS FOR (e:Employer) REQUIRE e.normalizedName IS UNIQUE",
    "CREATE CONSTRAINT position_name IF NOT EXISTS FOR (p:Position) REQUIRE p.normalizedName IS UNIQUE",
]

BIOGRAPHY_EXTRACTION_PROMPT = """
Anda adalah LLM Graph Builder untuk AlumniGraph AI.
Ekstrak entitas dari biodata alumni menjadi JSON valid saja.

Schema JSON:
{
  "alumni": {"name": "...", "description": "..."},
  "universities": ["..."],
  "occupations": ["..."],
  "employers": ["..."],
  "positions": ["..."]
}

Aturan:
- Gunakan null atau list kosong jika informasi tidak tersedia.
- Jangan mengarang entitas yang tidak ada pada teks.
- Jawab hanya JSON valid tanpa markdown.
"""


def read_csv_rows(path: str | Path) -> list[dict[str, str]]:
    with Path(path).open("r", encoding="utf-8", newline="") as file:
        return list(csv.DictReader(file))


def create_constraints(db: Neo4jConnection) -> None:
    for query in CONSTRAINTS:
        db.execute_write(query)


def _import_rows(db: Neo4jConnection, query: str, rows: list[dict[str, Any]], batch_size: int) -> None:
    for batch in chunked(rows, batch_size=batch_size):
        db.execute_write(query, {"rows": batch})


def import_nodes(db: Neo4jConnection, processed_dir: str | Path = settings.processed_data_dir, batch_size: int = 500) -> None:
    processed = Path(processed_dir)

    node_specs = [
        (
            "alumni.csv",
            """
            UNWIND $rows AS row
            MERGE (a:Alumni {alumniId: row.alumniId})
            SET a.name = row.name,
                a.normalizedName = row.normalizedName,
                a.description = row.description,
                a.source = row.source,
                a.clusterId = row.clusterId,
                a.embedding = row.embedding
            """,
        ),
        (
            "universities.csv",
            """
            UNWIND $rows AS row
            MERGE (u:University {normalizedName: row.normalizedName})
            SET u.name = row.name,
                u.source = row.source
            """,
        ),
        (
            "occupations.csv",
            """
            UNWIND $rows AS row
            MERGE (o:Occupation {normalizedName: row.normalizedName})
            SET o.name = row.name,
                o.source = row.source
            """,
        ),
        (
            "employers.csv",
            """
            UNWIND $rows AS row
            MERGE (e:Employer {normalizedName: row.normalizedName})
            SET e.name = row.name,
                e.source = row.source
            """,
        ),
        (
            "positions.csv",
            """
            UNWIND $rows AS row
            MERGE (p:Position {normalizedName: row.normalizedName})
            SET p.name = row.name,
                p.source = row.source
            """,
        ),
    ]

    for file_name, query in node_specs:
        rows = read_csv_rows(processed / file_name)
        logger.info("Importing %s rows from %s", len(rows), file_name)
        _import_rows(db, query, rows, batch_size)


def import_relationships(
    db: Neo4jConnection,
    processed_dir: str | Path = settings.processed_data_dir,
    batch_size: int = 500,
) -> None:
    processed = Path(processed_dir)

    relationship_specs = [
        (
            "rel_alumni_university.csv",
            """
            UNWIND $rows AS row
            MATCH (a:Alumni {alumniId: row.alumniId})
            MATCH (u:University {normalizedName: toLower(row.universityName)})
            MERGE (a)-[:LULUSAN_DARI]->(u)
            """,
        ),
        (
            "rel_alumni_occupation.csv",
            """
            UNWIND $rows AS row
            MATCH (a:Alumni {alumniId: row.alumniId})
            MATCH (o:Occupation {normalizedName: toLower(row.occupationName)})
            MERGE (a)-[:BEKERJA_SEBAGAI]->(o)
            """,
        ),
        (
            "rel_alumni_employer.csv",
            """
            UNWIND $rows AS row
            MATCH (a:Alumni {alumniId: row.alumniId})
            MATCH (e:Employer {normalizedName: toLower(row.employerName)})
            MERGE (a)-[:BEKERJA_DI]->(e)
            """,
        ),
        (
            "rel_alumni_position.csv",
            """
            UNWIND $rows AS row
            MATCH (a:Alumni {alumniId: row.alumniId})
            MATCH (p:Position {normalizedName: toLower(row.positionName)})
            MERGE (a)-[:MENJABAT_SEBAGAI]->(p)
            """,
        ),
    ]

    for file_name, query in relationship_specs:
        rows = read_csv_rows(processed / file_name)
        logger.info("Importing %s relationships from %s", len(rows), file_name)
        _import_rows(db, query, rows, batch_size)


def count_graph(db: Neo4jConnection) -> list[dict[str, Any]]:
    return db.run_query(
        """
        MATCH (n)
        WITH labels(n)[0] AS label, count(*) AS nodes
        RETURN label, nodes
        ORDER BY label
        """
    )


def extract_graph_from_biography(text: str, llm: OpenRouterClient | None = None) -> dict[str, Any]:
    client = llm or OpenRouterClient()
    response = client.chat(
        [
            build_system_message(BIOGRAPHY_EXTRACTION_PROMPT),
            build_user_message(text),
        ],
        temperature=0.0,
        max_tokens=900,
    )
    cleaned = response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(cleaned)


def upsert_extracted_biography(
    db: Neo4jConnection,
    extracted_graph: dict[str, Any],
    source: str = "llm_biography",
) -> str:
    alumni = extracted_graph.get("alumni") or {}
    alumni_name = normalize_text(alumni.get("name"))
    if not alumni_name:
        raise ValueError("Hasil ekstraksi tidak memiliki nama alumni.")

    primary_university = ""
    universities = [normalize_text(value) for value in extracted_graph.get("universities", []) if normalize_text(value)]
    if universities:
        primary_university = universities[0]

    alumni_id = make_stable_id(alumni_name, primary_university or source)
    db.execute_write(
        """
        MERGE (a:Alumni {alumniId: $alumniId})
        SET a.name = $name,
            a.normalizedName = $normalizedName,
            a.description = $description,
            a.source = $source
        """,
        {
            "alumniId": alumni_id,
            "name": alumni_name,
            "normalizedName": normalize_name(alumni_name),
            "description": normalize_text(alumni.get("description")),
            "source": source,
        },
    )

    relationship_specs = [
        ("universities", "University", "LULUSAN_DARI"),
        ("occupations", "Occupation", "BEKERJA_SEBAGAI"),
        ("employers", "Employer", "BEKERJA_DI"),
        ("positions", "Position", "MENJABAT_SEBAGAI"),
    ]

    for key, label, relationship in relationship_specs:
        for value in extracted_graph.get(key, []):
            name = normalize_text(value)
            if not name:
                continue
            db.execute_write(
                f"""
                MATCH (a:Alumni {{alumniId: $alumniId}})
                MERGE (n:{label} {{normalizedName: $normalizedName}})
                SET n.name = $name,
                    n.source = $source
                MERGE (a)-[:{relationship}]->(n)
                """,
                {
                    "alumniId": alumni_id,
                    "name": name,
                    "normalizedName": normalize_name(name),
                    "source": source,
                },
            )

    return alumni_id


def run_ml_pipeline(db: Neo4jConnection, graph_name: str = "alumniGraph") -> None:
    """Menjalankan algoritma Graph ML (Louvain & Node Similarity) di Neo4j GDS."""
    logger.info("Memulai Graph ML pipeline di Neo4j Sandbox...")
    try:
        from src.graph_ml import GraphMachineLearning
        ml = GraphMachineLearning(db)

        # 1. Bersihkan sisa grafik virtual jika ada
        try:
            db.run_query("CALL gds.graph.drop($name, false)", {"name": graph_name})
        except Exception:
            pass

        # 2. PROYEKSI GRAFIK UTUH (Dengan Mode UNDIRECTED agar jalur tetangga terbuka dua arah)
        db.run_query(
            """
            CALL gds.graph.project(
              $name,
              ['Alumni', 'University', 'Occupation', 'Employer', 'Position'],
              {
                LULUSAN_DARI: {type: 'LULUSAN_DARI', orientation: 'UNDIRECTED'},
                BEKERJA_SEBAGAI: {type: 'BEKERJA_SEBAGAI', orientation: 'UNDIRECTED'},
                BEKERJA_DI: {type: 'BEKERJA_DI', orientation: 'UNDIRECTED'},
                MENJABAT_SEBAGAI: {type: 'MENJABAT_SEBAGAI', orientation: 'UNDIRECTED'}
              }
            )
            """,
            {"name": graph_name},
        )
        logger.info("Graph projected: %s (Mode: UNDIRECTED)", graph_name)

        # 3. Jalankan Louvain Clustering (Opsional untuk komunitas)
        result_louvain = ml.write_louvain_clusters(graph_name=graph_name)
        logger.info("Louvain clusters written: %s", result_louvain)

        # 4. Jalankan Node Similarity (Menggantikan KNN lama)
        result_sim = ml.write_knn_similarity(graph_name=graph_name)
        logger.info("Node Similarity MIRIP_DENGAN relationships written: %s", result_sim)

        logger.info("Graph ML pipeline selesai sempurna. Fitur 'mirip' berbasis Jaccard siap digunakan.")
    except Exception as exc:
        logger.warning("Graph ML pipeline gagal: %s — lanjut tanpa ML.", exc)
    finally:
        # Bersihkan grafik dari memori virtual setelah selesai ditulis ke database utama
        try:
            db.run_query("CALL gds.graph.drop($name, false)", {"name": graph_name})
        except Exception:
            pass


def import_graph(processed_dir: str | Path = settings.processed_data_dir, batch_size: int = 500) -> None:
    db = Neo4jConnection()
    try:
        db.verify()
        create_constraints(db)
        import_nodes(db, processed_dir=processed_dir, batch_size=batch_size)
        import_relationships(db, processed_dir=processed_dir, batch_size=batch_size)
        logger.info("Graph counts: %s", count_graph(db))
        run_ml_pipeline(db)
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Import CSV hasil preprocessing ke Neo4j.")
    parser.add_argument("--processed-dir", default=str(settings.processed_data_dir))
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--skip-ml", action="store_true", help="Lewati Graph ML pipeline setelah import.")
    args = parser.parse_args()
    import_graph(processed_dir=args.processed_dir, batch_size=args.batch_size)


if __name__ == "__main__":
    main()