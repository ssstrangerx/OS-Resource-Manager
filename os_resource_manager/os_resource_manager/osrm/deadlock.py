"""Deadlock handling: Banker's safety algorithm, Banker's resource-request algorithm,
deadlock detection (several instances per resource type) and recovery by terminating processes."""

from dataclasses import dataclass, field

from .logger import get_logger
from .validation import ValidationError, require_int, require_list, require_matrix

log = get_logger("deadlock")


@dataclass
class BankerState:
    allocation: list
    maximum: list
    available: list
    names: list = None

    def __post_init__(self):
        self.available = [require_int(v, "Available", minimum=0)
                          for v in require_list(self.available, "Available", 1)]
        m = len(self.available)
        rows = len(require_list(self.allocation, "Allocation", 1))
        self.allocation = require_matrix(self.allocation, "Allocation", rows, m)
        self.maximum = require_matrix(self.maximum, "Maximum", rows, m)
        for i in range(rows):
            for j in range(m):
                if self.allocation[i][j] > self.maximum[i][j]:
                    raise ValidationError(
                        f"P{i} holds {self.allocation[i][j]} of resource {j} but its maximum is "
                        f"{self.maximum[i][j]}: Allocation cannot be more than Maximum")
        self.names = self.names or [f"P{i}" for i in range(rows)]
        if len(self.names) != rows:
            raise ValidationError("Number of process names does not match the matrices")

    @property
    def need(self):
        return [[mx - al for mx, al in zip(mrow, arow)]
                for mrow, arow in zip(self.maximum, self.allocation)]


@dataclass
class SafetyResult:
    safe: bool
    sequence: list
    need: list
    steps: list = field(default_factory=list)       # text lines of the trace
    unfinished: list = field(default_factory=list)


def _fits(vector, work):
    return all(a <= b for a, b in zip(vector, work))


def safety(state):
    """Banker's safety algorithm. Returns the safe sequence, or reports an unsafe state."""
    need = state.need
    work = list(state.available)
    finish = [False] * len(need)
    sequence, steps = [], [f"Start: Work = Available = {work}"]
    progress = True
    while progress:
        progress = False
        for i, row in enumerate(need):
            if not finish[i] and _fits(row, work):
                new_work = [w + a for w, a in zip(work, state.allocation[i])]
                steps.append(f"{state.names[i]}: Need {row} <= Work {work} -> runs, "
                             f"releases {state.allocation[i]}, Work = {new_work}")
                work, finish[i] = new_work, True
                sequence.append(state.names[i])
                progress = True
    unfinished = [state.names[i] for i, f in enumerate(finish) if not f]
    result = SafetyResult(all(finish), sequence, need, steps, unfinished)
    log.info("Banker's safety: %s %s", "SAFE" if result.safe else "UNSAFE",
             sequence if result.safe else unfinished)
    return result


@dataclass
class RequestResult:
    granted: bool
    reason: str
    new_state: BankerState = None
    safety: SafetyResult = None
    decision: str = ""          # GRANTED, WAIT (not available), UNSAFE (would be unsafe), ERROR (exceeds Need)


def request_resources(state, process_index, request):
    """Banker's resource-request algorithm for one request."""
    n, m = len(state.allocation), len(state.available)
    i = require_int(process_index, "Process number", minimum=0, maximum=n - 1)
    request = [require_int(v, "Request", minimum=0) for v in require_list(request, "Request", 1)]
    if len(request) != m:
        raise ValidationError(f"Request must have {m} values, got {len(request)}")
    name = state.names[i]
    if not _fits(request, state.need[i]):
        res = RequestResult(False, f"{name} asked for {request}, more than its remaining Need {state.need[i]} (error)", decision="ERROR")
    elif not _fits(request, state.available):
        res = RequestResult(False, f"{name} must wait: {request} is more than Available {state.available}", decision="WAIT")
    else:
        trial = BankerState(
            allocation=[[a + (r if k == i else 0) for a, r in zip(row, request)] for k, row in enumerate(state.allocation)],
            maximum=[list(r) for r in state.maximum],
            available=[a - r for a, r in zip(state.available, request)],
            names=list(state.names))
        check = safety(trial)
        if check.safe:
            res = RequestResult(True, f"The new state is safe, sequence {' -> '.join(check.sequence)}", trial, check, "GRANTED")
        else:
            res = RequestResult(False, f"{name} must wait: granting {request} would leave an unsafe state", None, check, "UNSAFE")
    log.info("Request %s by %s: %s", request, name, res.decision)
    return res


@dataclass
class DetectionResult:
    deadlocked: list
    finish_order: list
    steps: list = field(default_factory=list)

    @property
    def deadlock(self):
        return bool(self.deadlocked)


def _validate_detection(allocation, request, available, names):
    available = [require_int(v, "Available", minimum=0) for v in require_list(available, "Available", 1)]
    m = len(available)
    rows = len(require_list(allocation, "Allocation", 1))
    allocation = require_matrix(allocation, "Allocation", rows, m)
    request = require_matrix(request, "Request", rows, m)
    names = names or [f"P{i}" for i in range(rows)]
    return allocation, request, available, names


def detect(allocation, request, available, names=None):
    """Deadlock detection for resources with several instances each."""
    allocation, request, available, names = _validate_detection(allocation, request, available, names)
    work = list(available)
    # A process that holds nothing cannot be part of a deadlock.
    finish = [all(v == 0 for v in row) for row in allocation]
    order, steps = [], [f"Start: Work = Available = {work}"]
    for i, done in enumerate(finish):
        if done:
            steps.append(f"{names[i]} holds nothing -> marked finished")
    progress = True
    while progress:
        progress = False
        for i in range(len(allocation)):
            if not finish[i] and _fits(request[i], work):
                new_work = [w + a for w, a in zip(work, allocation[i])]
                steps.append(f"{names[i]}: Request {request[i]} <= Work {work} -> can finish, Work = {new_work}")
                work, finish[i] = new_work, True
                order.append(names[i])
                progress = True
    deadlocked = [names[i] for i, f in enumerate(finish) if not f]
    steps.append("Deadlocked: " + (", ".join(deadlocked) if deadlocked else "none"))
    log.info("Detection: %s", ("deadlock among " + ", ".join(deadlocked)) if deadlocked else "no deadlock")
    return DetectionResult(deadlocked, order, steps)


def recover(allocation, request, available, names=None):
    """Recover from deadlock by terminating victims one at a time.

    Victim rule: among the deadlocked processes, terminate the one holding the most
    resource instances (it frees the most), then run detection again.
    Returns (terminated_names, final DetectionResult, steps).
    """
    allocation, request, available, names = _validate_detection(allocation, request, available, names)
    allocation = [list(r) for r in allocation]
    request = [list(r) for r in request]
    available = list(available)
    terminated, steps = [], []
    result = detect(allocation, request, available, names)
    while result.deadlock:
        candidates = [names.index(p) for p in result.deadlocked]
        victim = max(candidates, key=lambda i: (sum(allocation[i]), -i))
        steps.append(f"Terminate {names[victim]}: releases {allocation[victim]}")
        available = [a + r for a, r in zip(available, allocation[victim])]
        allocation[victim] = [0] * len(available)
        request[victim] = [0] * len(available)
        terminated.append(names[victim])
        steps.append(f"Available is now {available}")
        result = detect(allocation, request, available, names)
    steps.append("System is deadlock-free" + (f" after terminating {', '.join(terminated)}" if terminated else ""))
    log.info("Recovery terminated: %s", terminated or "none")
    return terminated, result, steps
