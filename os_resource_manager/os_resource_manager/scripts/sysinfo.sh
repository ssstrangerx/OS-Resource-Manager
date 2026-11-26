#!/usr/bin/env bash
# Collects a snapshot of the real machine (CPU, memory, disk, busiest processes)
# and saves it to output/system_snapshot.txt. The analysis report includes this file.

set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="$ROOT/output/system_snapshot.txt"
LOG="$ROOT/logs/activity.log"
mkdir -p "$ROOT/output" "$ROOT/logs"

log() { echo "$(date '+%Y-%m-%d %H:%M:%S') | INFO    | bash            | $*" >> "$LOG"; }

{
  echo "Snapshot taken : $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Host / kernel  : $(uname -n) / $(uname -sr)"
  echo "CPU cores      : $(nproc 2>/dev/null || grep -c ^processor /proc/cpuinfo)"
  echo "CPU model      : $(grep -m1 'model name' /proc/cpuinfo 2>/dev/null | cut -d: -f2 | sed 's/^ *//')"
  echo "Load average   : $(cut -d' ' -f1-3 /proc/loadavg 2>/dev/null)"
  echo "Uptime         : $(uptime -p 2>/dev/null || echo unknown)"
  echo
  echo "Memory (MB):"
  free -m 2>/dev/null || echo "  free command not available"
  echo
  echo "Disk usage of / :"
  df -h / 2>/dev/null | sed 's/^/  /'
  echo
  echo "Process states (R running, S sleeping, Z zombie ...):"
  ps -eo stat= | cut -c1 | sort | uniq -c | awk '{printf "  %s: %s\n", $2, $1}'
  echo
  echo "Top 5 processes by CPU:"
  ps -eo pid,ppid,stat,ni,pcpu,pmem,comm --sort=-pcpu | head -n 6 | sed 's/^/  /'
} > "$OUT"

cat "$OUT"
echo
echo "Saved to output/system_snapshot.txt"
log "sysinfo.sh saved system snapshot"
