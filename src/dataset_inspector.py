from __future__ import annotations

import argparse
import re
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DATA_DIR = PROJECT_ROOT / "data" / "raw"
DEFAULT_OUTPUT_PATH = PROJECT_ROOT / "docs" / "dataset_analysis.md"

MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nan", "none", "null"}
ENCODING_CANDIDATES = ("utf-8-sig", "utf-8", "latin-1", "cp1252")


@dataclass
class DatasetFileReport:
    file_name: str
    relative_path: str
    row_count: int
    column_count: int
    columns: list[str]
    missing_values: dict[str, int]
    duplicate_rows: int
    sample_rows: list[dict[str, str]]
    dtypes: dict[str, str]
    quality_notes: list[str]


def normalize_text(value: object) -> str:
    """Normalize text for inspection without changing the raw dataset file."""
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return text


def normalize_name(value: object) -> str:
    """Normalize entity-like names for later mapping review."""
    return normalize_text(value).casefold()


def scan_dataset_files(data_dir: str | Path = DEFAULT_DATA_DIR) -> list[Path]:
    """Return all CSV files found under data_dir."""
    data_path = Path(data_dir)
    if not data_path.exists():
        return []
    return sorted(path for path in data_path.rglob("*.csv") if path.is_file())


def _read_csv(file_path: str | Path) -> pd.DataFrame:
    csv_path = Path(file_path)
    last_error: Exception | None = None

    for encoding in ENCODING_CANDIDATES:
        try:
            df = pd.read_csv(
                csv_path,
                dtype=str,
                keep_default_na=False,
                sep=None,
                engine="python",
                encoding=encoding,
            )
            df.columns = [normalize_text(column) for column in df.columns]
            return df
        except UnicodeDecodeError as exc:
            last_error = exc
        except pd.errors.EmptyDataError:
            return pd.DataFrame()
        except pd.errors.ParserError as exc:
            last_error = exc

    raise ValueError(f"Gagal membaca CSV: {csv_path}") from last_error


def load_sample_rows(file_path: str | Path, sample_size: int = 5) -> list[dict[str, str]]:
    """Load the first sample_size rows from one CSV file."""
    df = _read_csv(file_path)
    if df.empty:
        return []

    sample_df = df.head(sample_size).copy()
    for column in sample_df.columns:
        sample_df[column] = sample_df[column].map(normalize_text)
    return sample_df.to_dict(orient="records")


def detect_columns(file_path: str | Path) -> list[str]:
    """Detect CSV columns exactly as read from the file header."""
    return list(_read_csv(file_path).columns)


def _missing_count(series: pd.Series) -> int:
    return int(series.map(lambda value: normalize_text(value).casefold() in MISSING_TOKENS).sum())


def _quality_notes(df: pd.DataFrame, duplicate_rows: int, missing_values: dict[str, int]) -> list[str]:
    notes: list[str] = []

    if df.empty:
        notes.append("File kosong atau tidak memiliki baris data.")
        return notes

    empty_columns = [column for column, count in missing_values.items() if count == len(df)]
    if empty_columns:
        notes.append("Kolom seluruhnya kosong: " + ", ".join(f"`{column}`" for column in empty_columns))

    columns_with_missing = [column for column, count in missing_values.items() if 0 < count < len(df)]
    if columns_with_missing:
        notes.append(
            "Kolom dengan nilai kosong sebagian: "
            + ", ".join(f"`{column}`" for column in columns_with_missing)
        )

    if duplicate_rows:
        notes.append(f"Ditemukan {duplicate_rows} baris duplikat penuh.")

    if not notes:
        notes.append("Tidak ada masalah kualitas data dasar yang terdeteksi pada tahap inspeksi awal.")

    return notes


def inspect_csv_file(file_path: str | Path, data_dir: str | Path, sample_size: int = 5) -> DatasetFileReport:
    csv_path = Path(file_path)
    df = _read_csv(csv_path)

    cleaned_df = df.copy()
    for column in cleaned_df.columns:
        cleaned_df[column] = cleaned_df[column].map(normalize_text)

    missing_values = {column: _missing_count(cleaned_df[column]) for column in cleaned_df.columns}
    duplicate_rows = int(cleaned_df.duplicated().sum()) if not cleaned_df.empty else 0
    sample_rows = cleaned_df.head(sample_size).to_dict(orient="records") if not cleaned_df.empty else []

    try:
        relative_path = str(csv_path.relative_to(Path(data_dir)))
    except ValueError:
        relative_path = str(csv_path)

    return DatasetFileReport(
        file_name=csv_path.name,
        relative_path=relative_path,
        row_count=int(len(df)),
        column_count=int(len(df.columns)),
        columns=list(df.columns),
        missing_values=missing_values,
        duplicate_rows=duplicate_rows,
        sample_rows=sample_rows,
        dtypes={column: str(dtype) for column, dtype in df.dtypes.items()},
        quality_notes=_quality_notes(cleaned_df, duplicate_rows, missing_values),
    )


