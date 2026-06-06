# Shared helpers for hardening_check_*.sh — source this file.
# Provides pass / warn / fail / section / summary, plus TTY color detection.

# Counters (declared via export so they survive across sourced contexts)
HC_PASS=0
HC_WARN=0
HC_FAIL=0

# Colors only when stdout is a TTY
if [ -t 1 ]; then
    HC_GREEN=$'\033[0;32m'
    HC_YELLOW=$'\033[0;33m'
    HC_RED=$'\033[0;31m'
    HC_BOLD=$'\033[1m'
    HC_NC=$'\033[0m'
else
    HC_GREEN=""
    HC_YELLOW=""
    HC_RED=""
    HC_BOLD=""
    HC_NC=""
fi

# Print a section header. Usage: section "A. SSH posture"
section() {
    printf '\n%s=== %s ===%s\n' "$HC_BOLD" "$1" "$HC_NC"
}

# Usage: pass "Check name" "optional detail"
pass() {
    HC_PASS=$((HC_PASS + 1))
    printf '  %s[PASS]%s %-40s %s\n' "$HC_GREEN" "$HC_NC" "$1" "${2:-}"
}

warn() {
    HC_WARN=$((HC_WARN + 1))
    printf '  %s[WARN]%s %-40s %s\n' "$HC_YELLOW" "$HC_NC" "$1" "${2:-}"
}

fail() {
    HC_FAIL=$((HC_FAIL + 1))
    printf '  %s[FAIL]%s %-40s %s\n' "$HC_RED" "$HC_NC" "$1" "${2:-}"
}

# Informational only — does not affect pass/warn/fail counters or exit code.
info() {
    printf '  [INFO] %-40s %s\n' "$1" "${2:-}"
}

# Final summary line. Exits non-zero if any FAIL.
summary() {
    printf '\n%sSummary:%s %s%d pass%s, %s%d warn%s, %s%d fail%s\n' \
        "$HC_BOLD" "$HC_NC" \
        "$HC_GREEN" "$HC_PASS" "$HC_NC" \
        "$HC_YELLOW" "$HC_WARN" "$HC_NC" \
        "$HC_RED" "$HC_FAIL" "$HC_NC"
    if [ "$HC_FAIL" -gt 0 ]; then
        return 1
    fi
    return 0
}
