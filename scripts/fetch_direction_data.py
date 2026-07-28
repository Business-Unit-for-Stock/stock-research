from __future__ import annotations

import argparse
import hashlib
import importlib
import importlib.util
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stock_research.direction import (  # noqa: E402
    ANALYSIS_COLUMNS,
    DIRECTION_COLUMNS,
    build_direction_analysis,
    latest_source_reported_date,
    normalize_akshare_boards,
    normalize_plate_rotation,
)


def parser() -> argparse.ArgumentParser:
    command = argparse.ArgumentParser(
        description="调用组织 Fork 获取并标准化 A 股方向研究数据"
    )
    command.add_argument("--output-dir", default="data/direction")
    command.add_argument("--plate-repo", required=True, help="plate-rotation-skill checkout path")
    command.add_argument("--akshare-repo", required=True, help="AKShare checkout path")
    command.add_argument(
        "--a-stock-data-repo",
        default=None,
        help="a-stock-data checkout path; records the pinned interface reference",
    )
    command.add_argument("--days", type=int, default=20, choices=[10, 20, 30, 50])
    command.add_argument("--plate-timeout", type=int, default=45)
    command.add_argument("--plate-request-timeout", type=int, default=15)
    command.add_argument("--plate-max-retries", type=int, default=1)
    command.add_argument("--akshare-max-retries", type=int, default=2)
    command.add_argument("--akshare-retry-delay", type=float, default=2.0)
    command.add_argument("--skip-akshare", action="store_true", help="only collect plate data")
    return command


def git_sha(path: Path | None) -> str | None:
    if path is None or not path.exists():
        return None
    completed = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return completed.stdout.strip() if completed.returncode == 0 else None


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dataframe_records(frame: pd.DataFrame) -> list[dict]:
    return json.loads(frame.to_json(orient="records", force_ascii=False, date_format="iso"))


def fetch_akshare_frame(loader, *, max_retries: int, retry_delay: float):
    attempts = max(0, max_retries) + 1
    for attempt in range(1, attempts + 1):
        try:
            return loader(), attempt
        except Exception:  # noqa: BLE001
            if attempt >= attempts:
                raise
            time.sleep(max(0.0, retry_delay) * (2 ** (attempt - 1)))
    raise RuntimeError("AKShare retry loop ended unexpectedly")


def load_akshare_with_delay_host(loader):
    """Reuse the AKShare loader while switching only Eastmoney's request host."""
    module = importlib.import_module(loader.__module__)
    original = getattr(module, "fetch_paginated_data", None)
    if original is None:
        raise RuntimeError(f"{loader.__module__} does not expose fetch_paginated_data")

    def fetch_from_delay_host(url, *args, **kwargs):
        parsed = urlsplit(url)
        hostname = parsed.hostname or ""
        if hostname == "push2.eastmoney.com" or hostname.endswith(".push2.eastmoney.com"):
            url = urlunsplit(
                (parsed.scheme, "push2delay.eastmoney.com", parsed.path, parsed.query, parsed.fragment)
            )
        return original(url, *args, **kwargs)

    module.fetch_paginated_data = fetch_from_delay_host
    try:
        return loader()
    finally:
        module.fetch_paginated_data = original


