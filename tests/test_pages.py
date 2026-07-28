import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory


ANALYSIS_FIELDS = [
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


class PagesTests(unittest.TestCase):
    def test_build_pages_publishes_analysis_without_raw_payloads(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        with TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "direction"
            output_dir = root / "site"
            data_dir.mkdir()
            record = {
                "as_of_date": "2026-07-27",
                "name": "脑机接口",
                "canonical_name": "脑机接口",
                "evidence_level": "cross_source",
                "lifecycle": "multi_source_current",
                "evidence_count": 2,
                "source_families": "kaipan,ths",
                "providers": "plate-rotation-skill",
                "universes": "plate",
                "best_rank": 1,
                "consensus_rank_score": 0.8,
                "plate_persistence_ratio": 0.0,
                "plate_appearance_days": 2,
                "quality_notes": "",
                "evidence_json": "[]",
            }
            for name in ("direction_analysis.csv", "confirmed_directions.csv"):
                with (data_dir / name).open("w", encoding="utf-8", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=ANALYSIS_FIELDS)
                    writer.writeheader()
                    writer.writerow(record)
            (data_dir / "direction_evidence.csv").write_text(
                "name,source_family\n脑机接口,ths\n", encoding="utf-8"
            )
            (data_dir / "summary.md").write_text("# 测试摘要\n", encoding="utf-8")
            (data_dir / "manifest.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-07-28T10:00:00+08:00",
                        "as_of_date": "2026-07-27",
                        "as_of_date_quality": "source_reported",
                        "parameters": {"scope": "complete_current_lists"},
                        "records": {
                            "direction_evidence": 1,
                            "direction_analysis": 1,
                            "confirmed_directions": 1,
                        },
                        "source_status": {
                            "plate_rotation_ths": {"ok": True, "rows": 1}
                        },
                        "fork_commits": {"stock_research": "abc123"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            raw_dir = data_dir / "raw"
            raw_dir.mkdir()
            (raw_dir / "private-upstream.json").write_text("{}", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "build_direction_pages.py"),
                    "--data-dir",
                    str(data_dir),
                    "--output-dir",
                    str(output_dir),
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertTrue((output_dir / "index.html").is_file())
            self.assertTrue((output_dir / ".nojekyll").is_file())
            self.assertFalse((output_dir / "raw").exists())
            self.assertFalse((output_dir / "data" / "private-upstream.json").exists())
            dashboard = json.loads(
                (output_dir / "data" / "dashboard.json").read_text(encoding="utf-8")
            )
            self.assertEqual(dashboard["records"]["direction_evidence"], 1)
            self.assertEqual(dashboard["analysis"][0]["name"], "脑机接口")
            self.assertEqual(dashboard["analysis"][0]["evidence_count"], 2)

            failed = subprocess.run(
                [
                    sys.executable,
                    str(project_root / "scripts" / "build_direction_pages.py"),
                    "--data-dir",
                    str(data_dir),
                    "--output-dir",
                    str(root / "complete-only"),
                    "--require-complete",
                ],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )
            self.assertNotEqual(failed.returncode, 0)
            self.assertIn("incomplete data", failed.stderr)


if __name__ == "__main__":
    unittest.main()
