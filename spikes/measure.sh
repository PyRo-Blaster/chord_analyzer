#!/bin/bash
# Run one command and report its wall time and peak memory.
# Usage: spikes/measure.sh <name> <command> [arguments...]
# Writes runs/phase0/<name>.log (output of the command) and runs/phase0/<name>.measure.
set -euo pipefail

name="$1"
shift
mkdir -p runs/phase0
log="runs/phase0/${name}.log"
timing="runs/phase0/${name}.time"

if ! /usr/bin/time -l -o "$timing" "$@" > "$log" 2>&1; then
    echo "FAILED: $name. Last lines of $log:" >&2
    tail -20 "$log" >&2
    exit 1
fi

awk '
    / real / { printf "wall_seconds=%s\n", $1 }
    /maximum resident set size/ { printf "peak_memory_gb=%.2f\n", $1 / 1073741824 }
' "$timing" | tee "runs/phase0/${name}.measure"
