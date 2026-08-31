#!/usr/bin/env bash
#
# Deploy the pushed main branch to the production VPS.
#
#   deploy/deploy.sh [user@host]
#
# The target host is deliberately NOT hardcoded, so the server's address stays
# out of the repo. It is resolved from, in order:
#   1. the first argument
#   2. $MRC_DEPLOY_TARGET
# and the SSH key from $MRC_DEPLOY_KEY (default ~/.ssh/id_ed25519).
# Both live in .claude/settings.local.json, which is gitignored.
#
# Push first - this deploys whatever origin/main already has.
# Content changes are NOT handled here; see DEPLOY.md.

set -euo pipefail

TARGET="${1:-${MRC_DEPLOY_TARGET:-}}"
SSH_KEY="${MRC_DEPLOY_KEY:-$HOME/.ssh/id_ed25519}"

if [ -z "$TARGET" ]; then
    echo "deploy.sh: no target host." >&2
    echo "Pass one (deploy/deploy.sh root@HOST) or set MRC_DEPLOY_TARGET." >&2
    exit 2
fi

echo "==> Deploying to $TARGET"

ssh -i "$SSH_KEY" "$TARGET" bash -s <<'REMOTE'
set -euo pipefail

runuser -u mine -- bash -c '
    set -euo pipefail
    cd /srv/mine-rescue

    git pull --ff-only

    set -a; . ./.env; set +a
    ./venv/bin/pip install -q -r requirements.txt
    ./venv/bin/python manage.py migrate --noinput
    ./venv/bin/python manage.py collectstatic --noinput
    ./venv/bin/python manage.py check
'

systemctl restart mine-rescue
sleep 2
systemctl is-active mine-rescue
REMOTE

echo "==> gunicorn restarted"

# Optional post-deploy smoke check; set MRC_DEPLOY_URL to enable.
if [ -n "${MRC_DEPLOY_URL:-}" ]; then
    code=$(curl -s -o /dev/null -w '%{http_code}' "$MRC_DEPLOY_URL")
    echo "==> $MRC_DEPLOY_URL -> $code"
    [ "$code" = "200" ] || { echo "deploy.sh: site did not return 200" >&2; exit 1; }
fi

echo "==> Done"
