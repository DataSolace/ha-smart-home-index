#!/usr/bin/env bash
# Copy the integration into a Home Assistant docker container over SSH.
#
#   HA_SSH=my-ha-host ./scripts/deploy.sh            copy, then restart Home Assistant
#   HA_SSH=my-ha-host ./scripts/deploy.sh --js-only  copy only; a page reload picks up panel JavaScript changes
#   HA_SSH=my-ha-host ./scripts/deploy.sh --feed-url http://host:3000/api/catalog-lite
#                                                    point the deployed copy at a local build of the app
#
# Python changes need the restart. Run `hass --script check_config` first if you can.
# custom_components is often root-owned on the host, so this copies with `docker cp`, not `cp`.
set -euo pipefail

: "${HA_SSH:?set HA_SSH to the ssh host that runs Home Assistant in docker}"
CONTAINER="${HA_CONTAINER:-homeassistant}"
COMPOSE_DIR="${HA_COMPOSE_DIR:-}"   # directory holding the compose file; needed for the restart
HERE="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HERE/custom_components/smart_home_index"
TMP="/tmp/shi_deploy_$$"

JS_ONLY=0; FEED_URL=""
while [ $# -gt 0 ]; do
  case "$1" in
    --js-only) JS_ONLY=1 ;;
    --feed-url) FEED_URL="$2"; shift ;;
    *) echo "unknown option $1" >&2; exit 2 ;;
  esac
  shift
done

STAGE="$(mktemp -d)"
trap 'rm -rf "$STAGE"' EXIT
cp -r "$SRC" "$STAGE/smart_home_index"
find "$STAGE" -name __pycache__ -prune -exec rm -rf {} +
if [ -n "$FEED_URL" ]; then
  sed -i "s|^FEED_URL = .*|FEED_URL = \"$FEED_URL\"|" "$STAGE/smart_home_index/const.py"
  grep -q "^FEED_URL = \"$FEED_URL\"" "$STAGE/smart_home_index/const.py" || { echo "could not set FEED_URL" >&2; exit 1; }
  echo "feed url set to $FEED_URL (deployed copy only)"
fi
scp -qr "$STAGE/smart_home_index" "$HA_SSH:$TMP"
ssh "$HA_SSH" "docker exec $CONTAINER rm -rf /config/custom_components/smart_home_index \
  && docker cp $TMP $CONTAINER:/config/custom_components/smart_home_index && rm -rf $TMP"
echo "copied"

if [ "$JS_ONLY" = 1 ]; then exit 0; fi
if [ -z "$COMPOSE_DIR" ]; then echo "set HA_COMPOSE_DIR to restart, or restart Home Assistant yourself"; exit 0; fi
ssh "$HA_SSH" "docker exec $CONTAINER hass --script check_config -c /config 2>&1 | tail -3; cd $COMPOSE_DIR && docker compose restart $CONTAINER"
