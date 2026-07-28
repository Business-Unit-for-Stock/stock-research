from __future__ import annotations

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PROJECT_ROOT / "pages"
PUBLIC_DATA_FILES = (
    "direction_analysis.csv",
    "direction_evidence.csv",
    "multi_source_strong.csv",
    "multi_source_coverage.csv",
    "manifest.json",
    "summary.md",
)
REQUIRED_RUNTIME_SOURCES = (
    "plate_rotation_ths",
    "plate_rotation_kaipan",
    "akshare_industry",
    "akshare_concept",
)
INTEGER_FIELDS = {"evidence_count", "strong_source_count", "plate_appearance_days"}
FLOAT_FIELDS = {"plate_persistence_ratio"}


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(description="Build the direction research Pages site")
    command.add_argument("--data-dir", default="data/direction")
    command.add_argument("--output-dir", default="build/pages")
    command.add_argument(
        "--require-complete",
        action="store_true",
        help="refuse to build when any runtime source failed",
    )
    return command


def read_csv(path: Path) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    for row in rows:
        for field in INTEGER_FIELDS:
            if field in row:
                row[field] = int(float(row[field])) if row[field] else 0
        for field in FLOAT_FIELDS:
            if field in row:
                row[field] = float(row[field]) if row[field] else 0.0
    return rows


def build_pages(
    data_dir: Path,
    output_dir: Path,
    *,
    require_complete: bool = False,
) -> dict[str, Any]:
    data_dir = data_dir.resolve()
    output_dir = output_dir.resolve()
    required = [data_dir / name for name in PUBLIC_DATA_FILES]
    required.extend(TEMPLATE_DIR / name for name in ("index.html", "styles.css", "app.js"))
    missing = [str(path) for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError("Missing Pages inputs: " + ", ".join(missing))

    manifest = json.loads((data_dir / "manifest.json").read_text(encoding="utf-8"))
    if require_complete:
        source_status = manifest.get("source_status", {})
        failed = [
            source
            for source in REQUIRED_RUNTIME_SOURCES
            if not source_status.get(source, {}).get("ok")
        ]
        if failed:
            raise RuntimeError(
                "Refusing to replace the public page with incomplete data: " + ", ".join(failed)
            )
    analysis = read_csv(data_dir / "direction_analysis.csv")
    strong = read_csv(data_dir / "multi_source_strong.csv")
    coverage = read_csv(data_dir / "multi_source_coverage.csv")
    payload = {
        "schema_version": 2,
        "generated_at": manifest.get("generated_at"),
        "as_of_date": manifest.get("as_of_date"),
        "as_of_date_quality": manifest.get("as_of_date_quality"),
        "parameters": manifest.get("parameters", {}),
        "records": manifest.get("records", {}),
        "source_status": manifest.get("source_status", {}),
        "method_references": manifest.get("method_references", {}),
        "fork_commits": manifest.get("fork_commits", {}),
        "strong": strong,
        "coverage": coverage,
        "analysis": analysis,
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    public_data_dir = output_dir / "data"
    public_data_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.js"):
        shutil.copy2(TEMPLATE_DIR / name, output_dir / name)
    for name in PUBLIC_DATA_FILES:
        shutil.copy2(data_dir / name, public_data_dir / name)
    (public_data_dir / "dashboard.json").write_text(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    (output_dir / ".nojekyll").write_text("", encoding="ascii")
    return payload


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    payload = build_pages(
        Path(args.data_dir),
        Path(args.output_dir),
        require_complete=args.require_complete,
    )
    print(
        f"pages evidence={payload['records'].get('direction_evidence', 0)} "
        f"analysis={len(payload['analysis'])} strong={len(payload['strong'])} "
        f"coverage={len(payload['coverage'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
