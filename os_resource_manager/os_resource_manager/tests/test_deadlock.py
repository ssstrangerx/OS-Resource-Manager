import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from osrm import deadlock as d
from osrm.validation import ValidationError

ALLOC = [[0, 1, 0], [2, 0, 0], [3, 0, 2], [2, 1, 1], [0, 0, 2]]
MAXM = [[7, 5, 3], [3, 2, 2], [9, 0, 2], [2, 2, 2], [4, 3, 3]]
DET_ALLOC = [[0, 1, 0], [2, 0, 0], [3, 0, 3], [2, 1, 1], [0, 0, 2]]
DET_REQ_OK = [[0, 0, 0], [2, 0, 2], [0, 0, 0], [1, 0, 0], [0, 0, 2]]
DET_REQ_DEAD = [[0, 0, 0], [2, 0, 2], [0, 0, 1], [1, 0, 0], [0, 0, 2]]


class Banker(unittest.TestCase):
    def setUp(self):
        self.state = d.BankerState(ALLOC, MAXM, [3, 3, 2])

    def test_d01_safe_sequence(self):
        """TC-D01 Textbook state is safe with sequence P1, P3, P4, P0, P2"""
        r = d.safety(self.state)
        self.assertTrue(r.safe)
        self.assertEqual(r.sequence, ["P1", "P3", "P4", "P0", "P2"])
        self.assertEqual(r.need[0], [7, 4, 3])

    def test_d02_unsafe_state(self):
        """TC-D02 With Available 1 1 1 the state is unsafe; P0, P2, P4 cannot finish"""
        r = d.safety(d.BankerState(ALLOC, MAXM, [1, 1, 1]))
        self.assertFalse(r.safe)
        self.assertEqual(r.unfinished, ["P0", "P2", "P4"])

    def test_d03_request_granted_then_others(self):
        """TC-D03 P1 (1,0,2) is granted; then P4 (3,3,0) must wait and P0 (0,2,0) is unsafe"""
        r1 = d.request_resources(self.state, 1, [1, 0, 2])
        self.assertTrue(r1.granted)
        self.assertEqual(r1.decision, "GRANTED")
        self.assertEqual(r1.new_state.available, [2, 3, 0])
        r2 = d.request_resources(r1.new_state, 4, [3, 3, 0])
        self.assertFalse(r2.granted)
        self.assertEqual(r2.decision, "WAIT")
        self.assertIn("more than Available", r2.reason)
        r3 = d.request_resources(r1.new_state, 0, [0, 2, 0])
        self.assertFalse(r3.granted)
        self.assertEqual(r3.decision, "UNSAFE")
        self.assertIn("unsafe", r3.reason)

    def test_d04_request_above_need_is_error(self):
        """TC-D04 A request larger than the process's remaining Need is refused as an error"""
        r = d.request_resources(self.state, 3, [1, 0, 0])
        self.assertFalse(r.granted)
        self.assertEqual(r.decision, "ERROR")
        self.assertIn("Need", r.reason)

    def test_d05_minimal_state(self):
        """TC-D05 Boundary: one process, one resource, nothing more needed -> safe"""
        r = d.safety(d.BankerState([[2]], [[2]], [0]))
        self.assertTrue(r.safe)
        self.assertEqual(r.sequence, ["P0"])

    def test_d06_invalid_banker_input(self):
        """TC-D06 Invalid: Allocation above Maximum, ragged rows, negative values, bad request"""
        with self.assertRaises(ValidationError):
            d.BankerState([[5, 0]], [[3, 0]], [1, 1])
        with self.assertRaises(ValidationError):
            d.BankerState([[1, 0], [1]], [[2, 2], [2, 2]], [1, 1])
        with self.assertRaises(ValidationError):
            d.BankerState([[-1, 0]], [[2, 2]], [1, 1])
        with self.assertRaises(ValidationError):
            d.request_resources(self.state, 1, [1, 0])          # wrong length
        with self.assertRaises(ValidationError):
            d.request_resources(self.state, 9, [0, 0, 0])       # no such process


class Detection(unittest.TestCase):
    def test_d07_no_deadlock(self):
        """TC-D07 Detection: textbook case without deadlock"""
        r = d.detect(DET_ALLOC, DET_REQ_OK, [0, 0, 0])
        self.assertFalse(r.deadlock)
        self.assertEqual(len(r.finish_order), 5)

    def test_d08_deadlock(self):
        """TC-D08 Detection: after P2 asks for one more C, P1-P4 are deadlocked"""
        r = d.detect(DET_ALLOC, DET_REQ_DEAD, [0, 0, 0])
        self.assertEqual(r.deadlocked, ["P1", "P2", "P3", "P4"])

    def test_d09_recovery(self):
        """TC-D09 Recovery terminates the largest holder (P2) and the system is deadlock-free"""
        killed, final, _ = d.recover(DET_ALLOC, DET_REQ_DEAD, [0, 0, 0])
        self.assertEqual(killed, ["P2"])
        self.assertFalse(final.deadlock)

    def test_d10_invalid_detection_input(self):
        """TC-D10 Invalid: Request matrix with the wrong shape"""
        with self.assertRaises(ValidationError):
            d.detect(DET_ALLOC, DET_REQ_OK[:3], [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
