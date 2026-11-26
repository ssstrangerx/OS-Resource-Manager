"""CPU scheduling: FCFS, SJF, SRTF, Priority (non-preemptive and preemptive) and Round Robin.

Conventions (the same ones used in class):
- A smaller priority number means a higher priority.
- Ties are broken by earlier arrival time, then by input order.
- Round Robin: processes that arrive during a time slice join the ready queue
  before the process that was just preempted.
- A preemptive algorithm switches only when the newcomer is strictly better;
  an equal value does not preempt the running process.
"""

from collections import deque
from dataclasses import dataclass, field

from .logger import get_logger
from .validation import ValidationError, require_int

log = get_logger("scheduling")

ALGORITHMS = {
    "FCFS": "First Come First Serve",
    "SJF": "Shortest Job First (non-preemptive)",
    "SRTF": "Shortest Remaining Time First (preemptive SJF)",
    "PRIORITY_NP": "Priority (non-preemptive)",
    "PRIORITY_P": "Priority (preemptive)",
    "RR": "Round Robin",
}


@dataclass
class Process:
    pid: str
    arrival: int
    burst: int
    priority: int = 0


@dataclass
class ScheduleResult:
    algorithm: str
    processes: list
    gantt: list                      # [label, start, end]; label "IDLE" for idle CPU
    completion: dict
    first_run: dict
    quantum: int = None
    rows: list = field(default_factory=list)
    metrics: dict = field(default_factory=dict)

    def finalize(self):
        """Compute per-process times and the overall metrics."""
        self.rows = []
        for p in self.processes:
            ct = self.completion[p.pid]
            tat = ct - p.arrival
            wt = tat - p.burst
            rt = self.first_run[p.pid] - p.arrival
            self.rows.append({"pid": p.pid, "arrival": p.arrival, "burst": p.burst,
                              "priority": p.priority, "completion": ct,
                              "turnaround": tat, "waiting": wt, "response": rt})
        n = len(self.rows)
        start = min(p.arrival for p in self.processes)
        end = max(self.completion.values())
        span = end - start
        busy = sum(e - s for label, s, e in self.gantt if label != "IDLE")
        dispatches = sum(1 for label, _, _ in self.gantt if label != "IDLE")
        self.metrics = {
            "avg_turnaround": round(sum(r["turnaround"] for r in self.rows) / n, 2),
            "avg_waiting": round(sum(r["waiting"] for r in self.rows) / n, 2),
            "avg_response": round(sum(r["response"] for r in self.rows) / n, 2),
            "throughput": round(n / span, 3) if span else float(n),
            "cpu_utilization": round(100 * busy / span, 2) if span else 100.0,
            "context_switches": max(0, dispatches - 1),
            "makespan": span,
        }
        return self


def make_processes(raw):
    """Validate raw input (list of dicts or tuples) and return a list of Process objects."""
    if not isinstance(raw, (list, tuple)) or not raw:
        raise ValidationError("At least one process is required")
    processes, seen = [], set()
    for i, item in enumerate(raw):
        if isinstance(item, Process):
            item = item.__dict__
        if isinstance(item, (list, tuple)):
            keys = ("pid", "arrival", "burst", "priority")
            item = dict(zip(keys, item))
        if not isinstance(item, dict):
            raise ValidationError(f"Process {i + 1} is not in a valid format")
        pid = str(item.get("pid") or f"P{i + 1}").strip()
        if pid in seen:
            raise ValidationError(f"Duplicate process id {pid}")
        seen.add(pid)
        processes.append(Process(
            pid=pid,
            arrival=require_int(item.get("arrival"), f"{pid} arrival time", minimum=0),
            burst=require_int(item.get("burst"), f"{pid} burst time", minimum=1),
            priority=require_int(item.get("priority", 0), f"{pid} priority", minimum=0),
        ))
    return processes


def _add(gantt, label, start, end):
    """Append a slot to the Gantt chart, merging it with the previous slot of the same label."""
    if end <= start:
        return
    if gantt and gantt[-1][0] == label and gantt[-1][2] == start:
        gantt[-1][2] = end
    else:
        gantt.append([label, start, end])


