#!/usr/bin/env python3
"""OS Resource Manager: menu-driven simulator for CPU scheduling, memory management,
deadlock handling and disk scheduling.

Usage:
    python3 main.py              interactive menu
    python3 main.py --analyze    run the full analysis on the shared datasets (no questions asked)
"""

import argparse
import subprocess
import sys
from pathlib import Path

from osrm import analysis, deadlock, memory, reporting, scheduling, storage
from osrm.datasets import load
from osrm.logger import PROJECT_ROOT, get_logger, tail
from osrm.validation import ValidationError, parse_int_list, require_int

log = get_logger("menu")
SCRIPTS = PROJECT_ROOT / "scripts"


# ------------------------------------------------------------------ input helpers
class BackToMenu(Exception):
    """User typed 'b' to go back."""


ECHO = not sys.stdin.isatty()      # input piped from a file (samples/): show it, so traces read like a session


def ask(prompt):
    try:
        text = input(prompt).strip()
        if ECHO:
            print(text)
    except EOFError:
        print("\nInput closed. Exiting.")
        log.info("Input closed (EOF); exiting")
        sys.exit(0)
    if text.lower() == "b":
        raise BackToMenu
    return text


def ask_int(prompt, minimum=None, maximum=None, default=None):
    while True:
        text = ask(prompt)
        if text == "" and default is not None:
            return default
        try:
            return require_int(text, "Value", minimum, maximum)
        except ValidationError as exc:
            print(f"  ! {exc}. Try again (or 'b' to go back).")
            log.warning("Invalid input %r: %s", text, exc)


def ask_list(prompt, count=None, minimum=None, maximum=None, allow_empty=False):
    while True:
        text = ask(prompt)
        try:
            values = parse_int_list(text, "List", minimum, maximum, allow_empty=allow_empty)
            if count is not None and len(values) != count:
                raise ValidationError(f"Enter exactly {count} numbers, you entered {len(values)}")
            return values
        except ValidationError as exc:
            print(f"  ! {exc}. Try again (or 'b' to go back).")
            log.warning("Invalid list input %r: %s", text, exc)


def choose(title, options):
    """Show numbered options and return the chosen key."""
    print(f"\n{title}")
    for i, (_, label) in enumerate(options, 1):
        print(f"  {i}. {label}")
    pick = ask_int("Choice: ", 1, len(options))
    return options[pick - 1][0]


def pause():
    try:
        input("\nPress Enter to continue...")
        if ECHO:
            print()
    except EOFError:
        pass


# ------------------------------------------------------------------ 1. scheduling
def get_processes():
    data = load("scheduling")
    src = choose("Process data", [("mixed", "Sample workload 'mixed' (6 processes)"),
                                  ("convoy", "Sample workload 'convoy' (long job first)"),
                                  ("manual", "Enter processes manually"),
                                  ("live", "Import live processes from this computer (Bash: ps)")])
    if src in data["workloads"]:
        return data["workloads"][src]["processes"], data.get("quantum", 2)
    if src == "live":
        return import_live_processes(), 2
    n = ask_int("Number of processes (1-20): ", 1, 20)
    print("For each process enter: arrival burst [priority]   e.g.  0 5 2   (smaller priority = higher)")
    procs = []
    for i in range(n):
        while True:
            vals = ask_list(f"  P{i + 1}: ", minimum=0)
            if len(vals) in (2, 3) and vals[1] >= 1:
                procs.append({"pid": f"P{i + 1}", "arrival": vals[0], "burst": vals[1],
                              "priority": vals[2] if len(vals) == 3 else 0})
                break
            print("  ! Enter 2 or 3 numbers, and the burst time must be at least 1.")
    return procs, 2


