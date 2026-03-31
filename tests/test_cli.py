from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parent.parent


class CliIntegrationTests(unittest.TestCase):
    def test_batch_scaffold_creates_db_and_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            temp_root = Path(tmp_dir)
            input_csv = temp_root / "catalog.csv"
            input_csv.write_text(
                "url,name\nhttps://example.com,Example\nhttps://example.org,Example Org\n",
                encoding="utf-8",
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webgrade",
                    "run",
                    "--input",
                    str(input_csv),
                    "--output",
                    str(temp_root / "output"),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            output_root = temp_root / "output"
            self.assertTrue((output_root / "webgrade.sqlite3").exists())

            batch_dirs = [path for path in output_root.iterdir() if path.is_dir()]
            self.assertEqual(len(batch_dirs), 1)
            batch_dir = batch_dirs[0]
            self.assertTrue((batch_dir / "catalog.json").exists())
            self.assertTrue((batch_dir / "catalog.xlsx").exists())
            self.assertTrue((batch_dir / "webgrade.log").exists())

            payload = json.loads((batch_dir / "catalog.json").read_text(encoding="utf-8"))
            self.assertEqual(payload["batch"]["summary"]["site_count_total"], 2)
            self.assertEqual(payload["batch"]["summary"]["site_count_partial"], 2)
            self.assertEqual(len(payload["sites"]), 2)

    def test_report_name_requires_site(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "webgrade",
                    "run",
                    "--input",
                    str(Path(tmp_dir) / "missing.csv"),
                    "--report-name",
                    "Example",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
            )
            self.assertNotEqual(completed.returncode, 0)
            self.assertIn("--report-name can only be used with --site", completed.stderr)


if __name__ == "__main__":
    unittest.main()
