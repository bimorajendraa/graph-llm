from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"

DATASET_PRIORITY = (
    "normalized_alumni_dataset.csv",
    "merged_alumni_data.csv",
    "cleaned_full_data_v3.csv",
)

SOURCE_REPOSITORY = "https://github.com/burhansa25/graph"
MISSING_TOKENS = {"", "-", "--", "na", "n/a", "nan", "none", "null"}

REQUIRED_COLUMNS = ("univLabel", "alumniLabel")
OPTIONAL_COLUMNS = ("occupationLabel", "employerLabel", "positionLabel", "wiki")


@dataclass(frozen=True)
class ProcessedDataset:
    source_file: Path
    rows: pd.DataFrame
    alumni: pd.DataFrame
    universities: pd.DataFrame
    occupations: pd.DataFrame
    employers: pd.DataFrame
    positions: pd.DataFrame
    alumni_university: pd.DataFrame
    alumni_occupation: pd.DataFrame
    alumni_employer: pd.DataFrame
    alumni_position: pd.DataFrame


def normalize_text(value: object) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    text = re.sub(r"\s+", " ", text)
    return "" if text.casefold() in MISSING_TOKENS else text


def normalize_name(value: object) -> str:
    return normalize_text(value).casefold()


def make_stable_id(*parts: object, prefix: str = "alumni") -> str:
    raw = "||".join(normalize_name(part) for part in parts if normalize_text(part))
    digest = hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]
    return f"{prefix}-{digest}"


def find_primary_dataset(raw_dir: str | Path = RAW_DATA_DIR) -> Path:
    raw_path = Path(raw_dir)
    for file_name in DATASET_PRIORITY:
        candidate = raw_path / file_name
        if candidate.exists():
            return candidate

    csv_files = sorted(raw_path.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"Tidak ada file CSV di {raw_path}")
    return csv_files[0]


def load_raw_alumni_dataset(raw_dir: str | Path = RAW_DATA_DIR, file_name: str | None = None) -> tuple[Path, pd.DataFrame]:
    source_file = Path(raw_dir) / file_name if file_name else find_primary_dataset(raw_dir)
    df = pd.read_csv(source_file, dtype=str, keep_default_na=False)
    df.columns = [normalize_text(column) for column in df.columns]
    return source_file, df


def validate_columns(df: pd.DataFrame) -> None:
    missing_required = [column for column in REQUIRED_COLUMNS if column not in df.columns]
    if missing_required:
        missing = ", ".join(missing_required)
        raise ValueError(f"Kolom wajib tidak ditemukan: {missing}")


def clean_rows(df: pd.DataFrame) -> pd.DataFrame:
    validate_columns(df)

    cleaned = df.copy()
    for column in REQUIRED_COLUMNS + OPTIONAL_COLUMNS:
        if column not in cleaned.columns:
            cleaned[column] = ""

    selected_columns = list(REQUIRED_COLUMNS + OPTIONAL_COLUMNS)
    cleaned = cleaned[selected_columns]

    for column in selected_columns:
        cleaned[column] = cleaned[column].map(normalize_text)

    cleaned = cleaned[cleaned["alumniLabel"].ne("") & cleaned["univLabel"].ne("")]
    cleaned = cleaned.drop_duplicates().reset_index(drop=True)
    cleaned["alumniId"] = cleaned.apply(
        lambda row: make_stable_id(row["alumniLabel"], row["univLabel"]),
        axis=1,
    )
    cleaned["alumniNormalizedName"] = cleaned["alumniLabel"].map(normalize_name)
    cleaned["universityNormalizedName"] = cleaned["univLabel"].map(normalize_name)
    return cleaned


def split_entity_values(value: object, split_commas: bool = False) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []

    separators = r"[;|/]+"
    if split_commas:
        separators = r"[,;|/]+"

    values = [normalize_text(part) for part in re.split(separators, text)]
    return [value for value in values if value]


def _unique_entity_frame(values: list[str], source: str = SOURCE_REPOSITORY) -> pd.DataFrame:
    rows = sorted({normalize_text(value) for value in values if normalize_text(value)}, key=str.casefold)
    return pd.DataFrame(
        {
            "name": rows,
            "normalizedName": [normalize_name(value) for value in rows],
            "source": [source for _ in rows],
        }
    )


