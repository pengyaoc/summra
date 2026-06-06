#!/usr/bin/env bash
# Hardening check — GCP firewall side. Read-only.
#
# Runs LOCALLY (your laptop) — needs `gcloud` configured.
# Reads <GCP_PROJECT_ID> from $GCP_PROJECT_ID env var, or parses it out of
# .prod-metadata.local.md if the env var is not set.
#
# Section C: firewall rules opening 0.0.0.0/0 to anything other than 22/80/443.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

# shellcheck source=hardening_check_lib.sh
source "$SCRIPT_DIR/hardening_check_lib.sh"

# ----------------------------------------------------------------------------
# Resolve <GCP_PROJECT_ID>
# ----------------------------------------------------------------------------
PROJECT="${GCP_PROJECT_ID:-}"
if [ -z "$PROJECT" ]; then
    META="$REPO_ROOT/.prod-metadata.local.md"
    if [ -r "$META" ]; then
        # Parse the markdown table row: | `<GCP_PROJECT_ID>` | `actual-value` |
        PROJECT="$(awk -F'`' '/<GCP_PROJECT_ID>/ {print $4; exit}' "$META")"
    fi
fi

if [ -z "$PROJECT" ]; then
    fail "GCP_PROJECT_ID missing" "set env var or fill .prod-metadata.local.md"
    summary; exit 1
fi

# ----------------------------------------------------------------------------
# C. GCP firewall rules
# ----------------------------------------------------------------------------
section "C. GCP firewall rules (project: $PROJECT)"

if ! command -v gcloud >/dev/null 2>&1; then
    fail "gcloud CLI missing" "install Google Cloud SDK to run this check"
    summary; exit 1
fi

RULES_JSON="$(gcloud compute firewall-rules list \
    --project="$PROJECT" \
    --filter='direction=INGRESS AND disabled=false' \
    --format=json 2>/dev/null)"

if [ -z "$RULES_JSON" ] || [ "$RULES_JSON" = "[]" ]; then
    warn "no firewall rules returned" "check gcloud auth or project ID"
    summary; exit $?
fi

if ! command -v jq >/dev/null 2>&1; then
    fail "jq missing" "install jq to parse firewall rules"
    summary; exit 1
fi

# Walk each rule. For each rule:
#   - has sourceRanges containing 0.0.0.0/0?
#   - what protocols/ports does it allow?
#   - classify: PASS (22/80/443/icmp), WARN (anything else), special-case ssh.
echo "$RULES_JSON" | jq -c '.[]' | while read -r rule; do
    name="$(echo "$rule" | jq -r '.name')"
    sources="$(echo "$rule" | jq -r '.sourceRanges // [] | join(",")')"
    targets="$(echo "$rule" | jq -r '.targetTags // [] | join(",")')"

    # Build a flat "proto:port" list from the allowed array.
    allows="$(echo "$rule" | jq -r '
        .allowed // [] | .[] |
        if .ports then (.IPProtocol as $p | .ports[] | "\($p):\(.)")
        else .IPProtocol end' | tr '\n' ',' | sed 's/,$//')"

    # If the rule does NOT cover 0.0.0.0/0, it's internal-only — informational
    if ! echo "$sources" | grep -q '0\.0\.0\.0/0'; then
        info "$name" "internal-only (sources: $sources; allow: $allows)"
        continue
    fi

    # Public ingress — classify each allow entry
    classified_ok=1
    for entry in ${allows//,/ }; do
        case "$entry" in
            tcp:80|tcp:443|icmp)
                : # expected, fine
                ;;
            tcp:22)
                # User chose lenient policy: WARN, don't FAIL
                warn "$name" "tcp:22 open to 0.0.0.0/0 — consider narrowing to your IP"
                classified_ok=0
                ;;
            tcp:80-443|tcp:80,443)
                : # range covering 80+443, fine
                ;;
            *)
                warn "$name" "unexpected public ingress: $entry (sources: $sources)"
                classified_ok=0
                ;;
        esac
    done

    if [ "$classified_ok" = "1" ]; then
        pass "$name" "public ingress: $allows"
    fi
done

# ----------------------------------------------------------------------------
summary
