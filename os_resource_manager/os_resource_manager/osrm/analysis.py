"""Phase 3 analysis: run every module on the shared datasets, compare the algorithms,
save tables (CSV), charts (PNG), step-by-step traces and a Markdown report."""

from datetime import datetime
from pathlib import Path

from . import deadlock, memory, reporting, scheduling, storage
from .datasets import load
from .logger import get_logger

log = get_logger("analysis")

SCHED_HEADERS = ["Algorithm", "Avg WT", "Avg TAT", "Avg RT", "Throughput", "CPU %", "Ctx switches"]


def _sched_rows(results):
    rows = []
    for r in results:
        name = r.algorithm + (f" (q={r.quantum})" if r.quantum else "")
        m = r.metrics
        rows.append([name, m["avg_waiting"], m["avg_turnaround"], m["avg_response"],
                     m["throughput"], m["cpu_utilization"], m["context_switches"]])
    return rows


def process_table(result):
    headers = ["PID", "AT", "BT", "PR", "CT", "TAT", "WT", "RT"]
    rows = [[r["pid"], r["arrival"], r["burst"], r["priority"], r["completion"],
             r["turnaround"], r["waiting"], r["response"]] for r in result.rows]
    return reporting.table(headers, rows)


# ------------------------------------------------------------------ scheduling
def analyse_scheduling(data, out, say):
    quantum = data.get("quantum", 2)
    report, obs = [], []
    say("\n" + "=" * 70 + "\nMODULE 1: CPU SCHEDULING\n" + "=" * 70)
    trace_lines = []
    workloads = data["workloads"]
    for wname, wl in workloads.items():
        results = scheduling.compare_all(wl["processes"], quantum)
        rows = _sched_rows(results)
        title = f"Workload '{wname}' ({len(wl['processes'])} processes, RR quantum {quantum})"
        tbl = reporting.table(SCHED_HEADERS, rows, title)
        say("\n" + tbl)
        say("\n" + reporting.ascii_bars("Average waiting time", [r[0].split(" ")[0] for r in rows],
                                        [r[1] for r in rows]))
        reporting.save_csv(out / "csv" / f"scheduling_{wname}.csv", SCHED_HEADERS, rows)
        reporting.bar_chart(out / "charts" / f"scheduling_{wname}.png",
                            f"CPU scheduling comparison: '{wname}' workload",
                            [r[0].split(" ")[0] for r in rows],
                            {"Avg waiting time": [r[1] for r in rows],
                             "Avg turnaround time": [r[2] for r in rows],
                             "Avg response time": [r[3] for r in rows]},
                            "Time units")
        report.append(f"### Workload: {wname}\n\n{wl.get('description', '')}\n\n```\n{tbl}\n```\n\n"
                      f"![Scheduling comparison {wname}](charts/scheduling_{wname}.png)\n")
        trace_lines.append(f"===== Workload: {wname} =====")
        for r in results:
            trace_lines.append(f"\n--- {scheduling.ALGORITHMS[r.algorithm]}"
                               + (f" (quantum {r.quantum})" if r.quantum else "") + " ---")
            trace_lines.append("Gantt: " + scheduling.gantt_text(r.gantt))
            trace_lines.append(process_table(r))
            if wname == next(iter(workloads)):
                reporting.gantt_chart(out / "charts" / f"gantt_{r.algorithm.lower()}.png",
                                      f"Gantt chart: {scheduling.ALGORITHMS[r.algorithm]}", r.gantt)
        best = min(results, key=lambda r: r.metrics["avg_waiting"])
        worst = max(results, key=lambda r: r.metrics["avg_waiting"])
        fastest = min(results, key=lambda r: r.metrics["avg_response"])
        obs.append(f"'{wname}': lowest average waiting time is {best.algorithm} "
                   f"({best.metrics['avg_waiting']}), highest is {worst.algorithm} ({worst.metrics['avg_waiting']}); "
                   f"best average response time is {fastest.algorithm} ({fastest.metrics['avg_response']}).")
        fcfs = next(r for r in results if r.algorithm == "FCFS")
        if best.algorithm != "FCFS" and best.metrics["avg_waiting"] > 0:
            ratio = round(fcfs.metrics["avg_waiting"] / best.metrics["avg_waiting"], 2)
            obs.append(f"'{wname}': FCFS waits {ratio}x longer than {best.algorithm} on average, because short "
                       f"jobs queue behind long ones (convoy effect).")
        rr = next(r for r in results if r.algorithm == "RR")
        most = max(results, key=lambda r: (r.metrics["context_switches"], r.algorithm == "RR"))
        if most.algorithm == "RR":
            obs.append(f"'{wname}': RR makes the most context switches ({rr.metrics['context_switches']}), "
                       f"because it preempts the running process every {rr.quantum} time units.")
        else:
            obs.append(f"'{wname}': {most.algorithm} makes the most context switches "
                       f"({most.metrics['context_switches']}); RR makes {rr.metrics['context_switches']}.")

    # Round Robin quantum sweep on the first workload
    first_name, first = next(iter(workloads.items()))
    quanta = data.get("quantum_sweep", [1, 2, 3, 4, 5, 6, 8, 10])
    sweep = scheduling.quantum_sweep(first["processes"], quanta)
    rows = [[q, r.metrics["avg_waiting"], r.metrics["avg_turnaround"], r.metrics["avg_response"],
             r.metrics["context_switches"]] for q, r in zip(quanta, sweep)]
    headers = ["Quantum", "Avg WT", "Avg TAT", "Avg RT", "Ctx switches"]
    tbl = reporting.table(headers, rows, f"Round Robin time-quantum sweep ('{first_name}' workload)")
    say("\n" + tbl)
    reporting.save_csv(out / "csv" / "rr_quantum_sweep.csv", headers, rows)
    reporting.line_chart(out / "charts" / "rr_quantum_sweep.png", "Round Robin: effect of the time quantum",
                         quanta, {"Avg waiting time": [r[1] for r in rows],
                                  "Avg response time": [r[3] for r in rows],
                                  "Context switches": [r[4] for r in rows]},
                         "Time quantum", "Time units / count")
    report.append(f"### Round Robin time quantum\n\n```\n{tbl}\n```\n\n![RR quantum sweep](charts/rr_quantum_sweep.png)\n")
    fcfs_wt = scheduling.schedule(first["processes"], "FCFS").metrics["avg_waiting"]
    best_q = min(zip(quanta, sweep), key=lambda x: (x[1].metrics["avg_waiting"], x[0]))
    obs.append(f"RR quantum: raising q from {quanta[0]} to {quanta[-1]} cuts context switches from {rows[0][4]} "
               f"to {rows[-1][4]}, but average response time rises from {rows[0][3]} to {rows[-1][3]}. "
               f"The lowest average waiting time here is at q={best_q[0]} ({best_q[1].metrics['avg_waiting']}).")
    if sweep[-1].metrics["avg_waiting"] == fcfs_wt:
        obs.append(f"RR quantum: at q={quanta[-1]} every process finishes in one slice, so RR gives exactly "
                   f"the FCFS result (avg WT {fcfs_wt}).")
    reporting.save_text(out / "traces" / "scheduling_trace.txt", "\n".join(trace_lines))
    return report, obs


