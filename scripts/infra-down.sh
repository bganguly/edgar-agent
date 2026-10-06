#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.gcp"
BACKEND_SVC="edgar-backend"
FRONTEND_SVC="edgar-frontend"

TARGET=""

# ── Preflight / menu ──────────────────────────────────────────────────────────

_run_preflight() {
  local _local_running=0 _gcp_deployed=0
  lsof -ti:8000 >/dev/null 2>&1 && _local_running=1 || true
  [[ -f "$ENV_FILE" ]] && _gcp_deployed=1 || true

  printf '\n=== edgar-agent teardown ===\n\n'
  printf '  [1] Local  — kill uvicorn + npm dev'
  (( _local_running )) && printf ' [running]' || printf ' [not detected]'
  printf '\n'
  printf '  [2] Cloud  — delete Cloud Run services'
  (( _gcp_deployed )) && printf ' [deployed]' || printf ' [no .env.gcp found]'
  printf '\n'
  printf '\nChoice [1/2, default 2]: '
  read -r _MODE
  _MODE="${_MODE:-2}"
  case "$_MODE" in
    2) TARGET="cloud" ;;
    *) TARGET="local" ;;
  esac
}

# ── Local teardown ────────────────────────────────────────────────────────────

_teardown_local() {
  printf '\nStopping local processes...\n'
  local _pids
  _pids=$(lsof -ti:8000 2>/dev/null || true)
  if [[ -n "$_pids" ]]; then
    kill "$_pids" 2>/dev/null || true
    printf '  Killed PID(s) on :8000 (uvicorn)\n'
  else
    printf '  No process found on :8000\n'
  fi
  _pids=$(lsof -ti:5173 2>/dev/null || true)
  if [[ -n "$_pids" ]]; then
    kill "$_pids" 2>/dev/null || true
    printf '  Killed PID(s) on :5173 (frontend dev server)\n'
  else
    printf '  No process found on :5173\n'
  fi
  printf '\nLocal teardown complete.\n'
}

# ── GCP teardown ──────────────────────────────────────────────────────────────

_teardown_gcp() {
  [[ -f "$ENV_FILE" ]] || { printf '\nNo .env.gcp found — nothing to tear down.\n'; exit 0; }
  source "$ENV_FILE"
  [[ -n "${GCP_PROJECT:-}" ]] || { printf '\nGCP_PROJECT not set in .env.gcp\n' >&2; exit 1; }
  [[ -n "${GCP_REGION:-}" ]] || { GCP_REGION="us-central1"; }

  printf '\n  Project: %s\n  Region:  %s\n' "$GCP_PROJECT" "$GCP_REGION"

  printf '\nDeleting Cloud Run services...\n'
  if gcloud run services describe "$FRONTEND_SVC" \
       --region="$GCP_REGION" --project="$GCP_PROJECT" &>/dev/null; then
    gcloud run services delete "$FRONTEND_SVC" \
      --region="$GCP_REGION" --project="$GCP_PROJECT" --quiet
    printf '  Deleted: %s\n' "$FRONTEND_SVC"
  else
    printf '  Not found: %s (skipped)\n' "$FRONTEND_SVC"
  fi

  if gcloud run services describe "$BACKEND_SVC" \
       --region="$GCP_REGION" --project="$GCP_PROJECT" &>/dev/null; then
    gcloud run services delete "$BACKEND_SVC" \
      --region="$GCP_REGION" --project="$GCP_PROJECT" --quiet
    printf '  Deleted: %s\n' "$BACKEND_SVC"
  else
    printf '  Not found: %s (skipped)\n' "$BACKEND_SVC"
  fi

  rm -f "$ENV_FILE"
  printf '\nRemoved %s\n' "$ENV_FILE"
  printf 'GCP teardown complete.\n'
}

# ── Main ──────────────────────────────────────────────────────────────────────

_run_preflight
if [[ "$TARGET" == "local" ]]; then
  _teardown_local
else
  _teardown_gcp
fi
