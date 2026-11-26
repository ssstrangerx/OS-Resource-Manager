import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import main
from osrm import analysis, scheduling
from osrm.datasets import load
from osrm.logger import LOG_FILE
from osrm.validation import ValidationError, parse_int_list, require_int

HAS_BASH = shutil.which("bash") is not None and shutil.which("ps") is not None


class Integration(unittest.TestCase):
    def test_i01_full_analysis_creates_outputs(self):
        """TC-I01 Full analysis runs every module and writes the report, CSV files and traces"""
        with tempfile.TemporaryDirectory() as tmp:
            obs = analysis.run_full_analysis(tmp, quiet=True)
            out = Path(tmp)
            self.assertEqual(len(obs), 4)
            self.assertTrue((out / "analysis_report.md").exists())
            self.assertGreaterEqual(len(list((out / "csv").glob("*.csv"))), 8)
            for name in ("scheduling", "memory", "deadlock", "storage"):
                self.assertTrue((out / "traces" / f"{name}_trace.txt").exists())

    def test_i02_command_line_analysis(self):
        """TC-I02 'main.py --analyze --quiet' exits with status 0"""
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(main.main(["--analyze", "--quiet", "--output", tmp]), 0)

    def test_i03_dataset_errors(self):
        """TC-I03 Missing dataset file and broken JSON give a clear ValidationError"""
        with self.assertRaises(ValidationError):
            load("does_not_exist")
        with tempfile.TemporaryDirectory() as tmp:
            bad = Path(tmp) / "bad.json"
            bad.write_text("{ not json")
            with self.assertRaises(ValidationError):
                load(bad)

    def test_i04_validation_helpers(self):
        """TC-I04 Input parsing: commas or spaces accepted; decimals, text and booleans rejected"""
        self.assertEqual(parse_int_list("1, 2 3", "x"), [1, 2, 3])
        for bad in ("1.5", "abc", True):
            with self.assertRaises(ValidationError):
                require_int(bad, "x")
        with self.assertRaises(ValidationError):
            parse_int_list("", "x")

    def test_i05_activity_log_written(self):
        """TC-I05 Running an algorithm writes a line to logs/activity.log"""
        before = LOG_FILE.stat().st_size if LOG_FILE.exists() else 0
        scheduling.schedule([("P1", 0, 3)], "FCFS")
        self.assertGreater(LOG_FILE.stat().st_size, before)

    @unittest.skipUnless(HAS_BASH, "needs bash and ps")
    def test_i06_bash_live_import(self):
        """TC-I06 Bash: ps_to_dataset.sh builds a workload the scheduler accepts; a bad count fails"""
        script = ROOT / "scripts" / "ps_to_dataset.sh"
        ok = subprocess.run(["bash", str(script), "3"], capture_output=True, text=True, timeout=30)
        self.assertEqual(ok.returncode, 0, ok.stderr)
        data = json.loads((ROOT / "data" / "live_processes.json").read_text())
        self.assertEqual(len(data["processes"]), 3)
        scheduling.schedule(data["processes"], "RR", 2)
        bad = subprocess.run(["bash", str(script), "50"], capture_output=True, text=True, timeout=30)
        self.assertNotEqual(bad.returncode, 0)

    @unittest.skipUnless(HAS_BASH, "needs bash")
    def test_i07_bash_launcher(self):
        """TC-I07 Bash: run.sh help succeeds and an unknown command fails"""
        self.assertEqual(subprocess.run(["bash", str(ROOT / "run.sh"), "help"], capture_output=True).returncode, 0)
        self.assertNotEqual(subprocess.run(["bash", str(ROOT / "run.sh"), "nonsense"], capture_output=True).returncode, 0)

    def test_i08_menu_survives_bad_input(self):
        """TC-I08 Menu: invalid choices are re-asked and the program exits cleanly on 0"""
        feed = "\n".join(["9", "abc", "-1", "0"]) + "\n"
        run = subprocess.run([sys.executable, str(ROOT / "main.py")], input=feed, capture_output=True,
                             text=True, timeout=30, cwd=ROOT)
        self.assertEqual(run.returncode, 0)
        self.assertIn("must be at most", run.stdout)
        self.assertIn("Goodbye", run.stdout)

    def test_i09_menu_end_to_end(self):
        """TC-I09 Menu: scheduling -> sample 'mixed' -> compare all, then disk -> standard -> compare"""
        feed = "\n".join(["1", "1", "7", "3", "", "4", "1", "7", "", "0"]) + "\n"
        run = subprocess.run([sys.executable, str(ROOT / "main.py")], input=feed, capture_output=True,
                             text=True, timeout=60, cwd=ROOT)
        self.assertEqual(run.returncode, 0, run.stderr)
        self.assertIn("Algorithm comparison", run.stdout)
        self.assertIn("SSTF: 53 -> 65", run.stdout)

    def test_i10_sample_sessions_replay(self):
        """TC-I10 Every samples/*.txt session runs to 'Goodbye' with no unexpected error"""
        files = sorted((ROOT / "samples").glob("*.txt"))
        self.assertGreaterEqual(len(files), 5)
        for f in files:
            with self.subTest(sample=f.name):
                run = subprocess.run([sys.executable, str(ROOT / "main.py")], input=f.read_text(),
                                     capture_output=True, text=True, timeout=60, cwd=ROOT)
                self.assertEqual(run.returncode, 0, run.stderr)
                self.assertIn("Goodbye", run.stdout)
                self.assertNotIn("Unexpected error", run.stdout)
        bad = (ROOT / "samples" / "05_invalid_input.txt")
        run = subprocess.run([sys.executable, str(ROOT / "main.py")], input=bad.read_text(),
                             capture_output=True, text=True, timeout=60, cwd=ROOT)
        self.assertEqual(run.stdout.count("Try again"), 8)   # each of the 8 bad values is re-asked
        self.assertIn("burst time must be at least 1", run.stdout)


if __name__ == "__main__":
    unittest.main()
