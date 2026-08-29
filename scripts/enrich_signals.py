from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

# Allow direct execution from a checkout without requiring an editable install.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stock_research.data import normalize_symbol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将行业知识库上下文附加到信号表")
    parser.add_argument("--signals", required=True)
    parser.add_argument("--companies", required=True)
    parser.add_argument("--industries", required=True)
    parser.add_argument("--output", default="outputs/signals-industry.csv")
    return parser


def _split(value: object) -> list[str]:
    if value is None or pd.isna(value):
        return []
    return [part.strip() for part in str(value).split(";") if part.strip()]


def enrich_signals(
    signals: pd.DataFrame, companies: pd.DataFrame, industries: pd.DataFrame
) -> pd.DataFrame:
    required_signals = {"symbol"}
    required_companies = {"security_symbol", "related_industries"}
    required_industries = {"id", "title", "classification_code", "status", "confidence"}
    for required, frame, label in (
        (required_signals, signals, "signals"),
        (required_companies, companies, "companies"),
        (required_industries, industries, "industries"),
    ):
        missing = required - set(frame.columns)
        if missing:
            raise ValueError(f"{label} 缺少字段: {sorted(missing)}")

    company_rows: list[dict[str, str]] = []
    for row in companies.to_dict("records"):
        symbol = str(row.get("security_symbol", "")).strip()
        if not symbol:
            continue
        company_rows.append(
            {
                "symbol": normalize_symbol(symbol),
                "company_id": str(row.get("id", "")),
                "company_title": str(row.get("title", "")),
                "related_industries": str(row.get("related_industries", "")),
                "company_status": str(row.get("status", "")),
                "company_confidence": str(row.get("confidence", "")),
                "company_source_refs": str(row.get("source_refs", "")),
            }
        )
    company_frame = pd.DataFrame(
        company_rows,
        columns=[
            "symbol",
            "company_id",
            "company_title",
            "related_industries",
            "company_status",
            "company_confidence",
            "company_source_refs",
        ],
    )
    if not company_frame.empty and company_frame["symbol"].duplicated().any():
        raise ValueError("companies 存在重复 security_symbol")

    industry_by_title: dict[str, dict[str, str]] = {}
    for row in industries.to_dict("records"):
        title = str(row.get("title", "")).strip()
        if title in industry_by_title:
            raise ValueError(f"industries 存在重复 title: {title}")
        industry_by_title[title] = {
            "id": str(row.get("id", "")),
            "title": title,
            "classification_code": str(row.get("classification_code", "")),
            "status": str(row.get("status", "")),
            "confidence": str(row.get("confidence", "")),
        }

    enriched = signals.copy()
    enriched["symbol"] = enriched["symbol"].map(normalize_symbol)
    if not company_frame.empty:
        enriched = enriched.merge(company_frame, on="symbol", how="left", validate="many_to_one")
    else:
        for column in company_frame.columns:
            if column != "symbol":
                enriched[column] = ""

    industry_columns = {
        "industry_ids": [],
        "industry_titles": [],
        "industry_classification_codes": [],
        "industry_statuses": [],
        "industry_confidences": [],
    }
    for related in enriched["related_industries"].fillna(""):
        matches = [
            industry_by_title[title] for title in _split(related) if title in industry_by_title
        ]
        industry_columns["industry_ids"].append(";".join(item["id"] for item in matches))
        industry_columns["industry_titles"].append(";".join(item["title"] for item in matches))
        industry_columns["industry_classification_codes"].append(
            ";".join(item["classification_code"] for item in matches if item["classification_code"])
        )
        industry_columns["industry_statuses"].append(";".join(item["status"] for item in matches))
        industry_columns["industry_confidences"].append(
            ";".join(item["confidence"] for item in matches)
        )
    for column, values in industry_columns.items():
        enriched[column] = values
    return enriched


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    result = enrich_signals(
        pd.read_csv(Path(args.signals)),
        pd.read_csv(Path(args.companies)),
        pd.read_csv(Path(args.industries)),
    )
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, index=False)
    print(
        f"rows={len(result)} matched_companies={int(result['company_id'].notna().sum())} "
        f"output={output}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
