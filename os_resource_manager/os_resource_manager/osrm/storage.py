"""Secondary storage: disk scheduling with FCFS, SSTF, SCAN, C-SCAN, LOOK and C-LOOK.

Conventions:
- Cylinders run from 0 to disk_size - 1.
- direction "up" moves towards higher cylinder numbers first, "down" towards 0.
- SCAN and C-SCAN travel to the end of the disk; LOOK and C-LOOK turn at the last request.
- For C-SCAN and C-LOOK the return jump is counted in the head movement by default
  (count_jump=True), as in the class slides; set it to False to leave it out.
- SSTF breaks a distance tie by taking the lower cylinder number.
"""

from dataclasses import dataclass, field

from .logger import get_logger
from .validation import ValidationError, require_int, require_list

log = get_logger("storage")

DISK_ALGORITHMS = ("FCFS", "SSTF", "SCAN", "C-SCAN", "LOOK", "C-LOOK")


@dataclass
class DiskResult:
    algorithm: str
    head: int
    requests: list
    path: list = field(default_factory=list)       # every head position visited, in order
    moves: list = field(default_factory=list)      # (from, to, distance)
    total: int = 0

    @property
    def average_seek(self):
        return round(self.total / len(self.requests), 2) if self.requests else 0.0


def _validate(requests, head, disk_size, direction):
    disk_size = require_int(disk_size, "Disk size (cylinders)", minimum=1)
    head = require_int(head, "Head position", minimum=0, maximum=disk_size - 1)
    requests = [require_int(r, "Cylinder request", minimum=0, maximum=disk_size - 1)
                for r in require_list(requests, "Request queue", 0)]
    direction = str(direction).lower()
    if direction not in ("up", "down"):
        raise ValidationError(f"Direction must be 'up' or 'down', got {direction!r}")
    return requests, head, disk_size, direction


def _path_for(algorithm, requests, head, disk_size, direction):
    if not requests:
        return [], []
    at_head = [r for r in requests if r == head]                      # served first, zero movement
    lower = sorted((r for r in requests if r < head), reverse=True)   # nearest first going down
    upper = sorted(r for r in requests if r > head)                   # nearest first going up
    end, start = disk_size - 1, 0
    if algorithm == "FCFS":
        return list(requests), []
    if algorithm == "SSTF":
        pending, pos, path = list(requests), head, []
        while pending:
            nxt = min(pending, key=lambda r: (abs(r - pos), r))
            pending.remove(nxt)
            path.append(nxt)
            pos = nxt
        return path, []
    first, second = (upper, lower) if direction == "up" else (lower, upper)
    first = at_head + first
    edge, other_edge = (end, start) if direction == "up" else (start, end)
    if algorithm == "SCAN":
        path = list(first)
        if second:
            path.append(edge)                     # sweep to the end, then reverse
            path += second
        elif not path or path[-1] != edge:
            path.append(edge)                     # SCAN always reaches the end in its direction
        return path, []
    if algorithm == "LOOK":
        return list(first) + list(second), []
    if algorithm == "C-SCAN":
        path, jumps = list(first), []
        if second:
            if not path or path[-1] != edge:
                path.append(edge)
            rest = sorted(second) if direction == "up" else sorted(second, reverse=True)
            jumps.append(len(path))               # index of the jump target in path
            if rest[0] != other_edge:             # land on the far edge unless a request is already there
                path.append(other_edge)
            path += rest
        return path, jumps
    # C-LOOK
    path, jumps = list(first), []
    if second:
        jumps.append(len(path))
        path += sorted(second) if direction == "up" else sorted(second, reverse=True)
    return path, jumps


def disk_schedule(requests, head, disk_size=200, algorithm="FCFS", direction="up", count_jump=True):
    algorithm = str(algorithm).upper()
    if algorithm not in DISK_ALGORITHMS:
        raise ValidationError(f"Unknown disk algorithm {algorithm!r}. Choose from {', '.join(DISK_ALGORITHMS)}")
    requests, head, disk_size, direction = _validate(requests, head, disk_size, direction)
    path, jumps = _path_for(algorithm, requests, head, disk_size, direction)
    result = DiskResult(algorithm, head, requests, path=[head] + path)
    pos = head
    for idx, target in enumerate(path):
        distance = abs(target - pos)
        is_jump = idx in jumps
        counted = distance if (count_jump or not is_jump) else 0
        result.moves.append((pos, target, counted, is_jump))
        result.total += counted
        pos = target
    log.info("%s from head %d over %d requests: %d cylinders", algorithm, head, len(requests), result.total)
    return result


def compare_disk(requests, head, disk_size=200, direction="up", count_jump=True):
    return [disk_schedule(requests, head, disk_size, a, direction, count_jump) for a in DISK_ALGORITHMS]