# ------------------------------------------------------------------ memory
def analyse_memory(data, out, say):
    report, obs, trace = [], [], []
    say("\n" + "=" * 70 + "\nMODULE 2: MEMORY MANAGEMENT\n" + "=" * 70)
    refs = data["reference_string"]
    frames = data.get("frames", 3)
    results = memory.compare_paging(refs, frames)
    headers = ["Algorithm", "Frames", "Faults", "Hits", "Fault rate %", "Hit ratio %"]
    rows = [[r.algorithm, r.frames, r.faults, r.hits, r.fault_rate, r.hit_ratio] for r in results]
    tbl = reporting.table(headers, rows, f"Page replacement, {len(refs)} references, {frames} frames")
    say("\n" + tbl)
    say("\n" + reporting.ascii_bars("Page faults", [r[0] for r in rows], [r[2] for r in rows]))
    reporting.save_csv(out / "csv" / "paging_comparison.csv", headers, rows)
    reporting.bar_chart(out / "charts" / "paging_comparison.png",
                        f"Page faults with {frames} frames", [r[0] for r in rows],
                        {"Page faults": [r[2] for r in rows], "Hits": [r[3] for r in rows]}, "Count")
    for r in results:
        trace.append(f"\n--- {r.algorithm}, {r.frames} frames ---")
        trace.append(reporting.table(["Step", "Page", "Frames", "Result", "Evicted"],
                                     [[t["step"], t["page"], " ".join(map(str, t["frames"])), t["status"],
                                       t["evicted"] if t["evicted"] is not None else "-"] for t in r.trace]))

    counts = data.get("frame_sweep", [1, 2, 3, 4, 5, 6, 7])
    sweep = memory.frames_sweep(refs, counts)
    sweep_rows = [[f] + [sweep[a][i] for a in memory.PAGE_ALGORITHMS] for i, f in enumerate(counts)]
    sweep_tbl = reporting.table(["Frames", *memory.PAGE_ALGORITHMS], sweep_rows, "Page faults as frames increase")
    say("\n" + sweep_tbl)
    reporting.save_csv(out / "csv" / "paging_frame_sweep.csv", ["Frames", *memory.PAGE_ALGORITHMS], sweep_rows)
    reporting.line_chart(out / "charts" / "paging_frame_sweep.png", "Page faults vs number of frames",
                         counts, sweep, "Frames", "Page faults")

    bel_refs = data.get("belady_string")
    bel_text = ""
    if bel_refs:
        bel_counts = data.get("belady_frames", [1, 2, 3, 4, 5])
        bel_faults = [memory.page_replacement(bel_refs, f, "FIFO").faults for f in bel_counts]
        anomalies = memory.belady_check(bel_refs, bel_counts)
        bel_tbl = reporting.table(["Frames", "FIFO faults"], list(zip(bel_counts, bel_faults)),
                                  "Belady's anomaly check (FIFO)")
        say("\n" + bel_tbl)
        reporting.line_chart(out / "charts" / "belady_fifo.png", "Belady's anomaly: FIFO faults vs frames",
                             bel_counts, {"FIFO": bel_faults}, "Frames", "Page faults")
        bel_text = f"\n```\n{bel_tbl}\n```\n\n![Belady](charts/belady_fifo.png)\n"
        for f1, x1, f2, x2 in anomalies:
            obs.append(f"Belady's anomaly: FIFO has {x1} faults with {f1} frames but {x2} faults with {f2} frames "
                       f"(more frames, more faults). LRU and Optimal never show this.")

    best = min(results, key=lambda r: r.faults)
    worst = max(results, key=lambda r: r.faults)
    obs.append(f"Paging ({frames} frames): {best.algorithm} has the fewest faults ({best.faults}), "
               f"{worst.algorithm} the most ({worst.faults}). Optimal is the lower bound but needs future knowledge.")

    # contiguous allocation
    blocks, reqs = data["blocks"], data["requests"]
    fits = memory.compare_fits(blocks, reqs)
    fit_headers = ["Strategy", "Allocated", "Waiting", "Used KB", "Utilization %", "Free KB left", "Largest free"]
    fit_rows = [[f.strategy + " FIT", f"{len(f.allocations)}/{len(reqs)}",
                 ", ".join(w["pid"] for w in f.waiting) or "-", f.allocated, f.utilization,
                 f.free_left, f.largest_free] for f in fits]
    fit_tbl = reporting.table(fit_headers, fit_rows, f"Contiguous allocation: blocks {blocks} KB")
    say("\n" + fit_tbl)
    for f in fits:
        detail = reporting.table(["Process", "Size", "Block", "Left in block"],
                                 [[a["pid"], a["size"], a["block"], a["left"]] for a in f.allocations]
                                 + [[w["pid"], w["size"], "WAITS", "-"] for w in f.waiting],
                                 f"{f.strategy} FIT")
        say(detail)
        trace.append("\n" + detail)
    reporting.save_csv(out / "csv" / "allocation_comparison.csv", fit_headers, fit_rows)
    reporting.bar_chart(out / "charts" / "allocation_comparison.png", "Contiguous allocation: memory utilization",
                        [r[0] for r in fit_rows], {"Utilization %": [r[4] for r in fit_rows]}, "Percent of memory used")
    full = [f.strategy for f in fits if not f.waiting]
    obs.append("Allocation: " + (f"{', '.join(s + ' FIT' for s in full)} placed every process"
                                 if full else "no strategy placed every process")
               + "; " + "; ".join(f"{f.strategy} FIT left {', '.join(w['pid'] for w in f.waiting)} waiting"
                                  for f in fits if f.waiting) + ".")

    reporting.save_text(out / "traces" / "memory_trace.txt", "\n".join(trace))
    report.append(f"### Page replacement\n\n```\n{tbl}\n```\n\n![Paging](charts/paging_comparison.png)\n\n"
                  f"```\n{sweep_tbl}\n```\n\n![Frame sweep](charts/paging_frame_sweep.png)\n{bel_text}\n"
                  f"### Contiguous allocation\n\n```\n{fit_tbl}\n```\n\n![Allocation](charts/allocation_comparison.png)\n")
    return report, obs


