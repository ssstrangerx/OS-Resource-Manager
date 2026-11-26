import logging
import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from osrm import storage as st
from osrm.validation import ValidationError

QUEUE = [98, 183, 37, 122, 14, 124, 65, 67]


def totals(direction="up", count_jump=True, queue=QUEUE, head=53):
    return {r.algorithm: r.total for r in st.compare_disk(queue, head, 200, direction, count_jump)}


class DiskScheduling(unittest.TestCase):
    def test_k01_textbook_totals_up(self):
        """TC-K01 Head 53 moving up: FCFS 640, SSTF 236, SCAN 331, C-SCAN 382, LOOK 299, C-LOOK 322"""
        self.assertEqual(totals("up"), {"FCFS": 640, "SSTF": 236, "SCAN": 331,
                                        "C-SCAN": 382, "LOOK": 299, "C-LOOK": 322})

    def test_k02_textbook_totals_down(self):
        """TC-K02 Head 53 moving down: SCAN 236, C-SCAN 386, LOOK 208, C-LOOK 326"""
        t = totals("down")
        self.assertEqual((t["SCAN"], t["C-SCAN"], t["LOOK"], t["C-LOOK"]), (236, 386, 208, 326))

    def test_k03_return_jump_not_counted(self):
        """TC-K03 With count_jump=False the C-SCAN/C-LOOK return jump is left out"""
        t = totals("up", count_jump=False)
        self.assertEqual((t["C-SCAN"], t["C-LOOK"]), (183, 153))

    def test_k04_empty_queue(self):
        """TC-K04 Boundary: an empty queue moves the head 0 cylinders"""
        self.assertTrue(all(v == 0 for v in totals(queue=[]).values()))

    def test_k05_request_at_head(self):
        """TC-K05 Boundary: a request at the current head position costs 0"""
        for algo in ("FCFS", "SSTF", "LOOK", "C-LOOK"):
            self.assertEqual(st.disk_schedule([53], 53, 200, algo).total, 0)

    def test_k06_head_at_disk_edges(self):
        """TC-K06 Boundary: head at cylinder 0 and at the last cylinder"""
        self.assertEqual(st.disk_schedule([10, 199], 0, 200, "SCAN", "up").total, 199)
        self.assertEqual(st.disk_schedule([10, 150], 199, 200, "LOOK", "down").total, 189)

    def test_k07_every_request_served_once(self):
        """TC-K07 300 random queues: every algorithm visits every request"""
        logging.disable(logging.INFO)          # keep the activity log readable: hundreds of runs
        self.addCleanup(logging.disable, logging.NOTSET)
        rng = random.Random(7)
        for _ in range(300):
            q = [rng.randint(0, 199) for _ in range(rng.randint(1, 15))]
            head = rng.randint(0, 199)
            for r in st.compare_disk(q, head, 200, rng.choice(["up", "down"])):
                visited = r.path[1:]
                for req in q:
                    self.assertIn(req, visited + [head])
                self.assertEqual(r.total, sum(mv[2] for mv in r.moves))

    def test_k08_invalid_disk_input(self):
        """TC-K08 Invalid: request beyond the disk, negative head, bad direction, unknown algorithm"""
        cases = (([250], 53, "up", "FCFS"), ([10], -1, "up", "FCFS"),
                 ([10], 53, "left", "SCAN"), ([10], 53, "up", "N-STEP"))
        for q, head, direction, algo in cases:
            with self.assertRaises(ValidationError):
                st.disk_schedule(q, head, 200, algo, direction)


if __name__ == "__main__":
    unittest.main()
