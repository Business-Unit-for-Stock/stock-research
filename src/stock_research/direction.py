from __future__ import annotations

import json
import math
import re
import unicodedata
from typing import Any

import pandas as pd


DIRECTION_COLUMNS = [
    "as_of_date",
    "date_quality",
    "fetched_at",
    "provider",
    "source_family",
    "universe",
    "code",
    "name",
    "canonical_name",
    "rank",
    "list_size",
    "rank_score",
    "metric",
    "metric_value",
    "metric_unit",
    "color",
    "leader",
    "up_count",
    "down_count",
    "raw_file",
    "source_commit",
]


ANALYSIS_COLUMNS = [
    "as_of_date",
    "name",
    "canonical_name",
    "evidence_level",
    "lifecycle",
    "evidence_count",
    "source_families",
    "providers",
    "universes",
    "best_rank",
    "consensus_rank_score",
    "plate_persistence_ratio",
    "plate_appearance_days",
    "quality_notes",
    "evidence_json",
]


def canonical_direction_name(value: Any) -> str:
    """Normalize names only enough for conservative cross-source matching."""
    text = unicodedata.normalize("NFKC", str(value or "")).strip().casefold()
    text = re.sub(r"[\s·•・_\-/]+", "", text)
    text = text.strip("()（）[]【】")
    for suffix in ("概念板块", "行业板块", "概念", "板块", "行业"):
        if text.endswith(suffix) and len(text) > len(suffix) + 1:
            text = text[: -len(suffix)]
            break
    return text


def _number(value: Any) -> float | None:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, str):
        value = value.strip().replace(",", "").removesuffix("%")
        if not value or value in {"-", "--", "None", "null"}:
            return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _integer(value: Any, default: int | None = None) -> int | None:
    number = _number(value)
    return int(number) if number is not None else default