def _simulate(processes, key, preemptive):
    """Shared engine for FCFS, SJF, SRTF and both Priority variants.

    key(process, remaining) returns the sort key; the smallest key runs next.
    """
    order = {p.pid: i for i, p in enumerate(processes)}
    remaining = {p.pid: p.burst for p in processes}
    completion, first_run, gantt = {}, {}, []
    time, done = min(p.arrival for p in processes), 0   # the clock starts at the first arrival
    while done < len(processes):
        ready = [p for p in processes if p.arrival <= time and remaining[p.pid] > 0]
        if not ready:
            next_arrival = min(p.arrival for p in processes if remaining[p.pid] > 0)
            _add(gantt, "IDLE", time, next_arrival)
            time = next_arrival
            continue
        current = min(ready, key=lambda p: (key(p, remaining[p.pid]), p.arrival, order[p.pid]))
        first_run.setdefault(current.pid, time)
        if preemptive:
            upcoming = [p.arrival for p in processes if p.arrival > time]
            run = min(remaining[current.pid], (min(upcoming) - time) if upcoming else remaining[current.pid])
        else:
            run = remaining[current.pid]
        _add(gantt, current.pid, time, time + run)
        time += run
        remaining[current.pid] -= run
        if remaining[current.pid] == 0:
            completion[current.pid] = time
            done += 1
    return gantt, completion, first_run


def round_robin(processes, quantum):
    quantum = require_int(quantum, "Time quantum", minimum=1)
    arrival_order = sorted(processes, key=lambda p: p.arrival)  # stable: keeps input order on ties
    remaining = {p.pid: p.burst for p in processes}
    completion, first_run, gantt = {}, {}, []
    queue, time, k = deque(), arrival_order[0].arrival, 0   # the clock starts at the first arrival

    def admit(upto):
        nonlocal k
        while k < len(arrival_order) and arrival_order[k].arrival <= upto:
            queue.append(arrival_order[k])
            k += 1

    while len(completion) < len(processes):
        admit(time)
        if not queue:
            nxt = arrival_order[k].arrival
            _add(gantt, "IDLE", time, nxt)
            time = nxt
            continue
        p = queue.popleft()
        first_run.setdefault(p.pid, time)
        run = min(quantum, remaining[p.pid])
        _add(gantt, p.pid, time, time + run)
        time += run
        remaining[p.pid] -= run
        admit(time)                       # arrivals during the slice join first
        if remaining[p.pid] > 0:
            queue.append(p)               # then the preempted process
        else:
            completion[p.pid] = time
    return gantt, completion, first_run


def schedule(raw_processes, algorithm, quantum=2):
    """Run one algorithm and return a finalized ScheduleResult."""
    algorithm = str(algorithm).upper()
    if algorithm not in ALGORITHMS:
        raise ValidationError(f"Unknown scheduling algorithm {algorithm!r}. Choose from {', '.join(ALGORITHMS)}")
    processes = make_processes(raw_processes)
    if algorithm == "FCFS":
        g, c, f = _simulate(processes, lambda p, r: p.arrival, preemptive=False)
    elif algorithm == "SJF":
        g, c, f = _simulate(processes, lambda p, r: p.burst, preemptive=False)
    elif algorithm == "SRTF":
        g, c, f = _simulate(processes, lambda p, r: r, preemptive=True)
    elif algorithm == "PRIORITY_NP":
        g, c, f = _simulate(processes, lambda p, r: p.priority, preemptive=False)
    elif algorithm == "PRIORITY_P":
        g, c, f = _simulate(processes, lambda p, r: p.priority, preemptive=True)
    else:
        g, c, f = round_robin(processes, quantum)
    result = ScheduleResult(algorithm, processes, g, c, f,
                            quantum=quantum if algorithm == "RR" else None).finalize()
    log.info("%s on %d processes: avg WT=%.2f avg TAT=%.2f", algorithm, len(processes),
             result.metrics["avg_waiting"], result.metrics["avg_turnaround"])
    return result


def compare_all(raw_processes, quantum=2):
    """Run every algorithm on the same workload."""
    return [schedule(raw_processes, name, quantum) for name in ALGORITHMS]


def quantum_sweep(raw_processes, quanta):
    """Round Robin with several time quanta, to see how the quantum changes the results."""
    return [schedule(raw_processes, "RR", q) for q in quanta]


def gantt_text(gantt):
    """'| P1 0-3 | P2 3-5 |' style Gantt chart."""
    return "| " + " | ".join(f"{label} {s}-{e}" for label, s, e in gantt) + " |"
