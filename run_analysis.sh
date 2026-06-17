#!/bin/bash
exec "$(cd "$(dirname "$0")" && pwd)/scripts/run_analysis.sh" "$@"