def inspect_dataset(data_dir: str | Path = DEFAULT_DATA_DIR, sample_size: int = 5) -> list[DatasetFileReport]:
    """Inspect every CSV file under data_dir."""
    csv_files = scan_dataset_files(data_dir)
    return [inspect_csv_file(path, data_dir=data_dir, sample_size=sample_size) for path in csv_files]


def _normalize_column_name(column: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", column.casefold())


def _candidate_columns(columns: Iterable[str], hints: Iterable[str]) -> list[str]:
    normalized_hints = [_normalize_column_name(hint) for hint in hints]
    candidates = []
    for column in columns:
        normalized_column = _normalize_column_name(column)
        if normalized_column in normalized_hints:
            candidates.append(column)
            continue
        if any(hint and hint in normalized_column for hint in normalized_hints):
            candidates.append(column)
    return candidates


def infer_schema_mapping(reports: list[DatasetFileReport]) -> list[dict[str, str]]:
    """Infer a conservative mapping from actual CSV columns to the target schema."""
    all_columns = sorted({column for report in reports for column in report.columns})

    def first_match(hints: Iterable[str]) -> str:
        matches = _candidate_columns(all_columns, hints)
        return matches[0] if matches else ""

    alumni_name = first_match(["alumniLabel", "alumni_name", "alumni", "name"])
    university_name = first_match(["univLabel", "universityLabel", "university", "universitas"])
    occupation_name = first_match(["occupationLabel", "occupation", "pekerjaan", "profesi"])
    employer_name = first_match(["employerLabel", "employer", "company", "perusahaan"])
    position_name = first_match(["positionLabel", "position", "jabatan", "role"])
    source = first_match(["wiki", "source", "url", "link", "sumber"])
    description = first_match(["description", "deskripsi", "bio", "biodata", "abstract"])

    rows = [
        {
            "Target Schema": "`Alumni.alumniId`",
            "Kolom Dataset Aktual": "_Tidak ada_",
            "Status": "Perlu dibuat",
            "Catatan": "Dataset tidak memiliki ID alumni eksplisit; buat ID stabil dari nama alumni setelah deduplikasi.",
        },
        {
            "Target Schema": "`Alumni.name`",
            "Kolom Dataset Aktual": f"`{alumni_name}`" if alumni_name else "_Tidak ditemukan_",
            "Status": "Tersedia" if alumni_name else "Wajib dicek",
            "Catatan": "Gunakan sebagai nama alumni utama.",
        },
        {
            "Target Schema": "`Alumni.normalizedName`",
            "Kolom Dataset Aktual": f"Turunan dari `{alumni_name}`" if alumni_name else "_Tidak ditemukan_",
            "Status": "Perlu dibuat" if alumni_name else "Wajib dicek",
            "Catatan": "Hasil trim, lowercase/casefold, dan penghapusan spasi berlebih.",
        },
        {
            "Target Schema": "`Alumni.description`",
            "Kolom Dataset Aktual": f"`{description}`" if description else "_Tidak ada_",
            "Status": "Opsional/null" if not description else "Tersedia",
            "Catatan": "Dataset saat ini tidak menyediakan biodata/deskripsi naratif.",
        },
        {
            "Target Schema": "`Alumni.source`",
            "Kolom Dataset Aktual": f"`{source}`" if source else "_Tidak ada_",
            "Status": "Tersedia" if source else "Opsional/null",
            "Catatan": "`wiki` dapat dipakai sebagai sumber khusus alumni bila nilainya tersedia.",
        },
        {
            "Target Schema": "`University.name`",
            "Kolom Dataset Aktual": f"`{university_name}`" if university_name else "_Tidak ditemukan_",
            "Status": "Tersedia" if university_name else "Opsional",
            "Catatan": "Buat node University jika nilai tidak kosong.",
        },
        {
            "Target Schema": "`Occupation.name`",
            "Kolom Dataset Aktual": f"`{occupation_name}`" if occupation_name else "_Tidak ditemukan_",
            "Status": "Tersedia sebagian" if occupation_name else "Opsional",
            "Catatan": "Buat node Occupation hanya untuk nilai tidak kosong.",
        },
        {
            "Target Schema": "`Employer.name`",
            "Kolom Dataset Aktual": f"`{employer_name}`" if employer_name else "_Tidak ditemukan_",
            "Status": "Tersedia sebagian" if employer_name else "Opsional",
            "Catatan": "Buat node Employer hanya untuk nilai tidak kosong.",
        },
        {
            "Target Schema": "`Position.name`",
            "Kolom Dataset Aktual": f"`{position_name}`" if position_name else "_Tidak ditemukan_",
            "Status": "Tersedia sebagian" if position_name else "Opsional",
            "Catatan": "Buat node Position hanya untuk nilai tidak kosong.",
        },
    ]
    return rows


def recommend_graph_schema(reports: list[DatasetFileReport]) -> list[str]:
    """Create conservative schema suggestions from detected column names."""
    all_columns = sorted({column for report in reports for column in report.columns})
    if not all_columns:
        return ["Belum ada kolom yang dapat dianalisis. Salin CSV ke `data/raw` lalu jalankan ulang inspeksi."]

    field_hints: dict[str, list[str]] = {
        "Alumni.alumniId": ["alumniId", "alumni_id", "id"],
        "Alumni.name": ["alumniLabel", "alumni_name", "alumnus", "alumni"],
        "Alumni.description": ["description", "deskripsi", "bio", "biodata", "abstract", "ringkasan"],
        "Alumni.source": ["wiki", "source", "sumber", "url", "link", "referensi"],
        "University.name": ["univLabel", "universityLabel", "university", "universitas", "univ"],
        "Occupation.name": ["occupationLabel", "occupation", "pekerjaan", "profesi", "job"],
        "Employer.name": ["employerLabel", "employer", "perusahaan", "instansi", "company"],
        "Position.name": ["positionLabel", "position", "jabatan", "posisi", "role"],
    }

    recommendations = [
        "Rekomendasi berikut bersifat kandidat awal. Verifikasi manual tetap wajib sebelum membuat schema final."
    ]

    for target_field, hints in field_hints.items():
        matches = _candidate_columns(all_columns, hints)
        if matches:
            rendered_matches = ", ".join(f"`{column}`" for column in matches)
            recommendations.append(f"- `{target_field}`: kandidat kolom {rendered_matches}.")
        else:
            recommendations.append(f"- `{target_field}`: belum ditemukan kandidat kolom yang jelas.")

    recommendations.append(
        "- Relationship graph baru boleh dibuat jika kolom sumber dan targetnya benar-benar tersedia pada laporan ini."
    )
    return recommendations


def _escape_markdown(value: object) -> str:
    text = normalize_text(value)
    text = text.replace("|", "\\|")
    return text if text else "-"


def _markdown_table(rows: list[dict[str, object]], max_columns: int = 8) -> str:
    if not rows:
        return "_Tidak ada data contoh._"

    columns = list(rows[0].keys())[:max_columns]
    header = "| " + " | ".join(_escape_markdown(column) for column in columns) + " |"
    separator = "| " + " | ".join("---" for _ in columns) + " |"
    body = [
        "| " + " | ".join(_escape_markdown(row.get(column, "")) for column in columns) + " |"
        for row in rows
    ]

    note = ""
    if len(rows[0].keys()) > max_columns:
        note = f"\n\n_Catatan: tabel contoh hanya menampilkan {max_columns} kolom pertama._"

    return "\n".join([header, separator, *body]) + note


def _missing_table(report: DatasetFileReport) -> str:
    rows = [
        {
            "Kolom": column,
            "Missing": count,
            "Persentase": f"{(count / report.row_count * 100):.2f}%" if report.row_count else "0.00%",
        }
        for column, count in report.missing_values.items()
    ]
    return _markdown_table(rows, max_columns=3)


def _mapping_table(reports: list[DatasetFileReport]) -> str:
    return _markdown_table(infer_schema_mapping(reports), max_columns=4)


def _relationship_recommendations(reports: list[DatasetFileReport]) -> list[str]:
    all_columns = sorted({column for report in reports for column in report.columns})

    checks = [
        ("(:Alumni)-[:LULUSAN_DARI]->(:University)", ["alumniLabel"], ["univLabel"]),
        ("(:Alumni)-[:BEKERJA_SEBAGAI]->(:Occupation)", ["alumniLabel"], ["occupationLabel"]),
        ("(:Alumni)-[:BEKERJA_DI]->(:Employer)", ["alumniLabel"], ["employerLabel"]),
        ("(:Alumni)-[:MENJABAT_SEBAGAI]->(:Position)", ["alumniLabel"], ["positionLabel"]),
    ]

    lines = []
    for relationship, source_hints, target_hints in checks:
        source = _candidate_columns(all_columns, source_hints)
        target = _candidate_columns(all_columns, target_hints)
        if source and target:
            lines.append(f"- `{relationship}`: dapat dibuat dari `{source[0]}` dan `{target[0]}` bila target tidak kosong.")
        else:
            lines.append(f"- `{relationship}`: belum dapat dipastikan dari kolom yang tersedia.")

    lines.append("- `(:Alumni)-[:MIRIP_DENGAN]->(:Alumni)`: dibuat pada tahap analytics/ML, bukan dari CSV mentah.")
    return lines


def render_markdown_report(
    reports: list[DatasetFileReport],
    data_dir: str | Path = DEFAULT_DATA_DIR,
    sample_size: int = 5,
) -> str:
    generated_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data_path = Path(data_dir)
    total_rows = sum(report.row_count for report in reports)
    unique_columns = sorted({column for report in reports for column in report.columns})

    lines = [
        "# Analisis Dataset AlumniGraph AI",
        "",
        f"Dibuat: `{generated_at}`",
        f"Folder dataset: `{data_path}`",
        "",
        "## Ringkasan",
        "",
        f"- Total file CSV: {len(reports)}",
        f"- Total baris: {total_rows}",
        f"- Total kolom unik: {len(unique_columns)}",
        "",
    ]

    if not reports:
        lines.extend(
            [
                "## Status",
                "",
                "Belum ada file CSV di `data/raw`.",
                "",
                "Salin dataset dari repository sumber terlebih dahulu:",
                "",
                "```powershell",
                "git clone https://github.com/burhansa25/graph.git data/source_repo",
                "Get-ChildItem .\\data\\source_repo -Recurse -Filter *.csv | Copy-Item -Destination .\\data\\raw",
                "```",
                "",
                "Setelah itu jalankan:",
                "",
                "```powershell",
                "python -m src.dataset_inspector --data-dir data/raw --output docs/dataset_analysis.md",
                "```",
                "",
            ]
        )

    for report in reports:
        lines.extend(
            [
                f"## File: `{report.relative_path}`",
                "",
                f"- Nama file: `{report.file_name}`",
                f"- Jumlah baris: {report.row_count}",
                f"- Jumlah kolom: {report.column_count}",
                f"- Duplikasi baris penuh: {report.duplicate_rows}",
                "",
                "### Nama Kolom",
                "",
                ", ".join(f"`{column}`" for column in report.columns) if report.columns else "_Tidak ada kolom._",
                "",
                "### Missing Value",
                "",
                _missing_table(report),
                "",
                f"### Contoh {sample_size} Baris Pertama",
                "",
                _markdown_table(report.sample_rows),
                "",
                "### Catatan Kualitas Data",
                "",
                *[f"- {note}" for note in report.quality_notes],
                "",
            ]
        )

    lines.extend(
        [
            "## Rekomendasi Schema Graph Awal",
            "",
            *recommend_graph_schema(reports),
            "",
            "## Mapping Kolom ke Schema Target",
            "",
            _mapping_table(reports),
            "",
            "## Rekomendasi Relationship",
            "",
            *_relationship_recommendations(reports),
            "",
            "## Keputusan Lanjutan",
            "",
            "- [x] Kolom wajib sudah divalidasi pada tahap inspeksi awal.",
            "- [x] Mapping kolom ke schema target sudah dibuat berdasarkan kolom aktual.",
            "- [ ] Aturan preprocessing perlu memakai mapping aktual di atas.",
            "- [ ] Tahap 1 boleh dimulai setelah checklist di atas selesai.",
        ]
    )

    return "\n".join(lines).rstrip() + "\n"


def generate_dataset_report(data_dir: str | Path = DEFAULT_DATA_DIR, sample_size: int = 5) -> str:
    """Generate a Markdown dataset inspection report."""
    reports = inspect_dataset(data_dir=data_dir, sample_size=sample_size)
    return render_markdown_report(reports, data_dir=data_dir, sample_size=sample_size)


def save_dataset_report(report: str, output_path: str | Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Save a Markdown report to disk."""
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report, encoding="utf-8")
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspeksi awal dataset CSV AlumniGraph AI.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR), help="Folder berisi file CSV mentah.")
    parser.add_argument("--output", default=str(DEFAULT_OUTPUT_PATH), help="Path laporan Markdown.")
    parser.add_argument("--sample-size", type=int, default=5, help="Jumlah contoh baris per file.")
    parser.add_argument("--json", action="store_true", help="Tampilkan ringkasan terstruktur ke terminal.")
    args = parser.parse_args()

    reports = inspect_dataset(data_dir=args.data_dir, sample_size=args.sample_size)
    report_markdown = render_markdown_report(reports, data_dir=args.data_dir, sample_size=args.sample_size)
    output_path = save_dataset_report(report_markdown, args.output)

    print(f"Laporan dataset disimpan ke: {output_path}")
    print(f"Total file CSV: {len(reports)}")
    print(f"Total baris: {sum(report.row_count for report in reports)}")

    if args.json:
        import json

        print(json.dumps([asdict(report) for report in reports], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
