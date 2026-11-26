#!/usr/bin/env bash
# Turns the busiest live processes on this machine into a CPU-scheduling workload.
#
#   arrival  = position in the list (0, 1, 2, ...)
#   burst    = CPU time the process has used so far, in seconds (kept between 1 and 20)
#   priority = nice value mapped to 0..9 (nice -20 -> 0 = highest, nice 19 -> 9 = lowest)
#
# Usage: bash scripts/ps_to_dataset.sh [count]     (count 2-10, default 5)
# Writes data/live_processes.json, which the scheduling menu then loads.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/data/live_processes.json"
LOG="$ROOT/logs/activity.log"
mkdir -p "$ROOT/logs"
log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | ${2:-INFO   } | bash            | $1" >> "$LOG"; }

COUNT="${1:-5}"
if ! [[ "$COUNT" =~ ^[0-9]+$ ]] || (( COUNT < 2 || COUNT > 10 )); then
  echo "Error: count must be a whole number from 2 to 10 (got '$COUNT')" >&2
  log "ps_to_dataset.sh rejected count '$COUNT'" "WARNING"
  exit 1
fi

# pid, command, cumulative CPU seconds, nice; skip the tools this script itself runs
ps -eo pid=,comm=,times=,ni= --sort=-times \
  | awk -v self="$$" '$1 != self && $2 != "ps" && $2 != "awk" && $2 != "head"' \
  | head -n "$COUNT" \
  | awk -v when="$(date '+%Y-%m-%d %H:%M:%S')" '
    BEGIN {
      print "{"
      print "  \"source\": \"ps snapshot " when "\","
      print "  \"processes\": ["
      printf "%-8s %-16s %-8s %-5s ->  %-3s %-3s %-3s\n", "PID", "COMMAND", "CPU(s)", "NICE", "AT", "BT", "PR" > "/dev/stderr"
    }
    {
      burst = $3 + 0; if (burst < 1) burst = 1; if (burst > 20) burst = 20
      nice = ($4 == "-") ? 0 : $4 + 0
      pr = int((nice + 20) / 4); if (pr < 0) pr = 0; if (pr > 9) pr = 9
      gsub(/"/, "", $2)
      if (NR > 1) print ","
      printf "    {\"pid\": \"P%s\", \"name\": \"%s\", \"arrival\": %d, \"burst\": %d, \"priority\": %d}", $1, $2, NR - 1, burst, pr
      printf "%-8s %-16s %-8s %-5s ->  %-3d %-3d %-3d\n", $1, $2, $3, $4, NR - 1, burst, pr > "/dev/stderr"
    }
    END { print ""; print "  ]"; print "}" }
  ' > "$OUT" 2> "$ROOT/data/.live_table.txt"

if [[ ! -s "$OUT" ]]; then
  echo "Error: could not read processes with ps" >&2
  log "ps_to_dataset.sh could not read processes" "ERROR  "
  exit 1
fi

echo "Live processes imported from this computer:"
cat "$ROOT/data/.live_table.txt"
rm -f "$ROOT/data/.live_table.txt"
echo "Saved to data/live_processes.json"
log "ps_to_dataset.sh imported $COUNT live processes"