def load_plate_parsers(plate_repo: Path):
    path = plate_repo / "scripts" / "parsers.py"
    spec = importlib.util.spec_from_file_location("organization_plate_parsers", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"无法加载 plate-rotation 解析器: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def fetch_plate_payload(
    plate_repo: Path,
    *,
    source: str,
    days: int,
    timeout_seconds: int,
    request_timeout_seconds: int,
    max_retries: int,
) -> dict:
    fetch = plate_repo / "scripts" / "fetch.py"
    completed = subprocess.run(
        [
            sys.executable,
            str(fetch),
            "main",
            "/api/getPlateRotatData",
            f"from={source}",
            f"days={days}",
            "--timeout",
            str(request_timeout_seconds),
            "--max-retries",
            str(max_retries),
            "--raw",
        ],
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or f"exit code {completed.returncode}")
    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"plate-rotation 返回非 JSON: {completed.stdout[:300]}") from exc
    if not isinstance(payload, dict):
        raise RuntimeError("plate-rotation 返回不是 JSON object")
    return payload


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_summary(
    path: Path,
    analysis: pd.DataFrame,
    source_status: dict[str, dict],
    method_references: dict[str, dict],
    *,
    evidence_rows: int,
) -> None:
    strong = analysis[analysis["strength_level"] == "multi_source_strong"]
    coverage = analysis[analysis["coverage_level"] == "multi_source_coverage"]
    lines = [
        "# 方向数据运行摘要",
        "",
        f"- 完整方向证据：{evidence_rows}",
        f"- 聚合方向候选：{len(analysis)}",
        f"- 多源强势：{len(strong)}",
        f"- 多源覆盖：{len(coverage)}",
        "- 当前处理范围：各接口完整响应（本地无 Top-N 截断）",
        "",
    ]
    lines.append("## 数据源状态")
    for name, status in source_status.items():
        state = "ok" if status.get("ok") else "failed"
        detail = status.get("error") or status.get("note") or f"rows={status.get('rows', 0)}"
        lines.append(f"- `{name}`: {state}; {detail}")
    lines.extend(["", "## 方法参考"])
    for name, reference in method_references.items():
        lines.append(
            f"- `{name}`: {reference['purpose']}; "
            f"运行时请求={'是' if reference['runtime_requests'] else '否'}"
        )
    lines.extend(["", "## 多源强势"])
    if strong.empty:
        lines.append("- 当前没有至少两个独立来源同时满足各自强势规则的方向。")
    else:
        for row in strong.itertuples(index=False):
            lines.append(
                f"- {row.name}: 强势来源={row.strong_source_families}; "
                f"覆盖来源={row.source_families}"
            )
    lines.extend(["", "## 多源覆盖（包含多源强势）"])
    if coverage.empty:
        lines.append("- 当前没有至少两个独立来源共同出现的方向。")
    else:
        for row in coverage.itertuples(index=False):
            lines.append(
                f"- {row.name}: 覆盖来源={row.source_families}; "
                f"强势来源={row.strong_source_families or '-'}"
            )
    lines.extend(
        [
            "",
            "强势按来源独立判定：同花顺/开盘啦当前精选榜的返回项视为强势；东方财富仅将"
            "榜单前 20% 且涨幅为正的方向视为强势。原始量纲不混合计算，不构成投资建议。",
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    output_dir = Path(args.output_dir)
    raw_dir = output_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    plate_repo = Path(args.plate_repo)
    akshare_repo = Path(args.akshare_repo)
    a_stock_data_repo = Path(args.a_stock_data_repo) if args.a_stock_data_repo else None
    if str(akshare_repo) not in sys.path:
        sys.path.insert(0, str(akshare_repo))
    fetched_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    retrieval_date = fetched_at[:10]
    commits = {
        "plate_rotation_skill": git_sha(plate_repo),
        "akshare": git_sha(akshare_repo),
        "a_stock_data": git_sha(a_stock_data_repo),
        "stock_research": git_sha(PROJECT_ROOT),
    }
    source_status: dict[str, dict] = {}
    method_references = {
        "a_stock_data": {
            "available": bool(commits["a_stock_data"]),
            "mode": "pinned_method_catalog",
            "commit": commits["a_stock_data"],
            "purpose": "SKILL.md 中的 44 项 A 股数据接口方法目录",
            "runtime_requests": False,
            "note": "不是可导入运行包；Workflow 仅固定版本，实际板块请求由 AKShare 执行。",
        }
    }
    frames: list[pd.DataFrame] = []

    try:
        parsers = load_plate_parsers(plate_repo)
    except Exception as exc:  # noqa: BLE001
        parsers = None
        error = f"{type(exc).__name__}: {exc}"
        source_status["plate_rotation_ths"] = {"ok": False, "error": error}
        source_status["plate_rotation_kaipan"] = {"ok": False, "error": error}

    if parsers is not None:
        for source in ("ths", "kaipan"):
            status_key = f"plate_rotation_{source}"
            raw_path = raw_dir / f"plate_rotation_{source}.json"
            try:
                payload = fetch_plate_payload(
                    plate_repo,
                    source=source,
                    days=args.days,
                    timeout_seconds=args.plate_timeout,
                    request_timeout_seconds=args.plate_request_timeout,
                    max_retries=args.plate_max_retries,
                )
                write_json(raw_path, payload)
                frame = normalize_plate_rotation(
                    payload,
                    source=source,
                    parser_module=parsers,
                    fetched_at=fetched_at,
                    source_commit=commits["plate_rotation_skill"] or "unknown",
                    raw_file=str(raw_path.relative_to(output_dir)).replace("\\", "/"),
                )
                if frame.empty:
                    raise RuntimeError("解析后没有板块记录")
                frames.append(frame)
                source_status[status_key] = {
                    "ok": True,
                    "rows": len(frame),
                    "scope": "upstream_selected_current_list",
                    "raw_file": raw_path.name,
                }
            except Exception as exc:  # noqa: BLE001
                source_status[status_key] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    plate_frame = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DIRECTION_COLUMNS)
    as_of_date = latest_source_reported_date(plate_frame) or retrieval_date
    date_quality = "aligned_to_plate" if not plate_frame.empty else "retrieval_date"

    if args.skip_akshare:
        for universe in ("industry", "concept"):
            source_status[f"akshare_{universe}"] = {
                "ok": False,
                "skipped": True,
                "note": "skipped by command argument",
            }
    else:
        try:
            import akshare as ak
        except ImportError as exc:
            for universe in ("industry", "concept"):
                source_status[f"akshare_{universe}"] = {
                    "ok": False,
                    "error": f"ImportError: {exc}",
                }
            ak = None
        if ak is not None:
            for universe, loader in (
                ("industry", ak.stock_board_industry_name_em),
                ("concept", ak.stock_board_concept_name_em),
            ):
                status_key = f"akshare_{universe}"
                raw_path = raw_dir / f"akshare_{universe}.json"
                try:
                    request_mode = "akshare_default_host"
                    try:
                        raw_frame, attempts = fetch_akshare_frame(
                            loader,
                            max_retries=args.akshare_max_retries,
                            retry_delay=args.akshare_retry_delay,
                        )
                    except Exception as primary_exc:  # noqa: BLE001
                        try:
                            raw_frame, fallback_attempts = fetch_akshare_frame(
                                lambda: load_akshare_with_delay_host(loader),
                                max_retries=args.akshare_max_retries,
                                retry_delay=args.akshare_retry_delay,
                            )
                        except Exception as fallback_exc:  # noqa: BLE001
                            raise RuntimeError(
                                f"default host failed: {type(primary_exc).__name__}: {primary_exc}; "
                                f"delay host failed: {type(fallback_exc).__name__}: {fallback_exc}"
                            ) from fallback_exc
                        attempts = args.akshare_max_retries + 1 + fallback_attempts
                        request_mode = "eastmoney_delay_host_fallback"
                    records = dataframe_records(raw_frame)
                    write_json(raw_path, records)
                    frame = normalize_akshare_boards(
                        records,
                        universe=universe,
                        as_of_date=as_of_date,
                        date_quality=date_quality,
                        fetched_at=fetched_at,
                        source_commit=commits["akshare"] or "unknown",
                        raw_file=str(raw_path.relative_to(output_dir)).replace("\\", "/"),
                    )
                    if frame.empty:
                        raise RuntimeError("标准化后没有板块记录")
                    frames.append(frame)
                    source_status[status_key] = {
                        "ok": True,
                        "rows": len(frame),
                        "attempts": attempts,
                        "request_mode": request_mode,
                        "scope": "complete_returned_list",
                        "raw_file": raw_path.name,
                    }
                except Exception as exc:  # noqa: BLE001
                    source_status[status_key] = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}

    evidence = pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=DIRECTION_COLUMNS)
    analysis = build_direction_analysis(evidence, as_of_date=as_of_date)
    multi_source_strong = analysis[analysis["strength_level"] == "multi_source_strong"].copy()
    multi_source_coverage = analysis[
        analysis["coverage_level"] == "multi_source_coverage"
    ].copy()
    evidence_path = output_dir / "direction_evidence.csv"
    analysis_path = output_dir / "direction_analysis.csv"
    strong_path = output_dir / "multi_source_strong.csv"
    coverage_path = output_dir / "multi_source_coverage.csv"
    evidence.to_csv(evidence_path, index=False, encoding="utf-8")
    analysis.to_csv(analysis_path, index=False, encoding="utf-8")
    multi_source_strong.to_csv(strong_path, index=False, encoding="utf-8")
    multi_source_coverage.to_csv(coverage_path, index=False, encoding="utf-8")
    write_summary(
        output_dir / "summary.md",
        analysis,
        source_status,
        method_references,
        evidence_rows=len(evidence),
    )

    files = {}
    for path in sorted(output_dir.rglob("*")):
        if path.is_file() and path.name != "manifest.json":
            files[str(path.relative_to(output_dir)).replace("\\", "/")] = {
                "bytes": path.stat().st_size,
                "sha256": sha256(path),
            }
    manifest = {
        "generated_at": fetched_at,
        "as_of_date": as_of_date,
        "as_of_date_quality": date_quality,
        "parameters": {
            "days": args.days,
            "scope": "complete_provider_responses",
            "plate_request_timeout": args.plate_request_timeout,
            "plate_max_retries": args.plate_max_retries,
            "akshare_max_retries": args.akshare_max_retries,
            "akshare_retry_delay": args.akshare_retry_delay,
        },
        "fork_commits": commits,
        "source_status": source_status,
        "method_references": method_references,
        "records": {
            "direction_evidence": len(evidence),
            "direction_analysis": len(analysis),
            "multi_source_strong": len(multi_source_strong),
            "multi_source_coverage": len(multi_source_coverage),
        },
        "files": files,
        "method_notes": [
            "a-stock-data is retained as a pinned interface reference because its implementation is embedded in SKILL.md.",
            "AKShare supplies the structured Eastmoney board snapshot at runtime.",
            "If Eastmoney's default push2 host fails, the same AKShare loader is retried against the official push2delay host.",
            "Multi-source coverage counts independent source families, not duplicate provider outputs.",
            "Multi-source strength requires at least two independent families to satisfy source-specific rules.",
            "THS and Kaipan responses are upstream-selected current Top10 lists; no wider anonymous reusable endpoint is currently reliable.",
            "Eastmoney strength means top 20 percent of the returned list with positive change.",
            "Raw percentage returns and strength scores are never combined or converted to a cross-source rank score.",
            "Every parseable row returned by each current interface is normalized and analyzed without local Top-N truncation.",
            "Only the latest-day plate list is normalized; the upstream historical matrix parser can misalign dates when cells are empty.",
        ],
    }
    write_json(output_dir / "manifest.json", manifest)
    print(
        f"as_of={as_of_date} evidence={len(evidence)} analysis={len(analysis)} "
        f"strong={len(multi_source_strong)} coverage={len(multi_source_coverage)}"
    )
    if evidence.empty:
        print(json.dumps(source_status, ensure_ascii=False, indent=2), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