def _first(record: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        if key in record and record[key] is not None:
            return record[key]
    return default


def _rank_score(rank: int, list_size: int) -> float:
    if rank <= 0 or list_size <= 0:
        return 0.0
    return round(max(0.0, min(1.0, (list_size - rank + 1) / list_size)), 6)


def normalize_akshare_boards(
    records: list[dict[str, Any]],
    *,
    universe: str,
    as_of_date: str,
    date_quality: str,
    fetched_at: str,
    source_commit: str,
    raw_file: str,
    top_n: int,
) -> pd.DataFrame:
    """Normalize AKShare's Eastmoney industry/concept ranking snapshot."""
    normalized: list[dict[str, Any]] = []
    for index, record in enumerate(records, start=1):
        rank = _integer(_first(record, "排名", "rank"), index) or index
        if rank > top_n:
            continue
        name = str(_first(record, "板块名称", "name", default="")).strip()
        if not name:
            continue
        change_pct = _number(_first(record, "涨跌幅", "change_pct"))
        normalized.append(
            {
                "as_of_date": as_of_date,
                "date_quality": date_quality,
                "fetched_at": fetched_at,
                "provider": "akshare",
                "source_family": "eastmoney",
                "universe": universe,
                "code": str(_first(record, "板块代码", "code", default="")),
                "name": name,
                "canonical_name": canonical_direction_name(name),
                "rank": rank,
                "list_size": top_n,
                "rank_score": _rank_score(rank, top_n),
                "metric": "change_pct",
                "metric_value": change_pct,
                "metric_unit": "pct",
                "color": "",
                "leader": str(_first(record, "领涨股票", "leader", default="")),
                "up_count": _integer(_first(record, "上涨家数", "up_count")),
                "down_count": _integer(_first(record, "下跌家数", "down_count")),
                "raw_file": raw_file,
                "source_commit": source_commit,
            }
        )
    return pd.DataFrame(normalized, columns=DIRECTION_COLUMNS)


def normalize_plate_rotation(
    payload: dict[str, Any],
    *,
    source: str,
    parser_module: Any,
    fetched_at: str,
    source_commit: str,
    raw_file: str,
    top_n: int,
) -> pd.DataFrame:
    """Normalize the verified latest-day plate list and preserve source units."""
    dates = parser_module.parse_plate_rotat_dates(payload)
    normalized: list[dict[str, Any]] = []
    metric = "change_pct" if source == "ths" else "strength_score"
    unit = "pct" if source == "ths" else "score"
    if not dates:
        return pd.DataFrame(columns=DIRECTION_COLUMNS)
    for record in parser_module.parse_plate_rotat(payload, source=source)[:top_n]:
        rank = _integer(record.get("rank"))
        name = str(record.get("name") or "").strip()
        if rank is None or not name:
            continue
        normalized.append(
            {
                "as_of_date": dates[0],
                "date_quality": "source_reported",
                "fetched_at": fetched_at,
                "provider": "plate-rotation-skill",
                "source_family": source,
                "universe": "plate",
                "code": str(record.get("code") or ""),
                "name": name,
                "canonical_name": canonical_direction_name(name),
                "rank": rank,
                "list_size": top_n,
                "rank_score": _rank_score(rank, top_n),
                "metric": metric,
                "metric_value": _number(record.get("value")),
                "metric_unit": unit,
                "color": str(record.get("color") or ""),
                "leader": "",
                "up_count": None,
                "down_count": None,
                "raw_file": raw_file,
                "source_commit": source_commit,
            }
        )
    return pd.DataFrame(normalized, columns=DIRECTION_COLUMNS)


def latest_source_reported_date(frame: pd.DataFrame) -> str | None:
    if frame.empty or "as_of_date" not in frame:
        return None
    reported = frame.loc[frame["date_quality"] == "source_reported", "as_of_date"]
    values = [str(value) for value in reported.dropna().tolist() if str(value)]
    return max(values) if values else None


def build_direction_analysis(
    frame: pd.DataFrame,
    *,
    as_of_date: str | None = None,
) -> pd.DataFrame:
    """Build rank-based evidence without comparing heterogeneous raw metrics."""
    if frame.empty:
        return pd.DataFrame(columns=ANALYSIS_COLUMNS)
    target_date = as_of_date or str(frame["as_of_date"].max())
    current_all = frame[frame["as_of_date"].astype(str) == target_date].copy()
    if current_all.empty:
        return pd.DataFrame(columns=ANALYSIS_COLUMNS)

    # A source family contributes at most one vote, even when one provider emits
    # both industry and concept rows with the same normalized name.
    current = current_all.sort_values(["canonical_name", "source_family", "rank"])
    current = current.drop_duplicates(["canonical_name", "source_family"], keep="first")

    plate = frame[frame["source_family"].isin(["ths", "kaipan"])].copy()
    plate_dates = {
        family: set(group["as_of_date"].astype(str))
        for family, group in plate.groupby("source_family")
    }

    output: list[dict[str, Any]] = []
    for canonical_name, group in current.groupby("canonical_name", sort=False):
        group = group.sort_values(["rank", "source_family"])
        all_group = current_all[current_all["canonical_name"] == canonical_name]
        names = [str(value) for value in all_group["name"].dropna().unique()]
        families = sorted(str(value) for value in group["source_family"].unique())
        providers = sorted(str(value) for value in group["provider"].unique())
        universes = sorted(str(value) for value in all_group["universe"].unique())

        history = plate[plate["canonical_name"] == canonical_name]
        ratios: list[float] = []
        appearance_slots = 0
        for family, family_history in history.groupby("source_family"):
            observed_dates = plate_dates.get(str(family), set())
            appeared_dates = set(family_history["as_of_date"].astype(str))
            appearance_slots += len(appeared_dates)
            if len(observed_dates) >= 5:
                ratios.append(len(appeared_dates) / len(observed_dates))
        persistence = max(ratios, default=0.0)

        evidence_count = len(families)
        if evidence_count >= 2 and persistence >= 0.5:
            lifecycle = "multi_source_persistent"
        elif evidence_count >= 2:
            lifecycle = "multi_source_current"
        elif persistence >= 0.5:
            lifecycle = "single_source_persistent"
        else:
            lifecycle = "single_source_current"

        notes: list[str] = []
        if len(names) > 1:
            notes.append("normalized_name_match")
        if len(universes) > 1:
            notes.append("mixed_universe")
        if history.empty:
            notes.append("no_plate_history")

        evidence = []
        for row in group.itertuples(index=False):
            evidence.append(
                {
                    "source": row.source_family,
                    "provider": row.provider,
                    "universe": row.universe,
                    "name": row.name,
                    "rank": int(row.rank),
                    "metric": row.metric,
                    "value": None if pd.isna(row.metric_value) else float(row.metric_value),
                    "unit": row.metric_unit,
                }
            )

        output.append(
            {
                "as_of_date": target_date,
                "name": names[0] if names else canonical_name,
                "canonical_name": canonical_name,
                "evidence_level": "cross_source" if evidence_count >= 2 else "single_source",
                "lifecycle": lifecycle,
                "evidence_count": evidence_count,
                "source_families": ",".join(families),
                "providers": ",".join(providers),
                "universes": ",".join(universes),
                "best_rank": int(group["rank"].min()),
                "consensus_rank_score": round(float(group["rank_score"].mean()), 6),
                "plate_persistence_ratio": round(persistence, 6),
                "plate_appearance_days": appearance_slots,
                "quality_notes": ",".join(notes),
                "evidence_json": json.dumps(evidence, ensure_ascii=False, separators=(",", ":")),
            }
        )

    result = pd.DataFrame(output, columns=ANALYSIS_COLUMNS)
    return result.sort_values(
        ["evidence_count", "consensus_rank_score", "best_rank"],
        ascending=[False, False, True],
    ).reset_index(drop=True)