# ------------------------------------------------------------------ deadlock
def analyse_deadlock(data, out, say):
    report, obs, trace = [], [], []
    say("\n" + "=" * 70 + "\nMODULE 3: DEADLOCK HANDLING\n" + "=" * 70)
    b = data["banker"]
    state = deadlock.BankerState(b["allocation"], b["maximum"], b["available"])
    res = deadlock.safety(state)
    names = state.names
    m = len(state.available)
    headers = ["Process", "Allocation", "Maximum", "Need"]
    rows = [[names[i], " ".join(map(str, state.allocation[i])), " ".join(map(str, state.maximum[i])),
             " ".join(map(str, res.need[i]))] for i in range(len(names))]
    tbl = reporting.table(headers, rows, f"Banker's algorithm: Available = {state.available}")
    say("\n" + tbl)
    say("\n".join("  " + s for s in res.steps))
    verdict = ("SAFE, sequence < " + ", ".join(res.sequence) + " >") if res.safe else \
        ("UNSAFE, cannot finish: " + ", ".join(res.unfinished))
    say("Result: " + verdict)
    trace += ["Banker's safety algorithm", tbl, *res.steps, "Result: " + verdict]
    obs.append(f"Banker's: the state is {verdict}.")

    req_rows = []
    current = state                       # requests arrive one after another
    for rq in b.get("requests", []):
        r = deadlock.request_resources(current, rq["process"], rq["request"])
        req_rows.append([names[rq["process"]], " ".join(map(str, rq["request"])),
                         r.decision, r.reason])
        trace.append(f"Request {names[rq['process']]} {rq['request']} (Available {current.available}): {r.reason}")
        if r.granted:
            current = r.new_state
    req_tbl = ""
    if req_rows:
        req_tbl = reporting.table(["Process", "Request", "Decision", "Reason"], req_rows,
                                  "Resource requests, handled in order (a granted request changes the state)")
        say("\n" + req_tbl)
        reporting.save_csv(out / "csv" / "banker_requests.csv", ["Process", "Request", "Decision", "Reason"], req_rows)
        words = {"GRANTED": "granted", "WAIT": "waits (not enough available)",
                 "UNSAFE": "refused (state would be unsafe)", "ERROR": "rejected (more than its Need)"}
        obs.append("Requests in order: " + "; ".join(f"{r[0]} ({r[1]}) {words.get(r[2], r[2])}" for r in req_rows) + ".")

    det_rows = []
    for case in data.get("detection", []):
        d = deadlock.detect(case["allocation"], case["request"], case["available"])
        say(f"\nDetection - {case['name']}")
        say("\n".join("  " + s for s in d.steps))
        trace += [f"\nDetection - {case['name']}", *d.steps]
        victims = "-"
        if d.deadlock:
            killed, final, steps = deadlock.recover(case["allocation"], case["request"], case["available"])
            say("  Recovery:")
            say("\n".join("    " + s for s in steps))
            trace += ["Recovery:", *steps]
            victims = ", ".join(killed)
            obs.append(f"Detection '{case['name']}': deadlock among {', '.join(d.deadlocked)}; "
                       f"terminating {victims} (largest holder first) clears it.")
        else:
            obs.append(f"Detection '{case['name']}': no deadlock, every process can finish "
                       f"({' -> '.join(d.finish_order)}).")
        det_rows.append([case["name"], "YES" if d.deadlock else "NO", ", ".join(d.deadlocked) or "-", victims])
    det_tbl = reporting.table(["Case", "Deadlock", "Deadlocked processes", "Terminated in recovery"], det_rows,
                              "Deadlock detection summary")
    say("\n" + det_tbl)
    reporting.save_csv(out / "csv" / "deadlock_detection.csv",
                       ["Case", "Deadlock", "Deadlocked processes", "Terminated in recovery"], det_rows)
    reporting.save_text(out / "traces" / "deadlock_trace.txt", "\n".join(trace))
    report.append(f"```\n{tbl}\n```\n\nResult: **{verdict}**\n\n```\n{req_tbl}\n```\n\n```\n{det_tbl}\n```\n")
    return report, obs


