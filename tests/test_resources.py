import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from stock_research.resources import (
    ResourceCatalogError,
    load_information_sources,
    load_resource_catalog,
)


class ResourceCatalogTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = Path(__file__).resolve().parents[1] / "config" / "finance-resources.json"

    def test_catalog_loads_and_applies_production_gate(self) -> None:
        catalog = load_resource_catalog(self.path)
        self.assertEqual(catalog.snapshot_date.isoformat(), "2026-10-06")
        self.assertEqual(len(catalog.resources), 27)
        self.assertEqual(catalog.resources[0].repository, "akfamily/akshare")
        self.assertEqual(
            [resource.repository for resource in catalog.production_candidates()],
            ["akfamily/akshare"],
        )
        self.assertNotIn(
            "mementum/backtrader",
            {resource.repository for resource in catalog.active_resources()},
        )

    def test_duplicate_repository_is_rejected(self) -> None:
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        raw["repositories"].append(raw["repositories"][0])
        with TemporaryDirectory() as directory:
            path = Path(directory) / "catalog.json"
            path.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ResourceCatalogError):
                load_resource_catalog(path)

    def test_information_sources_keep_web_sources_disabled_until_reviewed(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config" / "finance-information-sources.json"
        sources = load_information_sources(path)
        self.assertGreaterEqual(len(sources), 15)
        self.assertEqual(
            {source.id for source in sources if source.enabled},
            {"akshare-market-data", "baostock-market-data", "yfinance-market-data"},
        )
        self.assertTrue(all(source.url.startswith("https://") for source in sources))

    def test_unreviewed_source_cannot_be_enabled(self) -> None:
        path = Path(__file__).resolve().parents[1] / "config" / "finance-information-sources.json"
        raw = json.loads(path.read_text(encoding="utf-8"))
        raw["sources"][3]["enabled"] = True
        with TemporaryDirectory() as directory:
            invalid = Path(directory) / "sources.json"
            invalid.write_text(json.dumps(raw), encoding="utf-8")
            with self.assertRaises(ResourceCatalogError):
                load_information_sources(invalid)


if __name__ == "__main__":
    unittest.main()
