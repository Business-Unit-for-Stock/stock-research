import unittest

import pandas as pd

from scripts.enrich_signals import enrich_signals


class IndustryEnrichmentTests(unittest.TestCase):
    def test_enriches_company_and_industry_context_without_recommending_trades(self) -> None:
        signals = pd.DataFrame(
            [
                {"date": "2026-08-28", "symbol": "600588", "score": 0.2, "target_weight": 1.0},
                {"date": "2026-08-28", "symbol": "000001", "score": 0.1, "target_weight": 0.0},
            ]
        )
        companies = pd.DataFrame(
            [
                {
                    "id": "ENT-I65-600588",
                    "title": "用友网络",
                    "security_symbol": "600588.XSHG",
                    "related_industries": "软件和信息技术服务业",
                    "status": "active",
                    "confidence": "medium",
                    "source_refs": "SRC-SSE-600588-2025AR",
                }
            ]
        )
        industries = pd.DataFrame(
            [
                {
                    "id": "IND-I65",
                    "title": "软件和信息技术服务业",
                    "classification_code": "I65",
                    "status": "active",
                    "confidence": "medium",
                }
            ]
        )
        result = enrich_signals(signals, companies, industries)
        matched = result.iloc[0]
        unmatched = result.iloc[1]
        self.assertEqual(matched["company_id"], "ENT-I65-600588")
        self.assertEqual(matched["industry_ids"], "IND-I65")
        self.assertEqual(matched["industry_classification_codes"], "I65")
        self.assertEqual(unmatched["industry_ids"], "")
        self.assertIn("target_weight", result.columns)


if __name__ == "__main__":
    unittest.main()
