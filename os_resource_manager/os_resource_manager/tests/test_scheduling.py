import logging
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from osrm import scheduling as s
from osrm.validation import ValidationError


def times(result):
    return {r["pid"]: (r["completion"], r["turnaround"], r["waiting"]) for r in result.rows}


class ValidCases(unittest.TestCase):
    def test_s01_fcfs_basic(self):
        """TC-S01 FCFS runs processes in arrival order"""
        r = s.schedule([("P1", 0, 5), ("P2", 1, 3), ("P3", 2, 8)], "FCFS")
        self.assertEqual(s.gantt_text(r.gantt), "| P1 0-5 | P2 5-8 | P3 8-16 |")
        self.assertEqual(r.metrics["avg_waiting"], 3.33)

    def test_s02_srtf_known_answer(self):
        """TC-S02 SRTF matches the hand-solved class problem (avg TAT 23.25, avg WT 9.5)"""
        r = s.schedule([("P1", 0, 10), ("P2", 1, 30), ("P3", 2, 6), ("P4", 8, 9)], "SRTF")
        self.assertEqual(s.gantt_text(r.gantt), "| P1 0-2 | P3 2-8 | P1 8-16 | P4 16-25 | P2 25-55 |")
        self.assertEqual((r.metrics["avg_turnaround"], r.metrics["avg_waiting"]), (23.25, 9.5))

    def test_s03_round_robin_known_answer(self):
        """TC-S03 Round Robin (q=2): new arrivals join before the preempted process"""
        procs = [("P1", 0, 5), ("P2", 1, 3), ("P3", 3, 4), ("P4", 5, 2), ("P5", 6, 3)]
        r = s.schedule(procs, "RR", quantum=2)
        order = [g[0] for g in r.gantt]
        self.assertEqual(order, ["P1", "P2", "P1", "P3", "P2", "P4", "P5", "P1", "P3", "P5"])
        self.assertEqual((r.metrics["avg_turnaround"], r.metrics["avg_waiting"]), (10.4, 7.0))

    def test_s04_priority_np_with_idle_gap(self):
        """TC-S04 Non-preemptive priority with a tie and an idle gap"""
        procs = [("P1", 0, 3, 3), ("P2", 1, 4, 2), ("P3", 2, 2, 1), ("P4", 4, 1, 2), ("P5", 12, 3, 1)]
        r = s.schedule(procs, "PRIORITY_NP")
        self.assertEqual(s.gantt_text(r.gantt), "| P1 0-3 | P3 3-5 | P2 5-9 | P4 9-10 | IDLE 10-12 | P5 12-15 |")
        self.assertEqual((r.metrics["avg_turnaround"], r.metrics["avg_waiting"]), (4.6, 2.0))

    def test_s05_priority_preemptive_equal_does_not_preempt(self):
        """TC-S05 Preemptive priority: an equal priority newcomer does not preempt"""
        procs = [("P1", 0, 4, 2), ("P2", 1, 3, 2), ("P3", 2, 2, 1), ("P4", 4, 3, 3), ("P5", 5, 2, 1)]
        r = s.schedule(procs, "PRIORITY_P")
        self.assertEqual(s.gantt_text(r.gantt),
                         "| P1 0-2 | P3 2-4 | P1 4-5 | P5 5-7 | P1 7-8 | P2 8-11 | P4 11-14 |")
        self.assertEqual((r.metrics["avg_turnaround"], r.metrics["avg_waiting"]), (6.4, 3.6))

    def test_s06_sjf_known_answer(self):
        """TC-S06 SJF picks the shortest job among those that have arrived"""
        r = s.schedule([("P1", 0, 10), ("P2", 1, 30), ("P3", 2, 6), ("P4", 8, 9)], "SJF")
        self.assertEqual(s.gantt_text(r.gantt), "| P1 0-10 | P3 10-16 | P4 16-25 | P2 25-55 |")


class BoundaryCases(unittest.TestCase):
    def test_s07_single_process(self):
        """TC-S07 One process: waiting 0, no context switch, every algorithm agrees"""
        for algo in s.ALGORITHMS:
            r = s.schedule([("P1", 3, 4)], algo, quantum=1)
            self.assertEqual(times(r)["P1"], (7, 4, 0), algo)
            self.assertEqual(r.metrics["context_switches"], 0, algo)

    def test_s08_cpu_idle_before_first_arrival(self):
        """TC-S08 CPU stays idle until the first process arrives"""
        r = s.schedule([("P1", 5, 2), ("P2", 9, 1)], "FCFS")
        self.assertEqual(r.gantt[0], ["P1", 5, 7])
        self.assertIn(["IDLE", 7, 9], r.gantt)
        self.assertLess(r.metrics["cpu_utilization"], 100)

    def test_s09_same_arrival_tie_uses_input_order(self):
        """TC-S09 Equal arrival times are served in input order"""
        r = s.schedule([("A", 0, 2), ("B", 0, 2), ("C", 0, 2)], "FCFS")
        self.assertEqual([g[0] for g in r.gantt], ["A", "B", "C"])

    def test_s10_huge_quantum_equals_fcfs(self):
        """TC-S10 RR with a quantum larger than every burst gives the FCFS result"""
        procs = [("P1", 0, 8), ("P2", 1, 4), ("P3", 2, 9)]
        self.assertEqual(s.schedule(procs, "RR", quantum=50).rows, s.schedule(procs, "FCFS").rows)

    def test_s11_random_workloads_are_consistent(self):
        """TC-S11 200 random workloads: every process finishes and CPU busy time equals total burst"""
        logging.disable(logging.INFO)          # keep the activity log readable: hundreds of runs
        self.addCleanup(logging.disable, logging.NOTSET)
        rng = random.Random(42)
        for _ in range(200):
            procs = [(f"P{i}", rng.randint(0, 15), rng.randint(1, 10), rng.randint(0, 5)) for i in range(rng.randint(1, 7))]
            for algo in s.ALGORITHMS:
                r = s.schedule(procs, algo, quantum=rng.randint(1, 4))
                busy = sum(e - b for label, b, e in r.gantt if label != "IDLE")
                self.assertEqual(busy, sum(p[2] for p in procs))
                for row in r.rows:
                    self.assertGreaterEqual(row["waiting"], 0)
                    self.assertEqual(row["turnaround"], row["waiting"] + row["burst"])


class InvalidCases(unittest.TestCase):
    def test_s12_negative_arrival(self):
        """TC-S12 Negative arrival time is rejected"""
        with self.assertRaises(ValidationError):
            s.schedule([("P1", -1, 5)], "FCFS")

    def test_s13_zero_burst(self):
        """TC-S13 Burst time 0 is rejected"""
        with self.assertRaises(ValidationError):
            s.schedule([("P1", 0, 0)], "FCFS")

    def test_s14_bad_quantum(self):
        """TC-S14 Quantum 0 is rejected"""
        with self.assertRaises(ValidationError):
            s.schedule([("P1", 0, 5)], "RR", quantum=0)

    def test_s15_bad_input_shapes(self):
        """TC-S15 Empty list, duplicate ids, text values and unknown algorithms are rejected"""
        for bad in ([], [("P1", 0, 2), ("P1", 1, 2)], [("P1", "abc", 2)], [("P1", 0, 2.5)]):
            with self.assertRaises(ValidationError):
                s.schedule(bad, "FCFS")
        with self.assertRaises(ValidationError):
            s.schedule([("P1", 0, 2)], "LOTTERY")


if __name__ == "__main__":
    unittest.main()
