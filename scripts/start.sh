#!/bin/sh
# Validate the data folder, then start the API and web UI with docker compose.
# Usage: scripts/start.sh /path/to/data   (normally via: make start DIR=/path/to/data)
set -eu

usage="usage: make start DIR=/path/to/data (a folder with companies.json and fx_rates.json)"
[ -n "${1:-}" ] || { echo "$usage"; exit 1; }

# Expand a leading ~ (zsh does not expand it in DIR=~/... arguments).
case "$1" in
  "~"/*) raw="$HOME/${1#"~"/}" ;;
  *) raw="$1" ;;
esac

dir=$(cd "$raw" 2>/dev/null && pwd) || { echo "DIR '$1' is not a folder. $usage"; exit 1; }
for f in companies.json fx_rates.json; do
  [ -f "$dir/$f" ] || { echo "Missing $dir/$f. $usage"; exit 1; }
done

echo "Data folder: $dir"
echo "UI:  http://localhost:3000"
echo "API: http://localhost:8000/api/health"
DIR="$dir" exec docker compose up --build