def import_live_processes():
    script = SCRIPTS / "ps_to_dataset.sh"
    count = ask_int("How many live processes to import (2-10) [5]: ", 2, 10, default=5)
    try:
        run = subprocess.run(["bash", str(script), str(count)], capture_output=True, text=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ValidationError(f"Could not run {script.name}: {exc}") from None
    if run.returncode != 0:
        raise ValidationError(f"{script.name} failed: {run.stderr.strip() or run.stdout.strip()}")
    print(run.stdout.strip())
    return load(PROJECT_ROOT / "data" / "live_processes.json")["processes"]


def show_schedule(result):
    title = scheduling.ALGORITHMS[result.algorithm] + (f" (quantum {result.quantum})" if result.quantum else "")
    print(f"\n{title}")
    print("Gantt: " + scheduling.gantt_text(result.gantt))
    print(analysis.process_table(result))
    m = result.metrics
    print(f"Avg waiting {m['avg_waiting']} | Avg turnaround {m['avg_turnaround']} | Avg response {m['avg_response']} | "
          f"Throughput {m['throughput']}/unit | CPU {m['cpu_utilization']}% | Context switches {m['context_switches']}")


def scheduling_menu():
    procs, default_q = get_processes()
    action = choose("What to run", [*[(k, v) for k, v in scheduling.ALGORITHMS.items()],
                                    ("ALL", "Compare all algorithms"),
                                    ("SWEEP", "Round Robin with different time quanta")])
    if action in ("RR", "ALL"):
        q = ask_int(f"Time quantum [{default_q}]: ", 1, 100, default=default_q)
    else:
        q = default_q
    out = reporting.ensure_dirs()
    if action == "SWEEP":
        quanta = ask_list("Quanta to try, e.g. 1 2 3 4 5: ", minimum=1, maximum=100)
        res = scheduling.quantum_sweep(procs, quanta)
        rows = [[qq, r.metrics["avg_waiting"], r.metrics["avg_turnaround"], r.metrics["avg_response"],
                 r.metrics["context_switches"]] for qq, r in zip(quanta, res)]
        print("\n" + reporting.table(["Quantum", "Avg WT", "Avg TAT", "Avg RT", "Ctx switches"], rows,
                                     "Round Robin quantum sweep"))
        return
    if action == "ALL":
        results = scheduling.compare_all(procs, q)
        rows = analysis._sched_rows(results)
        print("\n" + reporting.table(analysis.SCHED_HEADERS, rows, "Algorithm comparison"))
        print("\n" + reporting.ascii_bars("Average waiting time", [r[0].split(" ")[0] for r in rows],
                                          [r[1] for r in rows]))
        reporting.save_csv(out / "csv" / "interactive_scheduling.csv", analysis.SCHED_HEADERS, rows)
        chart = reporting.bar_chart(out / "charts" / "interactive_scheduling.png", "CPU scheduling comparison",
                                    [r[0].split(" ")[0] for r in rows],
                                    {"Avg waiting": [r[1] for r in rows], "Avg turnaround": [r[2] for r in rows]},
                                    "Time units")
        print(f"\nSaved output/csv/interactive_scheduling.csv" + (" and output/charts/interactive_scheduling.png" if chart else ""))
        return
    show_schedule(scheduling.schedule(procs, action, q))


# ------------------------------------------------------------------ 2. memory
def paging_menu():
    data = load("memory")
    if choose("Reference string", [("s", f"Sample: {' '.join(map(str, data['reference_string']))}"),
                                   ("m", "Enter my own")]) == "s":
        refs, frames = data["reference_string"], data.get("frames", 3)
        frames = ask_int(f"Number of frames [{frames}]: ", 1, 100, default=frames)
    else:
        refs = ask_list("Page numbers separated by spaces: ", minimum=0)
        frames = ask_int("Number of frames: ", 1, 100)
    action = choose("Algorithm", [("FIFO", "FIFO"), ("LRU", "LRU"), ("OPTIMAL", "Optimal"),
                                  ("ALL", "Compare all three"), ("SWEEP", "Faults for 1 to 7 frames")])
    if action == "SWEEP":
        counts = list(range(1, 8))
        sweep = memory.frames_sweep(refs, counts)
        rows = [[f] + [sweep[a][i] for a in memory.PAGE_ALGORITHMS] for i, f in enumerate(counts)]
        print("\n" + reporting.table(["Frames", *memory.PAGE_ALGORITHMS], rows, "Page faults vs frames"))
        for f1, x1, f2, x2 in memory.belady_check(refs, counts):
            print(f"Belady's anomaly: FIFO {x1} faults with {f1} frames, {x2} faults with {f2} frames")
        return
    algos = memory.PAGE_ALGORITHMS if action == "ALL" else [action]
    results = [memory.page_replacement(refs, frames, a) for a in algos]
    if len(results) == 1:
        r = results[0]
        print("\n" + reporting.table(["Step", "Page", "Frames", "Result", "Evicted"],
                                     [[t["step"], t["page"], " ".join(map(str, t["frames"])), t["status"],
                                       t["evicted"] if t["evicted"] is not None else "-"] for t in r.trace],
                                     f"{r.algorithm}, {frames} frames"))
    print("\n" + reporting.table(["Algorithm", "Faults", "Hits", "Fault rate %", "Hit ratio %"],
                                 [[r.algorithm, r.faults, r.hits, r.fault_rate, r.hit_ratio] for r in results]))


def allocation_menu():
    data = load("memory")
    if choose("Memory blocks and processes", [("s", f"Sample: blocks {data['blocks']}"),
                                              ("m", "Enter my own")]) == "s":
        blocks, reqs = data["blocks"], data["requests"]
    else:
        blocks = ask_list("Free block sizes in KB, e.g. 100 500 200: ", minimum=1)
        sizes = ask_list("Process sizes in KB, e.g. 212 417 112: ", minimum=1)
        reqs = [{"pid": f"P{i + 1}", "size": s} for i, s in enumerate(sizes)]
    action = choose("Strategy", [("FIRST", "First fit"), ("BEST", "Best fit"), ("WORST", "Worst fit"),
                                 ("ALL", "Compare all three")])
    strategies = memory.FIT_STRATEGIES if action == "ALL" else [action]
    for s in strategies:
        f = memory.contiguous_allocation(blocks, reqs, s)
        print("\n" + reporting.table(["Process", "Size", "Block", "Left in block"],
                                     [[a["pid"], a["size"], a["block"], a["left"]] for a in f.allocations]
                                     + [[w["pid"], w["size"], "WAITS", "-"] for w in f.waiting],
                                     f"{s} FIT: utilization {f.utilization}%, free left {f.free_left} KB"))


def memory_menu():
    if choose("Memory management", [("p", "Page replacement"), ("c", "Contiguous allocation")]) == "p":
        paging_menu()
    else:
        allocation_menu()


# ------------------------------------------------------------------ 3. deadlock
def read_matrix(name, n, m):
    print(f"{name}: one row per process, {m} numbers each")
    return [ask_list(f"  P{i}: ", count=m, minimum=0) for i in range(n)]


def banker_state():
    data = load("deadlock")["banker"]
    if choose("Banker's data", [("s", "Sample (5 processes, resources A B C)"), ("m", "Enter my own")]) == "s":
        return deadlock.BankerState(data["allocation"], data["maximum"], data["available"])
    n = ask_int("Number of processes (1-10): ", 1, 10)
    m = ask_int("Number of resource types (1-10): ", 1, 10)
    alloc = read_matrix("Allocation", n, m)
    maxm = read_matrix("Maximum", n, m)
    avail = ask_list(f"Available ({m} numbers): ", count=m, minimum=0)
    return deadlock.BankerState(alloc, maxm, avail)


def show_safety(state):
    res = deadlock.safety(state)
    rows = [[state.names[i], " ".join(map(str, state.allocation[i])), " ".join(map(str, state.maximum[i])),
             " ".join(map(str, res.need[i]))] for i in range(len(state.names))]
    print("\n" + reporting.table(["Process", "Allocation", "Maximum", "Need"], rows, f"Available = {state.available}"))
    print("\n".join("  " + s for s in res.steps))
    if res.safe:
        print("SAFE state. Safe sequence: < " + ", ".join(res.sequence) + " >")
    else:
        print("UNSAFE state. These processes cannot finish: " + ", ".join(res.unfinished))
    return res


def deadlock_menu():
    action = choose("Deadlock handling", [("safety", "Banker's safety algorithm"),
                                          ("request", "Banker's resource request"),
                                          ("detect", "Deadlock detection and recovery")])
    if action in ("safety", "request"):
        state = banker_state()
        show_safety(state)
        while action == "request":
            i = ask_int(f"Process making the request (0-{len(state.names) - 1}): ", 0, len(state.names) - 1)
            req = ask_list(f"Request ({len(state.available)} numbers): ", count=len(state.available), minimum=0)
            r = deadlock.request_resources(state, i, req)
            print(f"{r.decision}. {r.reason}")
            if r.granted:
                state = r.new_state
            again = ask("Another request? (y/n): ").lower()
            if again != "y":
                break
        return
    data = load("deadlock")["detection"]
    options = [(c["name"], f"Sample case: {c['name']}") for c in data] + [("manual", "Enter my own")]
    pick = choose("Detection data", options)
    if pick == "manual":
        n = ask_int("Number of processes (1-10): ", 1, 10)
        m = ask_int("Number of resource types (1-10): ", 1, 10)
        alloc = read_matrix("Allocation", n, m)
        req = read_matrix("Request", n, m)
        avail = ask_list(f"Available ({m} numbers): ", count=m, minimum=0)
    else:
        case = next(c for c in data if c["name"] == pick)
        alloc, req, avail = case["allocation"], case["request"], case["available"]
    d = deadlock.detect(alloc, req, avail)
    print("\n".join("  " + s for s in d.steps))
    if d.deadlock and ask("Recover by terminating processes? (y/n): ").lower() == "y":
        killed, _, steps = deadlock.recover(alloc, req, avail)
        print("\n".join("  " + s for s in steps))


# ------------------------------------------------------------------ 4. disk
def disk_menu():
    data = load("storage")
    options = [(k, f"Sample '{k}': head {w['head']}, {len(w['requests'])} requests")
               for k, w in data["workloads"].items()] + [("manual", "Enter my own")]
    pick = choose("Disk request queue", options)
    size = data.get("disk_size", 200)
    if pick == "manual":
        size = ask_int("Number of cylinders (e.g. 200): ", 1, 100000)
        head = ask_int(f"Current head position (0-{size - 1}): ", 0, size - 1)
        reqs = ask_list("Cylinder requests separated by spaces: ", minimum=0, maximum=size - 1)
        direction = choose("Head direction", [("up", "Towards higher cylinders"), ("down", "Towards 0")])
    else:
        w = data["workloads"][pick]
        head, reqs, direction = w["head"], w["requests"], w.get("direction", "up")
    action = choose("Algorithm", [*[(a, a) for a in storage.DISK_ALGORITHMS], ("ALL", "Compare all six")])
    algos = storage.DISK_ALGORITHMS if action == "ALL" else [action]
    results = [storage.disk_schedule(reqs, head, size, a, direction, data.get("count_jump", True)) for a in algos]
    for r in results:
        print(f"\n{r.algorithm}: " + " -> ".join(map(str, r.path)) + f"   total = {r.total}")
    if len(results) > 1:
        rows = [[r.algorithm, r.total, r.average_seek] for r in results]
        print("\n" + reporting.table(["Algorithm", "Total movement", "Avg seek"], rows))
        print("\n" + reporting.ascii_bars("Total head movement", [r[0] for r in rows], [r[1] for r in rows]))


# ------------------------------------------------------------------ main menu
def system_snapshot():
    script = SCRIPTS / "sysinfo.sh"
    try:
        run = subprocess.run(["bash", str(script)], capture_output=True, text=True, timeout=30)
        print(run.stdout)
        if run.returncode != 0:
            print("  ! " + run.stderr.strip())
    except (OSError, subprocess.TimeoutExpired) as exc:
        print(f"  ! Could not run {script.name}: {exc}")
        log.error("sysinfo.sh failed: %s", exc)


MENU = [
    ("CPU scheduling", scheduling_menu),
    ("Memory management (paging, allocation)", memory_menu),
    ("Deadlock handling (Banker's, detection)", deadlock_menu),
    ("Disk scheduling", disk_menu),
    ("Run full analysis (all modules, saves charts and report)", lambda: analysis.run_full_analysis()),
    ("System snapshot of this computer (Bash)", system_snapshot),
    ("View activity log", lambda: print(tail(25))),
]


def interactive():
    log.info("Interactive session started")
    while True:
        print("\n" + "=" * 52)
        print("        OS RESOURCE MANAGER - MAIN MENU")
        print("=" * 52)
        for i, (label, _) in enumerate(MENU, 1):
            print(f"  {i}. {label}")
        print("  0. Exit")
        print("  (type 'b' at any prompt to come back here)")
        try:
            pick = ask_int("Choice: ", 0, len(MENU))
        except BackToMenu:
            continue
        if pick == 0:
            log.info("Interactive session ended")
            print("Goodbye.")
            return
        label, func = MENU[pick - 1]
        log.info("Menu: %s", label)
        try:
            func()
        except BackToMenu:
            continue
        except ValidationError as exc:
            print(f"\n  ! Input error: {exc}")
            log.warning("Validation error in %s: %s", label, exc)
        except Exception as exc:          # keep the menu alive whatever happens
            print(f"\n  ! Unexpected error: {exc} (details in logs/activity.log)")
            log.exception("Unexpected error in %s", label)
        pause()


def main(argv=None):
    parser = argparse.ArgumentParser(description="OS Resource Manager simulator")
    parser.add_argument("--analyze", action="store_true", help="run the full analysis without the menu")
    parser.add_argument("--output", help="folder for the analysis output (default: output/)")
    parser.add_argument("--quiet", action="store_true", help="do not print the analysis to the screen")
    args = parser.parse_args(argv)
    try:
        if args.analyze:
            analysis.run_full_analysis(args.output, quiet=args.quiet)
        else:
            interactive()
    except KeyboardInterrupt:
        print("\nStopped by user.")
        log.info("Stopped by user (Ctrl+C)")
        return 130
    except ValidationError as exc:
        print(f"Error: {exc}")
        log.error("Validation error: %s", exc)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
