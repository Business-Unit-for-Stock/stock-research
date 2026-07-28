import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from stock_research.direction import (
    build_direction_analysis,
    canonical_direction_name,
    normalize_akshare_boards,
    normalize_plate_rotation,
)


class _PlateParsers:
    @staticmethod
    def parse_plate_rotat_dates(payload):
        return payload["dates"]

    @staticmethod
    def parse_plate_rotat_matrix(payload, dates):
        return payload["matrix"]

    @staticmethod
    def parse_plate_rotat(payload, source="ths"):
        return payload["today"]


class DirectionTests(unittest.TestCase):
    def test_canonical_name_removes_only_generic_suffixes(self) -> None:
        self.assertEqual(canonical_direction_name(" F5G 概念 "), "f5g")
        self.assertEqual(canonical_direction_name("通信-板块"), "通信")
        self.assertEqual(canonical_direction_name("银行"), "银行")

    def test_akshare_snapshot_keeps_metric_unit(self) -> None:
        frame = normalize_akshare_boards(
            [
                {
                    "排名": 1,
                    "板块名称": "通信行业",
                    "板块代码": "BK0448",
                    "涨跌幅": "3.5",
                    "上涨家数": 20,
                    "下跌家数": 3,
                    "领涨股票": "示例股份",
                }
            ],
            universe="industry",
            as_of_date="2026-07-27",
            date_quality="aligned_to_plate",
            fetched_at="now",
            source_commit="abc",
            raw_file="raw/industry.json",
            top_n=20,
        )
        self.assertEqual(frame.iloc[0]["source_family"], "eastmoney")
        self.assertEqual(frame.iloc[0]["canonical_name"], "通信")
        self.assertEqual(frame.iloc[0]["metric_unit"], "pct")
        self.assertEqual(frame.iloc[0]["up_count"], 20)

    def test_plate_sources_preserve_incompatible_metrics(self) -> None:
        ths = normalize_plate_rotation(
            {
                "dates": ["2026-07-27"],
                "matrix": [],
                "today": [
                    {
                        "rank": 1,
                        "code": "886001",
                        "name": "通信概念",
                        "value": "4.2%",
                        "color": "red",
                    }
                ],
            },
            source="ths",
            parser_module=_PlateParsers,
            fetched_at="now",
            source_commit="plate",
            raw_file="raw/ths.json",
            top_n=20,
        )
        kaipan = normalize_plate_rotation(
            {
                "dates": ["2026-07-27"],
                "matrix": [],
                "today": [
                    {
                        "rank": 2,
                        "code": "801660",
                        "name": "通信板块",
                        "value": "15199",
                        "color": "red",
                    }
                ],
            },
            source="kaipan",
            parser_module=_PlateParsers,
            fetched_at="now",
            source_commit="plate",
            raw_file="raw/kaipan.json",
            top_n=20,
        )
        self.assertEqual(ths.iloc[0]["metric_unit"], "pct")
        self.assertEqual(kaipan.iloc[0]["metric_unit"], "score")

        analysis = build_direction_analysis(pd.concat([ths, kaipan], ignore_index=True))
        self.assertEqual(analysis.iloc[0]["evidence_level"], "cross_source")
        self.assertEqual(analysis.iloc[0]["evidence_count"], 2)
        self.assertEqual(analysis.iloc[0]["lifecycle"], "multi_source_current")
        self.assertNotIn("metric_value", analysis.columns)

    def test_same_source_family_only_counts_once(self) -> None:
        common = {
            "as_of_date": "2026-07-27",
            "date_quality": "retrieval_date",
            "fetched_at": "now",
            "provider": "akshare",
            "source_family": "eastmoney",
            "code": "BK1",
            "name": "通信",
            "canonical_name": "通信",
            "rank": 1,
            "list_size": 20,
            "rank_score": 1.0,
            "metric": "change_pct",
            "metric_value": 2.0,
            "metric_unit": "pct",
            "color": "",
            "leader": "",
            "up_count": None,
            "down_count": None,
            "raw_file": "raw.json",
            "source_commit": "abc",
        }
        rows = [{**common, "universe": "industry"}, {**common, "universe": "concept"}]
        analysis = build_direction_analysis(pd.DataFrame(rows))
        self.assertEqual(analysis.iloc[0]["evidence_count"], 1)
        self.assertEqual(analysis.iloc[0]["evidence_level"], "single_source")

    def test_direction_script_end_to_end_with_reused_modules(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            plate_repo = root / "plate"
            plate_scripts = plate_repo / "scripts"
            plate_scripts.mkdir(parents=True)
            (plate_scripts / "fetch.py").write_text(
                """import json, sys
source = next(value.split('=', 1)[1] for value in sys.argv if value.startswith('from='))
row = {
    'rank': 1,
    'code': '886001' if source == 'ths' else '801660',
    'name': '通信概念' if source == 'ths' else '通信板块',
    'value': '4.2%' if source == 'ths' else '15199',
    'color': 'red',
}
print(json.dumps({'dates': ['2026-07-27'], 'today': [row]}))
""",
                encoding="utf-8",
            )
            (plate_scripts / "parsers.py").write_text(
                """def parse_plate_rotat_dates(payload):
    return payload['dates']

def parse_plate_rotat(payload, source='ths'):
    return payload['today']
""",
                encoding="utf-8",
            )

            akshare_repo = root / "akshare-repo"
            package = akshare_repo / "akshare"
            package.mkdir(parents=True)
            (package / "__init__.py").write_text(
                """import pandas as pd

def _frame():
    return pd.DataFrame([{
        '排名': 1, '板块名称': '通信行业', '板块代码': 'BK0448',
        '涨跌幅': 3.5, '上涨家数': 20, '下跌家数': 3, '领涨股票': '示例股份',
    }])

def stock_board_industry_name_em():
    return _frame()

def stock_board_concept_name_em():
    return _frame()
""",
                encoding="utf-8",
            )
            a_stock_data_repo = root / "a-stock-data"
            a_stock_data_repo.mkdir()
            output = root / "output"
            environment = os.environ.copy()
            environment["PYTHONPATH"] = str(project_root / "src")
            completed = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "fetch_direction_data.py"),
                    "--output-dir",
                    str(output),
                    "--plate-repo",
                    str(plate_repo),
                    "--akshare-repo",
                    str(akshare_repo),
                    "--a-stock-data-repo",
                    str(a_stock_data_repo),
                    "--days",
                    "20",
                    "--top-n",
                    "10",
                ],
                capture_output=True,
                text=True,
                env=environment,
                timeout=30,
                check=False,
            )
            self.assertEqual(completed.returncode, 0, completed.stderr)
            confirmed = pd.read_csv(output / "confirmed_directions.csv")
            self.assertEqual(confirmed.iloc[0]["canonical_name"], "通信")
            self.assertEqual(confirmed.iloc[0]["evidence_count"], 3)
            manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["records"]["confirmed_directions"], 1)


if __name__ == "__main__":
    unittest.main()
