# OS Resource Manager

An integrated Python + Bash application that simulates the main resource-management jobs of an operating system (CPU scheduling, memory management, deadlock handling and disk scheduling), runs them on shared datasets, and compares the algorithms with tables, charts and written observations.

**Student:** Pranav Tripathi · Enrollment 2401010129 · B.Tech CSE Semester 5, Section B · K.R. Mangalam University
**Course:** Operating Systems

---

## 1. What it does

| Module | Algorithms | Measures |
|---|---|---|
| CPU scheduling | FCFS, SJF, SRTF, Priority (non-preemptive and preemptive), Round Robin | Gantt chart, CT, TAT, WT, RT, throughput, CPU utilisation, context switches |
| Memory management | FIFO, LRU, Optimal page replacement; first, best, worst fit allocation | page faults, hits, fault rate, Belady's anomaly; utilisation, waiting processes |
| Deadlock handling | Banker's safety and request algorithms; detection; recovery by termination | safe sequence, GRANTED / WAIT / UNSAFE / ERROR decision, deadlocked set |
| Disk scheduling | FCFS, SSTF, SCAN, C-SCAN, LOOK, C-LOOK | service order, total and average head movement |
| Bash layer | `run.sh`, `sysinfo.sh`, `ps_to_dataset.sh` | launcher, real machine snapshot (`ps`, `free`, `df`), live processes turned into a scheduling workload |

Everything runs from **one menu** (`./run.sh`) or **one command** (`./run.sh all`). All modules share the validation, logging and reporting code. See `docs/DESIGN.md` for the architecture.

## 2. Folder structure

```
os_resource_manager/
├── run.sh                  Bash launcher (menu, analyze, test, sysinfo, live, demo, all, clean)
├── main.py                 menu-driven program and --analyze mode
├── osrm/                   Python package
│   ├── scheduling.py       CPU scheduling engine
│   ├── memory.py           paging + contiguous allocation
│   ├── deadlock.py         Banker's, detection, recovery
│   ├── storage.py          disk scheduling
│   ├── analysis.py         runs every module on the shared datasets and compares them
│   ├── reporting.py        text tables, ASCII bars, PNG charts, CSV
│   ├── validation.py       input checks (ValidationError)
│   ├── datasets.py         loads data/*.json
│   └── logger.py           logs/activity.log
├── scripts/
│   ├── sysinfo.sh          snapshot of this computer
│   └── ps_to_dataset.sh    live processes -> data/live_processes.json
├── data/                   shared datasets (scheduling, memory, deadlock, storage .json)
├── samples/                sample menu sessions (input files)
├── tests/                  53 automated test cases
├── docs/                   DESIGN.md, architecture.png, workflow.png
├── output/                 created when you run it: charts, csv, traces, analysis_report.md
└── logs/                   activity.log
```

## 3. Requirements

- Ubuntu (or WSL Ubuntu on Windows), Bash
- Python 3.8 or newer (no extra package needed for the program itself)
- `python3-matplotlib` (optional, only for the PNG charts; without it the program prints ASCII charts)

## 4. Setup and execution (Ubuntu / WSL)

**Batch 1: copy the project into Linux and open it**

```bash
cd ~/myfolder                                                    # go to your working folder
cp /mnt/c/Users/<your-windows-name>/Downloads/os_resource_manager.zip .   # copy the zip from Windows Downloads
sudo apt install -y unzip python3-matplotlib                     # unzip tool + chart library (one time only)
unzip os_resource_manager.zip                                    # extract the project
cd os_resource_manager                                           # enter the project folder
```

**Batch 2: check and run everything**

```bash
chmod +x run.sh                 # allow run.sh to be executed
./run.sh setup                  # checks Python and matplotlib, makes the scripts executable
./run.sh test                   # runs the 53 test cases (should end with "OK")
./run.sh analyze                # runs all modules on the shared datasets, saves report + charts
ls output output/charts         # see what was created
```

**Batch 3: use the program**

```bash
./run.sh                        # opens the interactive menu
./run.sh sysinfo                # snapshot of this computer (CPU, memory, disk, processes)
./run.sh live 5                 # turns 5 running processes into a scheduling workload
./run.sh demo                   # replays the sample sessions and saves them in output/traces/
tail -20 logs/activity.log      # last 20 logged actions
```

`./run.sh all` does setup + sysinfo + test + analyze + demo in one go. `./run.sh clean` deletes the generated output and logs. To open the charts in Windows from WSL: `explorer.exe output/charts`.

## 5. Using the menu

```
====================================================
        OS RESOURCE MANAGER - MAIN MENU
====================================================
  1. CPU scheduling
  2. Memory management (paging, allocation)
  3. Deadlock handling (Banker's, detection)
  4. Disk scheduling
  5. Run full analysis (all modules, saves charts and report)
  6. System snapshot of this computer (Bash)
  7. View activity log
  0. Exit
  (type 'b' at any prompt to come back here)
```

Each module lets you pick a **sample dataset** or **enter your own** values. Type `b` at any prompt to go back. A wrong value is never fatal: the program says what is wrong and asks again.

## 6. Sample input

