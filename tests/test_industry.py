import tempfile
import unittest
from pathlib import Path

import pandas as pd

from stock_research.industry import IndustryKBError, parse_industry_kb, write_industry_snapshot


class IndustryTests(unittest.TestCase):
    def _make_kb(self, root: Path) -> None:
        (root / "03-行业档案").mkdir(parents=True)
        (root / ".obsidian").mkdir()
        (root / "90-模板").mkdir()
        (root / "03-行业档案" / "software.md").write_text(
            """---
type: industry
id: IND-I65
title: 软件和信息技术服务业
status: active
primary_sector: 第三产业
classification_system: GB/T 4754-2017
classification_code: I65
parent_industry: I 信息传输、软件和信息技术服务业
research_domains:
  - 软件、互联网与数字服务
related_chains:
  - "[[软件与信息技术服务产业链]]"
related_tracks: []
as_of: 2026-08-25
updated: 2026-08-25
review_cycle: yearly
review_due: 2027-07-30
confidence: medium
tags: [行业分析/行业档案]
---

# 软件和信息技术服务业

## 来源
- [[SRC-MIIT-I65-2026H1]]
""",
            encoding="utf-8",
        )
        (root / "03-行业档案" / "company.md").write_text(
            """---
type: entity
id: ENT-I65-600588
title: 用友网络
status: active
entity_kind: 上市公司
security_symbol: 600588.XSHG
related_industries:
  - "[[软件和信息技术服务业]]"
related_chains: []
primary_region: ""
as_of: 2026-08-25
updated: 2026-08-25
review_cycle: quarterly
review_due: 2026-11-25
confidence: medium
tags: [行业分析/企业]
---

# 用友网络

## 来源
- [[SRC-SSE-600588-2025AR]]
""",
            encoding="utf-8",
        )
        (root / "03-行业档案" / "ignored.md").write_text(
            "---\ntype: entity-index\nid: INDEX\ntitle: ignored\n---\n", encoding="utf-8"
        )
        (root / "90-模板" / "template.md").write_text(
            "---\ntype: industry\nid: TEMPLATE\n---\n", encoding="utf-8"
        )

    def test_parse_and_write_snapshot_excludes_note_body_and_templates(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kb"
            self._make_kb(root)
            snapshot = parse_industry_kb(root)
            self.assertEqual(len(snapshot.industries), 1)
            self.assertEqual(len(snapshot.companies), 1)
            self.assertEqual(
                snapshot.industries.iloc[0]["related_chains"], "软件与信息技术服务产业链"
            )
            self.assertEqual(snapshot.companies.iloc[0]["security_symbol"], "600588.XSHG")
            self.assertEqual(snapshot.industries.iloc[0]["source_refs"], "SRC-MIIT-I65-2026H1")
            self.assertEqual(
                snapshot.companies.iloc[0]["source_path"], "03-行业档案/company.md"
            )
            output = Path(directory) / "output"
            manifest = write_industry_snapshot(snapshot, output, source_revision="abc123")
            self.assertTrue(manifest.is_file())
            self.assertNotIn("来源", (output / "industry_registry.csv").read_text(encoding="utf-8"))
            self.assertEqual(
                pd.read_csv(output / "company_registry.csv").iloc[0]["id"], "ENT-I65-600588"
            )

    def test_body_security_code_is_supported_as_transitional_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kb"
            self._make_kb(root)
            entity = root / "03-行业档案" / "company.md"
            text = entity.read_text(encoding="utf-8").replace("security_symbol: 600588.XSHG\n", "")
            text = text.replace("# 用友网络\n", "# 用友网络\n\n证券代码：600588\n")
            entity.write_text(text, encoding="utf-8")
            snapshot = parse_industry_kb(root)
            self.assertEqual(snapshot.companies.iloc[0]["security_symbol"], "600588.XSHG")

    def test_duplicate_company_security_symbol_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "kb"
            self._make_kb(root)
            duplicate = root / "03-行业档案" / "duplicate.md"
            duplicate.write_text(
                (root / "03-行业档案" / "company.md").read_text(encoding="utf-8").replace(
                    "id: ENT-I65-600588", "id: ENT-I65-OTHER"
                ),
                encoding="utf-8",
            )
            with self.assertRaises(IndustryKBError):
                parse_industry_kb(root)


if __name__ == "__main__":
    unittest.main()
