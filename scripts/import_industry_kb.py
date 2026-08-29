from __future__ import annotations

import argparse
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from stock_research.industry import parse_industry_kb, write_industry_snapshot  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="将私有 Obsidian 行业知识库导出为结构化快照")
    parser.add_argument("--kb-root", required=True, help="industry-analysis 本地目录")
    parser.add_argument("--output-dir", default="outputs/industry")
    parser.add_argument("--source-repository", default="")
    parser.add_argument("--source-revision", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    snapshot = parse_industry_kb(args.kb_root)
    manifest = write_industry_snapshot(
        snapshot,
        args.output_dir,
        source_repository=args.source_repository,
        source_revision=args.source_revision,
    )
    print(
        f"industries={len(snapshot.industries)} companies={len(snapshot.companies)} "
        f"manifest={manifest}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