### 6.1 Shared datasets (`data/`)

| Module | Dataset |
|---|---|
| CPU scheduling | `mixed`: P1 (AT 0, BT 8, Pr 3), P2 (1, 4, 1), P3 (2, 9, 4), P4 (3, 5, 2), P5 (5, 2, 5), P6 (6, 6, 2); quantum 3. `convoy`: P1 (0, 24, 3), P2 (0, 3, 1), P3 (0, 3, 2), P4 (0, 2, 1) |
| Paging | reference string 7 0 1 2 0 3 0 4 2 3 0 3 2 1 2 0 1 7 0 1, 3 frames; Belady string 1 2 3 4 1 2 5 1 2 3 4 5 |
| Allocation | blocks 100 500 200 300 600 KB; processes 212, 417, 112, 426 KB |
| Banker's | Available 3 3 2; Allocation and Maximum for P0–P4 (textbook example); requests P1 (1 0 2), P4 (3 3 0), P0 (0 2 0), P3 (1 0 0) |
| Disk | 200 cylinders; `standard`: head 53, up, 98 183 37 122 14 124 65 67; `heavy`: head 100, down, 20 requests |

Priority rule: **smaller number = higher priority**.

### 6.2 Example manual entry (menu 1 → 3)

```
Number of processes (1-20): 4
For each process enter: arrival burst [priority]   e.g.  0 5 2   (smaller priority = higher)
  P1: 0 5 1
  P2: 1 3 2
  P3: 2 8 1
  P4: 3 6 3
```

### 6.3 Sample sessions (`samples/`)

| File | What it shows |
|---|---|
| `01_scheduling.txt` | SRTF on `mixed` (Gantt + table), then a manual workload with all algorithms compared |
| `02_memory.txt` | LRU frame-by-frame trace, Belady's anomaly sweep, all three fits compared |
| `03_deadlock.txt` | Banker's safety, three requests (granted, wait, unsafe), detection + recovery |
| `04_disk.txt` | manual queue with all six algorithms compared, then C-SCAN on the heavy queue |
| `05_invalid_input.txt` | eight bad inputs (out of range, text, negative, decimal, zero quantum, cylinder beyond disk) all rejected and re-asked |

Run one with `python3 main.py < samples/03_deadlock.txt`, or all with `./run.sh demo`.

## 7. Output

| Path | Contents |
|---|---|
| `output/analysis_report.md` | full analysis: every comparison table, chart and observation |
| `output/charts/` | bar charts, line charts, Gantt charts and disk head paths (PNG) |
| `output/csv/` | every comparison table as CSV (opens in Excel) |
| `output/traces/` | step-by-step traces per module, full console output, the replayed sample sessions |
| `output/system_snapshot.txt` | the Bash snapshot of the machine |
| `output/test_results.txt` | test suite output |
| `logs/activity.log` | every action from Python and Bash, with time and level |

### Sample results (shared datasets)

| Comparison | Result |
|---|---|
| CPU, `mixed` | lowest average WT: SRTF 8.33; FCFS 13.0; RR (q = 3) 17.67 with 12 context switches |
| CPU, `convoy` | FCFS average WT 20.25 vs SJF 3.75 (convoy effect, 5.4×) |
| Paging, 3 frames | FIFO 15, LRU 12, Optimal 9 faults |
| Belady | FIFO: 9 faults with 3 frames, 10 with 4 |
| Allocation | only best fit places all four processes |
| Banker's | safe sequence < P1, P3, P4, P0, P2 > |
| Disk, `standard` | FCFS 640, SSTF 236, SCAN 331, C-SCAN 382, LOOK 299, C-LOOK 322 cylinders |

## 8. Test cases

Run with `./run.sh test` (or `python3 -m unittest discover -s tests -v`). 53 tests in 5 files; all pass.

