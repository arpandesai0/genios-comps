#!/bin/sh
# Validate the data folder, then start the services with docker compose.
# Usage: scripts/start.sh /path/to/data [service ...]   (normally via: make start DIR=/path/to/data [SERVICES="api"])
# With no services named, every service starts (api and web). Naming services starts only those, e.g.
# SERVICES=api for local testing and evals without the front end.
set -eu
unset CDPATH  # so `cd` never prints a directory and corrupts $dir

usage="usage: make start DIR=/path/to/data [SERVICES=\"api web\"] (DIR: a folder with companies.json and fx_rates.json)"
fail() { echo "$1" >&2; exit 1; }
[ -n "${1:-}" ] || fail "$usage"

# Expand a leading ~ (zsh does not expand it in DIR=~/... arguments).
case "$1" in
  "~") raw="$HOME" ;;
  "~"/*) raw="$HOME/${1#"~"/}" ;;
  *) raw="$1" ;;
esac

dir=$(cd "$raw" 2>/dev/null && pwd) || fail "DIR '$1' is not a folder. $usage"
case "$dir" in
  *:*) fail "DIR '$dir' contains ':', which docker compose cannot mount. Move or link the folder elsewhere." ;;
esac
for f in companies.json fx_rates.json; do
  [ -f "$dir/$f" ] || fail "Missing $dir/$f. $usage"
done

shift
known=$(DIR="$dir" docker compose config --services)
for svc in "$@"; do
  echo "$known" | grep -qx "$svc" || fail "Unknown service '$svc'. Services: $(echo $known)."
done

echo "Data folder: $dir"
echo "Services: ${*:-all ($(echo $known))}"
export DIR="$dir"
services="$*"  # compose service names never contain spaces
follower=""

# Ctrl+C (at any point, including the build) stops the services, as an attached `docker compose up` would.
# The exit code is stop's, so a failed stop is not hidden.
stop_services() {
  trap - INT TERM
  echo
  rc=0
  docker compose stop $services || rc=$?
  [ -z "$follower" ] || kill "$follower" 2>/dev/null || true
  exit "$rc"
}
trap stop_services INT TERM

# Start in the background and wait until every service is running (the API healthy, i.e. data ingested and
# the model loaded), so the URLs below are printed only once they answer.
if ! docker compose up --build --detach --wait $services; then
  docker compose logs --tail 50 $services >&2
  fail "Start-up failed: see the logs above. Stop what started with: make stop"
fi

# Start-up logs first (ingestion, model load), then the banner, then only new log lines.
docker compose logs $services
line="****************************************************************"
echo
echo "$line"
echo "  Comps service is up"
echo "  Data:  $dir"
if [ -z "$services" ] || echo " $services " | grep -q " web "; then echo "  UI:    http://localhost:3000"; fi
echo "  API:   http://localhost:8000/api/health"
echo "  Docs:  http://localhost:8000/docs"
echo "  Ctrl+C stops the services (or run: make stop)"
echo "$line"
echo

docker compose logs --follow --since 0s $services &
follower=$!
rc=0
wait "$follower" || rc=$?
# Reached only if the logs ended without Ctrl+C: a service exited, or `make stop` ran elsewhere.
echo "The services are no longer running (exit $rc). Check 'docker compose ps -a', then run make start again." >&2
exit 1