def _relationship_frame(rows: list[dict[str, str]], columns: list[str]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(rows).drop_duplicates().sort_values(columns).reset_index(drop=True)


def build_processed_dataset(source_file: Path, raw_df: pd.DataFrame) -> ProcessedDataset:
    rows = clean_rows(raw_df)

    alumni_rows = (
        rows[["alumniId", "alumniLabel", "alumniNormalizedName", "wiki"]]
        .drop_duplicates(subset=["alumniId"])
        .rename(columns={"alumniLabel": "name", "alumniNormalizedName": "normalizedName", "wiki": "source"})
        .sort_values(["name", "alumniId"])
        .reset_index(drop=True)
    )
    alumni_rows["description"] = ""
    alumni_rows["clusterId"] = ""
    alumni_rows["embedding"] = ""
    alumni_rows["source"] = alumni_rows["source"].map(lambda value: normalize_text(value) or SOURCE_REPOSITORY)
    alumni_rows = alumni_rows[
        ["alumniId", "name", "normalizedName", "description", "source", "clusterId", "embedding"]
    ]

    universities = _unique_entity_frame(rows["univLabel"].tolist())

    occupation_values: list[str] = []
    employer_values: list[str] = []
    position_values: list[str] = []
    alumni_occupation_rows: list[dict[str, str]] = []
    alumni_employer_rows: list[dict[str, str]] = []
    alumni_position_rows: list[dict[str, str]] = []

    for row in rows.to_dict(orient="records"):
        alumni_id = row["alumniId"]

        for occupation in split_entity_values(row.get("occupationLabel", ""), split_commas=True):
            occupation_values.append(occupation)
            alumni_occupation_rows.append({"alumniId": alumni_id, "occupationName": occupation})

        for employer in split_entity_values(row.get("employerLabel", "")):
            employer_values.append(employer)
            alumni_employer_rows.append({"alumniId": alumni_id, "employerName": employer})

        for position in split_entity_values(row.get("positionLabel", "")):
            position_values.append(position)
            alumni_position_rows.append({"alumniId": alumni_id, "positionName": position})

    alumni_university = (
        rows[["alumniId", "univLabel"]]
        .drop_duplicates()
        .rename(columns={"univLabel": "universityName"})
        .sort_values(["alumniId", "universityName"])
        .reset_index(drop=True)
    )

    return ProcessedDataset(
        source_file=source_file,
        rows=rows,
        alumni=alumni_rows,
        universities=universities,
        occupations=_unique_entity_frame(occupation_values),
        employers=_unique_entity_frame(employer_values),
        positions=_unique_entity_frame(position_values),
        alumni_university=alumni_university,
        alumni_occupation=_relationship_frame(alumni_occupation_rows, ["alumniId", "occupationName"]),
        alumni_employer=_relationship_frame(alumni_employer_rows, ["alumniId", "employerName"]),
        alumni_position=_relationship_frame(alumni_position_rows, ["alumniId", "positionName"]),
    )


def preprocess_alumni_dataset(raw_dir: str | Path = RAW_DATA_DIR, file_name: str | None = None) -> ProcessedDataset:
    source_file, raw_df = load_raw_alumni_dataset(raw_dir=raw_dir, file_name=file_name)
    return build_processed_dataset(source_file, raw_df)


def save_processed_dataset(dataset: ProcessedDataset, output_dir: str | Path = PROCESSED_DATA_DIR) -> dict[str, Path]:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    frames = {
        "clean_rows.csv": dataset.rows,
        "alumni.csv": dataset.alumni,
        "universities.csv": dataset.universities,
        "occupations.csv": dataset.occupations,
        "employers.csv": dataset.employers,
        "positions.csv": dataset.positions,
        "rel_alumni_university.csv": dataset.alumni_university,
        "rel_alumni_occupation.csv": dataset.alumni_occupation,
        "rel_alumni_employer.csv": dataset.alumni_employer,
        "rel_alumni_position.csv": dataset.alumni_position,
    }

    saved_paths: dict[str, Path] = {}
    for file_name, frame in frames.items():
        path = output_path / file_name
        frame.to_csv(path, index=False, encoding="utf-8")
        saved_paths[file_name] = path
    return saved_paths


def summarize_processed_dataset(dataset: ProcessedDataset) -> dict[str, int | str]:
    return {
        "source_file": str(dataset.source_file),
        "clean_rows": len(dataset.rows),
        "alumni": len(dataset.alumni),
        "universities": len(dataset.universities),
        "occupations": len(dataset.occupations),
        "employers": len(dataset.employers),
        "positions": len(dataset.positions),
        "rel_alumni_university": len(dataset.alumni_university),
        "rel_alumni_occupation": len(dataset.alumni_occupation),
        "rel_alumni_employer": len(dataset.alumni_employer),
        "rel_alumni_position": len(dataset.alumni_position),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Preprocess dataset alumni menjadi CSV node dan relationship.")
    parser.add_argument("--raw-dir", default=str(RAW_DATA_DIR), help="Folder CSV mentah.")
    parser.add_argument("--file-name", default=None, help="Nama file CSV utama. Kosongkan untuk auto-detect.")
    parser.add_argument("--output-dir", default=str(PROCESSED_DATA_DIR), help="Folder output CSV hasil preprocessing.")
    args = parser.parse_args()

    dataset = preprocess_alumni_dataset(raw_dir=args.raw_dir, file_name=args.file_name)
    saved_paths = save_processed_dataset(dataset, output_dir=args.output_dir)
    summary = summarize_processed_dataset(dataset)

    print("Preprocessing selesai.")
    for key, value in summary.items():
        print(f"{key}: {value}")
    print("File output:")
    for name, path in saved_paths.items():
        print(f"- {name}: {path}")


if __name__ == "__main__":
    main()