# ------------------------------------------------------------------ storage
def analyse_storage(data, out, say):
    report, obs, trace = [], [], []
    say("\n" + "=" * 70 + "\nMODULE 4: DISK SCHEDULING\n" + "=" * 70)
    headers = ["Algorithm", "Total movement", "Avg seek", "Service order"]
    for wname, wl in data["workloads"].items():
        results = storage.compare_disk(wl["requests"], wl["head"], data.get("disk_size", 200),
                                       wl.get("direction", "up"), data.get("count_jump", True))
        rows = [[r.algorithm, r.total, r.average_seek, " ".join(map(str, r.path))] for r in results]
        tbl = reporting.table(headers, rows, f"Workload '{wname}': head {wl['head']}, "
                                             f"direction {wl.get('direction', 'up')}, {len(wl['requests'])} requests")
        say("\n" + tbl)
        say("\n" + reporting.ascii_bars("Total head movement (cylinders)", [r[0] for r in rows], [r[1] for r in rows]))
        reporting.save_csv(out / "csv" / f"disk_{wname}.csv", headers, rows)
        reporting.bar_chart(out / "charts" / f"disk_{wname}.png", f"Disk scheduling: '{wname}' workload",
                            [r[0] for r in rows], {"Total head movement": [r[1] for r in rows]}, "Cylinders")
        reporting.disk_path_chart(out / "charts" / f"disk_paths_{wname}.png",
                                  f"Head movement paths: '{wname}' workload", results)
        for r in results:
            trace.append(f"\n--- {wname}: {r.algorithm} ---")
            trace += [f"  {a:>3} -> {b:>3} : {d:>3}" + ("  (return jump)" if j else "") for a, b, d, j in r.moves]
            trace.append(f"  Total = {r.total}")
        best = min(results, key=lambda r: r.total)
        worst = max(results, key=lambda r: r.total)
        fcfs = next(r for r in results if r.algorithm == "FCFS")
        saving = round(100 * (fcfs.total - best.total) / fcfs.total, 1) if fcfs.total else 0
        obs.append(f"Disk '{wname}': {best.algorithm} has the least head movement ({best.total}), "
                   f"{worst.algorithm} the most ({worst.total}); {best.algorithm} saves {saving}% over FCFS.")
        scan = next(r for r in results if r.algorithm == "SCAN")
        look = next(r for r in results if r.algorithm == "LOOK")
        if scan.total > look.total:
            obs.append(f"Disk '{wname}': LOOK saves {scan.total - look.total} cylinders over SCAN by turning at the "
                       f"last request instead of the disk edge.")
        report.append(f"### Workload: {wname}\n\n```\n{tbl}\n```\n\n![Disk {wname}](charts/disk_{wname}.png)\n\n"
                      f"![Paths {wname}](charts/disk_paths_{wname}.png)\n")
    reporting.save_text(out / "traces" / "storage_trace.txt", "\n".join(trace))
    return report, obs


