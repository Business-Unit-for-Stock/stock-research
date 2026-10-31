"""Load and validate the finance-domain resource catalog."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any


class ResourceCatalogError(ValueError):
    """Raised when the finance resource catalog is invalid."""


@dataclass(frozen=True)
class Resource:
    repository: str
    url: str
    domain: str
    capability: str
    production_role: str
    active_as_of: date
    integration: str
    license: str | None = None


@dataclass(frozen=True)
class SourceFamily:
    id: str
    status: str
    scope: str


@dataclass(frozen=True)
class InformationSource:
    id: str
    name: str
    url: str
    source_type: str
    scope: tuple[str, ...]
    review_status: str
    enabled: bool
    notes: str


@dataclass(frozen=True)
class ResourceCatalog:
    schema_version: int
    snapshot_date: date
    stale_after_days: int
    resources: tuple[Resource, ...]
    official_source_families: tuple[SourceFamily, ...]

    def production_candidates(self) -> tuple[Resource, ...]:
        return tuple(
            resource
            for resource in self.resources
            if resource.production_role == "primary_candidate"
        )

    def active_resources(self) -> tuple[Resource, ...]:
        cutoff = self.snapshot_date.fromordinal(
            self.snapshot_date.toordinal() - self.stale_after_days
        )
        return tuple(resource for resource in self.resources if resource.active_as_of >= cutoff)


def _required_string(raw: dict[str, Any], key: str, context: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ResourceCatalogError(f"{context}.{key} must be a non-empty string")
    return value.strip()


def _parse_date(raw: dict[str, Any], key: str, context: str) -> date:
    value = _required_string(raw, key, context)
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ResourceCatalogError(f"{context}.{key} must be YYYY-MM-DD") from exc


def load_resource_catalog(path: str | Path) -> ResourceCatalog:
    """Load the catalog and reject duplicate or malformed entries."""

    catalog_path = Path(path)
    try:
        raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceCatalogError(f"cannot read resource catalog: {catalog_path}") from exc

    if not isinstance(raw, dict):
        raise ResourceCatalogError("catalog root must be an object")
    try:
        schema_version = int(raw["schema_version"])
        stale_after_days = int(raw["production_policy"]["stale_after_days"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ResourceCatalogError("catalog metadata is incomplete") from exc
    if schema_version != 1 or stale_after_days <= 0:
        raise ResourceCatalogError("unsupported schema or invalid stale_after_days")

    snapshot_date = _parse_date(raw, "snapshot_date", "catalog")
    raw_resources = raw.get("repositories")
    if not isinstance(raw_resources, list) or not raw_resources:
        raise ResourceCatalogError("repositories must be a non-empty list")

    resources: list[Resource] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_resources):
        context = f"repositories[{index}]"
        if not isinstance(item, dict):
            raise ResourceCatalogError(f"{context} must be an object")
        repository = _required_string(item, "repository", context)
        if repository in seen:
            raise ResourceCatalogError(f"duplicate repository: {repository}")
        seen.add(repository)
        resources.append(
            Resource(
                repository=repository,
                url=_required_string(item, "url", context),
                domain=_required_string(item, "domain", context),
                capability=_required_string(item, "capability", context),
                production_role=_required_string(item, "production_role", context),
                active_as_of=_parse_date(item, "active_as_of", context),
                integration=_required_string(item, "integration", context),
                license=item.get("license"),
            )
        )

    raw_families = raw.get("official_source_families", [])
    if not isinstance(raw_families, list):
        raise ResourceCatalogError("official_source_families must be a list")
    families: list[SourceFamily] = []
    family_ids: set[str] = set()
    for index, item in enumerate(raw_families):
        context = f"official_source_families[{index}]"
        if not isinstance(item, dict):
            raise ResourceCatalogError(f"{context} must be an object")
        family_id = _required_string(item, "id", context)
        if family_id in family_ids:
            raise ResourceCatalogError(f"duplicate source family: {family_id}")
        family_ids.add(family_id)
        families.append(
            SourceFamily(
                id=family_id,
                status=_required_string(item, "status", context),
                scope=_required_string(item, "scope", context),
            )
        )

    return ResourceCatalog(
        schema_version=schema_version,
        snapshot_date=snapshot_date,
        stale_after_days=stale_after_days,
        resources=tuple(resources),
        official_source_families=tuple(families),
    )


def load_information_sources(path: str | Path) -> tuple[InformationSource, ...]:
    """Load source registrations without enabling unreviewed web sources."""

    source_path = Path(path)
    try:
        raw = json.loads(source_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ResourceCatalogError(f"cannot read information source registry: {source_path}") from exc
    if not isinstance(raw, dict) or raw.get("schema_version") != 1:
        raise ResourceCatalogError("unsupported information source registry")
    sources = raw.get("sources")
    if not isinstance(sources, list) or not sources:
        raise ResourceCatalogError("sources must be a non-empty list")

    result: list[InformationSource] = []
    seen: set[str] = set()
    for index, item in enumerate(sources):
        context = f"sources[{index}]"
        if not isinstance(item, dict):
            raise ResourceCatalogError(f"{context} must be an object")
        source_id = _required_string(item, "id", context)
        if source_id in seen:
            raise ResourceCatalogError(f"duplicate information source: {source_id}")
        seen.add(source_id)
        scope = item.get("scope")
        if not isinstance(scope, list) or not scope or not all(
            isinstance(value, str) and value.strip() for value in scope
        ):
            raise ResourceCatalogError(f"{context}.scope must be a non-empty string list")
        enabled = item.get("enabled")
        review_status = _required_string(item, "review_status", context)
        if not isinstance(enabled, bool):
            raise ResourceCatalogError(f"{context}.enabled must be boolean")
        if enabled and not review_status.startswith("approved"):
            raise ResourceCatalogError(f"{context} cannot enable an unreviewed source")
        result.append(
            InformationSource(
                id=source_id,
                name=_required_string(item, "name", context),
                url=_required_string(item, "url", context),
                source_type=_required_string(item, "source_type", context),
                scope=tuple(value.strip() for value in scope),
                review_status=review_status,
                enabled=enabled,
                notes=_required_string(item, "notes", context),
            )
        )
    return tuple(result)
