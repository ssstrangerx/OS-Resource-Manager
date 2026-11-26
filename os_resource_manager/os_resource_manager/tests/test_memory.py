import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from osrm import memory as m
from osrm.validation import ValidationError

TEXTBOOK = [7, 0, 1, 2, 0, 3, 0, 4, 2, 3, 0, 3, 2, 1, 2, 0, 1, 7, 0, 1]
BELADY = [1, 2, 3, 4, 1, 2, 5, 1, 2, 3, 4, 5]
BLOCKS = [100, 500, 200, 300, 600]
REQUESTS = [("P1", 212), ("P2", 417), ("P3", 112), ("P4", 426)]


class PageReplacement(unittest.TestCase):
    def test_m01_textbook_answers(self):
        """TC-M01 Textbook string with 3 frames: FIFO 15, LRU 12, Optimal 9 faults"""
        faults = {r.algorithm: r.faults for r in m.compare_paging(TEXTBOOK, 3)}
        self.assertEqual(faults, {"FIFO": 15, "LRU": 12, "OPTIMAL": 9})

    def test_m02_belady_anomaly(self):
        """TC-M02 FIFO shows Belady's anomaly (9 faults with 3 frames, 10 with 4); LRU does not"""
        self.assertEqual(m.page_replacement(BELADY, 3, "FIFO").faults, 9)
        self.assertEqual(m.page_replacement(BELADY, 4, "FIFO").faults, 10)
        self.assertEqual(m.belady_check(BELADY, [3, 4]), [(3, 9, 4, 10)])
        lru = [m.page_replacement(BELADY, f, "LRU").faults for f in range(1, 6)]
        self.assertEqual(lru, sorted(lru, reverse=True))

    def test_m03_optimal_is_never_worse(self):
        """TC-M03 Optimal never has more faults than FIFO or LRU (frames 1-7)"""
        for f in range(1, 8):
            res = {r.algorithm: r.faults for r in m.compare_paging(TEXTBOOK, f)}
            self.assertLessEqual(res["OPTIMAL"], min(res["FIFO"], res["LRU"]))

    def test_m04_enough_frames(self):
        """TC-M04 Boundary: frames >= distinct pages, so only the first use of each page faults"""
        for algo in m.PAGE_ALGORITHMS:
            self.assertEqual(m.page_replacement(TEXTBOOK, 10, algo).faults, len(set(TEXTBOOK)))

    def test_m05_single_frame(self):
        """TC-M05 Boundary: one frame faults every time the page changes"""
        refs = [1, 1, 2, 2, 1]
        for algo in m.PAGE_ALGORITHMS:
            self.assertEqual(m.page_replacement(refs, 1, algo).faults, 3)

    def test_m06_trace_is_consistent(self):
        """TC-M06 Trace: hits + faults = references and frames never overflow"""
        r = m.page_replacement(TEXTBOOK, 3, "LRU")
        self.assertEqual(r.hits + r.faults, len(TEXTBOOK))
        self.assertTrue(all(len(t["frames"]) <= 3 for t in r.trace))

    def test_m07_invalid_paging_input(self):
        """TC-M07 Invalid: 0 frames, negative page, empty string, unknown algorithm"""
        for refs, frames, algo in ((TEXTBOOK, 0, "FIFO"), ([1, -2], 3, "FIFO"), ([], 3, "LRU"), (TEXTBOOK, 3, "RANDOM")):
            with self.assertRaises(ValidationError):
                m.page_replacement(refs, frames, algo)


class ContiguousAllocation(unittest.TestCase):
    def test_m08_textbook_fits(self):
        """TC-M08 Textbook blocks: best fit places all 4; first and worst fit leave P4 (426 KB) waiting"""
        first, best, worst = m.compare_fits(BLOCKS, REQUESTS)
        self.assertEqual([a["block"] for a in first.allocations], [2, 5, 2])
        self.assertEqual([a["block"] for a in best.allocations], [4, 2, 3, 5])
        self.assertEqual([a["block"] for a in worst.allocations], [5, 2, 5])
        self.assertEqual([w["pid"] for w in first.waiting], ["P4"])
        self.assertEqual(best.waiting, [])

    def test_m09_exact_fit_and_too_big(self):
        """TC-M09 Boundary: an exact fit leaves 0 KB; a request bigger than every block waits"""
        r = m.contiguous_allocation([100, 50], [("A", 100), ("B", 500)], "FIRST")
        self.assertEqual(r.allocations[0]["left"], 0)
        self.assertEqual([w["pid"] for w in r.waiting], ["B"])

    def test_m10_invalid_allocation_input(self):
        """TC-M10 Invalid: zero-size process, negative block, no blocks, unknown strategy"""
        for blocks, reqs, strat in (([100], [("A", 0)], "BEST"), ([-5], [("A", 1)], "BEST"),
                                    ([], [("A", 1)], "BEST"), ([100], [("A", 1)], "NEXT")):
            with self.assertRaises(ValidationError):
                m.contiguous_allocation(blocks, reqs, strat)


if __name__ == "__main__":
    unittest.main()