# ------------------------------------------------------------------ everything
def run_full_analysis(output_dir=None, data_dir=None, quiet=False):
    out = reporting.ensure_dirs(output_dir)
    lines = []

    def say(text=""):
        lines.append(text)
        if not quiet:
            print(text)

    def data(name):
        return load(Path(data_dir) / f"{name}.json" if data_dir else name)

    log.info("Full analysis started")
    sections = [
        ("1. CPU scheduling", analyse_scheduling, "scheduling"),
        ("2. Memory management", analyse_memory, "memory"),
        ("3. Deadlock handling", analyse_deadlock, "deadlock"),
        ("4. Disk scheduling", analyse_storage, "storage"),
    ]
    body, all_obs = [], []
    for title, func, name in sections:
        part, obs = func(data(name), out, say)
        body.append(f"## {title}\n\n" + "\n".join(part))
        all_obs.append((title, obs))

    say("\n" + "=" * 70 + "\nOBSERVATIONS\n" + "=" * 70)
    for title, obs in all_obs:
        say(title)
        for o in obs:
            say("  - " + o)

    snapshot = out / "system_snapshot.txt"
    host = f"\n## Host system snapshot (from scripts/sysinfo.sh)\n\n```\n{snapshot.read_text()}\n```\n" \
        if snapshot.exists() else ""
    md = [f"# OS Resource Manager: analysis report\n\nGenerated {datetime.now():%Y-%m-%d %H:%M}\n",
          *body, "## Observations\n",
          *[f"**{t}**\n\n" + "\n".join(f"- {o}" for o in obs) + "\n" for t, obs in all_obs], host]
    reporting.save_text(out / "analysis_report.md", "\n".join(md))
    reporting.save_text(out / "traces" / "console_output.txt", "\n".join(lines))
    say(f"\nSaved: {out / 'analysis_report.md'}, charts in {out / 'charts'}, CSV in {out / 'csv'}, "
        f"traces in {out / 'traces'}")
    log.info("Full analysis finished")
    return all_obs
