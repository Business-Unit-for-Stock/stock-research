"""Import a private Obsidian industry knowledge base as structured context.

The importer intentionally exports frontmatter and source references only.  It
does not copy note bodies, attachments, credentials, or private research prose
into the research artifacts.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

from .data import normalize_symbol


class IndustryKBError(ValueError):
    """Raised when a knowledge-base export violates the integration contract."""


INDUSTRY_COLUMNS = [
    "id",
    "title",
    "status",
    "primary_sector",
    "classification_system",
    "classification_code",
    "parent_industry",
    "research_domains",
    "related_chains",
    "related_tracks",
    "as_of",
    "updated",
    "review_due",
    "review_cycle",
    "confidence",
    "source_refs",
    "source_path",
]

COMPANY_COLUMNS = [
    "id",
    "title",
    "status",
    "entity_kind",
    "security_symbol",
    "related_industries",
    "related_chains",
    "primary_region",
    "as_of",
    "updated",
    "review_due",
    "review_cycle",
    "confidence",
    "source_refs",
    "source_path",
]

ALLOWED_STATUS = {"draft", "to-verify", "active", "stale", "archived"}
ALLOWED_CONFIDENCE = {"low", "medium", "high"}
_WIKILINK_RE = re.compile(r"\[\[([^\]|#]+)(?:#[^\]|]+)?(?:\|[^\]]+)?\]\]")
_SECURITY_CODE_RE = re.compile(
    r"证券代码\s*[:：]\s*(?P<code>\d{6})(?:\.(?P<exchange>XSHG|XSHE|XBSE|SH|SZ|BJ))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class IndustrySnapshot:
    """Structured records extracted from an Obsidian vault."""

    industries: pd.DataFrame
    companies: pd.DataFrame
    files: list[str]


def _load_yaml_frontmatter(text: str, path: Path) -> dict[str, Any]:
    if not text.startswith("---"):
        raise IndustryKBError(f"缺少 YAML frontmatter: {path}")
    lines = text.splitlines()
    try:
        end = next(index for index in range(1, len(lines)) if lines[index].strip() == "---")
    except StopIteration as exc:
        raise IndustryKBError(f"frontmatter 未闭合: {path}") from exc
    try:
        import yaml

        data = yaml.safe_load("\n".join(lines[1:end]))
    except ImportError as exc:  # pragma: no cover - dependency is exercised by CI extra
        raise IndustryKBError("解析行业知识库需要 PyYAML，请安装 a-share-research[industry]") from exc
    except Exception as exc:
        raise IndustryKBError(f"无法解析 frontmatter: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise IndustryKBError(f"frontmatter 必须是对象: {path}")
    return data


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple, set)):
        return ""
    return str(value).strip()


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    values = value if isinstance(value, (list, tuple, set)) else [value]
    return [str(item).strip() for item in values if str(item).strip()]


def _join_values(value: Any) -> str:
    return ";".join(_as_list(value))


def _wikilink_titles(value: Any) -> str:
    titles: list[str] = []
    for item in _as_list(value):
        match = _WIKILINK_RE.fullmatch(item.strip())
        titles.append((match.group(1) if match else item).strip())
    return ";".join(dict.fromkeys(title for title in titles if title))


def _extract_source_refs(text: str) -> str:
    refs = _WIKILINK_RE.findall(text)
    source_refs = [ref.strip() for ref in refs if ref.strip().upper().startswith("SRC-")]
    return ";".join(dict.fromkeys(source_refs))


def _extract_security_symbol(metadata: dict[str, Any], text: str, path: Path) -> str:
    explicit = _as_text(metadata.get("security_symbol"))
    if explicit:
        try:
            return normalize_symbol(explicit)
        except Exception as exc:
            raise IndustryKBError(f"security_symbol 无法识别: {path}: {explicit!r}") from exc

    code = _as_text(metadata.get("security_code"))
    exchange = _as_text(metadata.get("security_exchange"))
    if code:
        candidate = f"{code}.{exchange}" if exchange else code
        try:
            return normalize_symbol(candidate)
        except Exception as exc:
            raise IndustryKBError(f"security_code 无法识别: {path}: {candidate!r}") from exc

    match = _SECURITY_CODE_RE.search(text)
    if not match:
        return ""
    candidate = match.group("code")
    if match.group("exchange"):
        candidate = f"{candidate}.{match.group('exchange')}"
    try:
        return normalize_symbol(candidate)
    except Exception as exc:
        raise IndustryKBError(f"正文中的证券代码无法识别: {path}: {candidate!r}") from exc


def _validate_common(metadata: dict[str, Any], path: Path) -> tuple[str, str]:
    record_id = _as_text(metadata.get("id"))
    title = _as_text(metadata.get("title"))
    if not record_id or not title:
        raise IndustryKBError(f"记录缺少 id/title: {path}")
    status = _as_text(metadata.get("status")) or "draft"
    confidence = _as_text(metadata.get("confidence")) or "low"
    if status not in ALLOWED_STATUS:
        raise IndustryKBError(f"不支持的 status {status!r}: {path}")
    if confidence not in ALLOWED_CONFIDENCE:
        raise IndustryKBError(f"不支持的 confidence {confidence!r}: {path}")
    return record_id, title


def _parse_file(path: Path) -> tuple[str, dict[str, Any], str]:
    text = path.read_text(encoding="utf-8")
    metadata = _load_yaml_frontmatter(text, path)
    record_type = _as_text(metadata.get("type"))
    return record_type, metadata, text


def _industry_record(
    metadata: dict[str, Any], text: str, path: Path, source_path: str
) -> dict[str, str]:
    record_id, title = _validate_common(metadata, path)
    return {
        "id": record_id,
        "title": title,
        "status": _as_text(metadata.get("status")) or "draft",
        "primary_sector": _as_text(metadata.get("primary_sector")),
        "classification_system": _as_text(metadata.get("classification_system")),
        "classification_code": _as_text(metadata.get("classification_code")),
        "parent_industry": _as_text(metadata.get("parent_industry")),
        "research_domains": _join_values(metadata.get("research_domains")),
        "related_chains": _wikilink_titles(metadata.get("related_chains")),
        "related_tracks": _wikilink_titles(metadata.get("related_tracks")),
        "as_of": _as_text(metadata.get("as_of")),
        "updated": _as_text(metadata.get("updated")),
        "review_due": _as_text(metadata.get("review_due")),
        "review_cycle": _as_text(metadata.get("review_cycle")),
        "confidence": _as_text(metadata.get("confidence")) or "low",
        "source_refs": _extract_source_refs(text),
        "source_path": source_path,
    }


def _company_record(
    metadata: dict[str, Any], text: str, path: Path, source_path: str
) -> dict[str, str]:
    record_id, title = _validate_common(metadata, path)
    return {
        "id": record_id,
        "title": title,
        "status": _as_text(metadata.get("status")) or "draft",
        "entity_kind": _as_text(metadata.get("entity_kind")),
        "security_symbol": _extract_security_symbol(metadata, text, path),
        "related_industries": _wikilink_titles(metadata.get("related_industries")),
        "related_chains": _wikilink_titles(metadata.get("related_chains")),
        "primary_region": _as_text(metadata.get("primary_region")),
        "as_of": _as_text(metadata.get("as_of")),
        "updated": _as_text(metadata.get("updated")),
        "review_due": _as_text(metadata.get("review_due")),
        "review_cycle": _as_text(metadata.get("review_cycle")),
        "confidence": _as_text(metadata.get("confidence")) or "low",
        "source_refs": _extract_source_refs(text),
        "source_path": source_path,
    }


def parse_industry_kb(root: str | Path) -> IndustrySnapshot:
    """Parse industry and company records from a private Obsidian vault."""
    base = Path(root)
    if not base.is_dir():
        raise IndustryKBError(f"行业知识库目录不存在: {base}")
    records: list[tuple[str, dict[str, Any], str, Path]] = []
    for path in sorted(base.rglob("*.md")):
        if any(part in {".obsidian", ".trash", "90-模板", "99-归档"} for part in path.parts):
            continue
        # README and ordinary explanatory pages are not records unless they
        # explicitly declare YAML frontmatter.
        raw_text = path.read_text(encoding="utf-8")
        if not raw_text.startswith("---"):
            continue
        record_type, metadata, text = _parse_file(path)
        if record_type in {"industry", "entity"}:
            records.append((record_type, metadata, text, path))

    industries = [
        _industry_record(metadata, text, path, path.relative_to(base).as_posix())
        for kind, metadata, text, path in records
        if kind == "industry"
    ]
    companies = [
        _company_record(metadata, text, path, path.relative_to(base).as_posix())
        for kind, metadata, text, path in records
        if kind == "entity"
    ]
    industry_frame = pd.DataFrame(industries, columns=INDUSTRY_COLUMNS)
    company_frame = pd.DataFrame(companies, columns=COMPANY_COLUMNS)
    if industry_frame["id"].duplicated().any():
        raise IndustryKBError("行业记录存在重复 id")
    if industry_frame["title"].duplicated().any():
        raise IndustryKBError("行业记录存在重复 title")
    if company_frame["id"].duplicated().any():
        raise IndustryKBError("企业记录存在重复 id")
    if company_frame["security_symbol"].replace("", pd.NA).dropna().duplicated().any():
        raise IndustryKBError("企业记录存在重复 security_symbol")
    return IndustrySnapshot(
        industry_frame,
        company_frame,
        [path.relative_to(base).as_posix() for _, _, _, path in records],
    )


def write_industry_snapshot(
    snapshot: IndustrySnapshot,
    output_dir: str | Path,
    *,
    source_repository: str = "",
    source_revision: str = "",
) -> Path:
    """Write a compact CSV snapshot and a provenance manifest."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    industries_path = output / "industry_registry.csv"
    companies_path = output / "company_registry.csv"
    snapshot.industries.to_csv(industries_path, index=False)
    snapshot.companies.to_csv(companies_path, index=False)
    digest = hashlib.sha256()
    for path in snapshot.files:
        digest.update(path.encode("utf-8"))
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_repository": source_repository,
        "source_revision": source_revision,
        "industry_count": int(len(snapshot.industries)),
        "company_count": int(len(snapshot.companies)),
        "files_scanned": len(snapshot.files),
        "file_list_digest": digest.hexdigest(),
        "content_policy": (
            "frontmatter and source references only; note bodies and attachments are excluded"
        ),
        "files": [industries_path.name, companies_path.name],
    }
    manifest_path = output / "industry-manifest.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return manifest_path