| ID | Type | Test |
|---|---|---|
| TC-S01 | valid | FCFS runs processes in arrival order |
| TC-S02 | valid | SRTF matches the hand-solved class problem (avg TAT 23.25, avg WT 9.5) |
| TC-S03 | valid | Round Robin (q = 2): new arrivals join before the preempted process |
| TC-S04 | valid | Non-preemptive priority with a tie and an idle gap |
| TC-S05 | valid | Preemptive priority: an equal-priority newcomer does not preempt |
| TC-S06 | valid | SJF picks the shortest job among those that have arrived |
| TC-S07 | boundary | One process: waiting 0, no context switch, every algorithm agrees |
| TC-S08 | boundary | CPU stays idle until the first process arrives |
| TC-S09 | boundary | Equal arrival times are served in input order |
| TC-S10 | boundary | RR with a quantum larger than every burst gives the FCFS result |
| TC-S11 | random | 200 random workloads: every process finishes, busy time = total burst |
| TC-S12 | invalid | Negative arrival time is rejected |
| TC-S13 | invalid | Burst time 0 is rejected |
| TC-S14 | invalid | Quantum 0 is rejected |
| TC-S15 | invalid | Empty list, duplicate ids, text values and unknown algorithms are rejected |
| TC-M01 | valid | Textbook string, 3 frames: FIFO 15, LRU 12, Optimal 9 faults |
| TC-M02 | valid | FIFO shows Belady's anomaly (9 → 10 faults); LRU does not |
| TC-M03 | valid | Optimal never has more faults than FIFO or LRU (frames 1–7) |
| TC-M04 | boundary | Frames ≥ distinct pages: only the first use of each page faults |
| TC-M05 | boundary | One frame faults every time the page changes |
| TC-M06 | valid | Trace: hits + faults = references and frames never overflow |
| TC-M07 | invalid | 0 frames, negative page, empty string, unknown algorithm |
| TC-M08 | valid | Best fit places all 4; first and worst fit leave P4 (426 KB) waiting |
| TC-M09 | boundary | Exact fit leaves 0 KB; a request bigger than every block waits |
| TC-M10 | invalid | Zero-size process, negative block, no blocks, unknown strategy |
| TC-D01 | valid | Textbook state is safe with sequence P1, P3, P4, P0, P2 |
| TC-D02 | valid | With Available 1 1 1 the state is unsafe; P0, P2, P4 cannot finish |
| TC-D03 | valid | P1 (1,0,2) granted; then P4 (3,3,0) WAIT and P0 (0,2,0) UNSAFE |
| TC-D04 | invalid | A request larger than the remaining Need is an ERROR |
| TC-D05 | boundary | One process, one resource, nothing more needed: safe |
| TC-D06 | invalid | Allocation above Maximum, ragged rows, negative values, bad request |
| TC-D07 | valid | Detection: textbook case without deadlock |
| TC-D08 | valid | Detection: after P2 asks for one more C, P1–P4 are deadlocked |
| TC-D09 | valid | Recovery terminates the largest holder (P2); system becomes deadlock-free |
| TC-D10 | invalid | Request matrix with the wrong shape |
| TC-K01 | valid | Head 53 up: FCFS 640, SSTF 236, SCAN 331, C-SCAN 382, LOOK 299, C-LOOK 322 |
| TC-K02 | valid | Head 53 down: SCAN 236, C-SCAN 386, LOOK 208, C-LOOK 326 |
| TC-K03 | valid | `count_jump=False` leaves the C-SCAN / C-LOOK return jump out |
| TC-K04 | boundary | Empty queue moves the head 0 cylinders |
| TC-K05 | boundary | A request at the current head position costs 0 |
| TC-K06 | boundary | Head at cylinder 0 and at the last cylinder |
| TC-K07 | random | 300 random queues: every algorithm visits every request |
| TC-K08 | invalid | Request beyond the disk, negative head, bad direction, unknown algorithm |
| TC-I01 | integration | Full analysis writes the report, CSV files and traces |
| TC-I02 | integration | `main.py --analyze --quiet` exits with status 0 |
| TC-I03 | invalid | Missing dataset file and broken JSON give a clear ValidationError |
| TC-I04 | invalid | Input parsing: commas or spaces accepted; decimals, text, booleans rejected |
| TC-I05 | integration | Running an algorithm writes a line to `logs/activity.log` |
| TC-I06 | integration | Bash: `ps_to_dataset.sh` builds a workload the scheduler accepts; a bad count fails |
| TC-I07 | integration | Bash: `run.sh help` succeeds and an unknown command fails |
| TC-I08 | invalid | Menu: invalid choices are re-asked and the program exits cleanly on 0 |
| TC-I09 | integration | Menu end to end: scheduling compare-all, then disk compare-all |
| TC-I10 | integration | Every `samples/*.txt` session finishes; all 8 bad inputs are re-asked |

## 9. Reliability

- **Validation:** every number is checked for type and range (`validation.py`); matrices are checked for shape; Allocation must not exceed Maximum.
- **Exception handling:** input errors raise `ValidationError`; the menu catches it, shows the message and continues. Any unexpected error is logged with its traceback and the menu keeps running. Ctrl+C and closed input exit cleanly.
- **Logging:** `logs/activity.log` records each menu action, algorithm run, warning and error from Python, and each Bash action, in one format: `time | level | source | message`.
- **Charts are optional:** if matplotlib is missing or a chart fails, the program prints a note and carries on.

## 10. Screenshots to include

1. `./run.sh setup` and the end of `./run.sh test` (53 tests, OK)
2. Main menu
3. CPU scheduling: Gantt + table for one algorithm, and "compare all"
4. Memory: LRU trace and Belady sweep
5. Deadlock: Banker's safety sequence and a request decision
6. Disk: compare all six
7. Invalid input being rejected and re-asked
8. `./run.sh sysinfo` and `./run.sh live 5`
9. `tail -20 logs/activity.log`
10. Two or three charts from `output/charts/`

## 11. Troubleshooting

| Problem | Fix |
|---|---|
| `Permission denied` on `./run.sh` | `chmod +x run.sh` or run `bash run.sh` |
| `matplotlib: NOT installed` | `sudo apt install -y python3-matplotlib` (the program still works without it) |
| `unzip: command not found` | `sudo apt install -y unzip` |
| `$'\r': command not found` (file edited in Windows) | `sed -i 's/\r$//' run.sh scripts/*.sh` |
