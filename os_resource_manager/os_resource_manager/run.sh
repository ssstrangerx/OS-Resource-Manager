#!/usr/bin/env bash
# OS Resource Manager launcher.
#
#   ./run.sh            interactive menu
#   ./run.sh analyze    full analysis on the shared datasets (tables, charts, report)
#   ./run.sh test       run the test suite and save output/test_results.txt
#   ./run.sh sysinfo    snapshot of this computer (CPU, memory, disk, processes)
#   ./run.sh live [n]   turn n live processes into a scheduling dataset
#   ./run.sh demo       feed samples/*.txt to the menu and save each session in output/traces/
#   ./run.sh setup      check Python and matplotlib
#   ./run.sh all        setup + sysinfo + test + analyze + demo (everything for the submission)
#   ./run.sh clean      delete generated output and logs

set -u
cd "$(dirname "$0")"
mkdir -p logs output
LOG="logs/activity.log"

log() {   # same line format as the Python logger
  echo "$(date '+%Y-%m-%d %H:%M:%S') | ${2:-INFO   } | bash            | $1" >> "$LOG"
}

need_python() {
  if ! command -v python3 >/dev/null 2>&1; then
    echo "Python 3 is not installed. Install it with:  sudo apt install -y python3"
    log "python3 missing" "ERROR  "
    exit 1
  fi
}

setup() {
  need_python
  echo "Python      : $(python3 --version 2>&1)"
  if python3 -c 'import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)'; then
    echo "Version     : OK (3.8 or newer)"
  else
    echo "Version     : too old, Python 3.8 or newer is needed"
    exit 1
  fi
  if python3 -c 'import matplotlib' 2>/dev/null; then
    echo "matplotlib  : installed (PNG charts will be created)"
  else
    echo "matplotlib  : NOT installed - the program still runs, but PNG charts are skipped."
    echo "              Install it with:  sudo apt install -y python3-matplotlib"
  fi
  chmod +x run.sh main.py scripts/*.sh
  echo "Scripts     : executable"
  log "setup checked environment"
}

run_tests() {
  need_python
  echo "Running test suite..."
  python3 -m unittest discover -s tests -v 2>&1 | tee output/test_results.txt
  local status=${PIPESTATUS[0]}
  if [[ $status -eq 0 ]]; then log "test suite passed"; else log "test suite FAILED" "ERROR  "; fi
  echo "Saved to output/test_results.txt"
  return "$status"
}

run_demo() {
  need_python
  mkdir -p output/traces
  for f in samples/*.txt; do
    name="demo_$(basename "$f" .txt)"
    python3 main.py < "$f" > "output/traces/$name.txt" 2>&1
    echo "  $f  ->  output/traces/$name.txt"
    log "demo $(basename "$f") replayed"
  done
}

case "${1:-menu}" in
  menu)    need_python; log "menu started"; python3 main.py ;;
  analyze) need_python; log "full analysis started"; python3 main.py --analyze ;;
  test)    run_tests ;;
  sysinfo) bash scripts/sysinfo.sh ;;
  live)    bash scripts/ps_to_dataset.sh "${2:-5}" ;;
  demo)    echo "Replaying sample inputs through the menu..."; run_demo ;;
  setup)   setup ;;
  all)
    setup && echo && bash scripts/sysinfo.sh && echo && run_tests && echo && python3 main.py --analyze \
      && echo && echo "Replaying sample inputs through the menu..." && run_demo
    ;;
  clean)
    rm -rf output/* logs/*.log data/live_processes.json
    echo "Removed generated output and logs."
    ;;
  help|-h|--help) sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//' ;;
  *)
    echo "Unknown command '$1'."
    sed -n '2,13p' "$0" | sed 's/^# \{0,1\}//'
    log "unknown command '$1'" "WARNING"
    exit 1
    ;;
esac
