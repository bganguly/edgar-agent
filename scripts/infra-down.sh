#!/usr/bin/env bash
# infra-down.sh — stop local processes or tear down GCP Cloud Run resources
# Usage: ./scripts/infra-down.sh
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="$ROOT/.env.gcp"
BACKEND_SVC="edgar-backend"
FRONTEND_SVC="edgar-frontend"
AR_REPO="edgar-agent"
SA_NAME="edgar-runner"

bold()  { printf '\033[1m%s\033[0m\n' "$*"; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
red()   { printf '\033[31m%s\033[0m\n' "$*"; }
dim()   { printf '\033[2m%s\033[0m\n' "$*"; }

_local_running=0
lsof -ti:8000 >/dev/null 2>&1 && _local_running=1 || true
_gcp_deployed=0
[[ -f "$ENV_FILE" ]] && _gcp_deployed=1 || true

printf '\n=== edgar-agent — tear down ===\n\n'
printf '  [1] Local  — stop uvicorn + Vite dev processes'
(( _local_running )) && printf ' [running]' || printf ' [not detected]'
printf '\n'
printf '  [2] Cloud  — delete GCP Cloud Run resources'
(( _gcp_deployed )) && printf ' [deployed]' || printf ' [not deployed]'
printf '\n'
printf '\nChoice [1/2, default 2]: '
read -r _MODE
case "$_MODE" in
  1) _TARGET="local" ;;
  *) _TARGET="cloud" ;;
esac

# ── local ─────────────────────────────────────────────────────────────────────
if [[ "$_TARGET" == "local" ]]; then
  _stopped=0
  for _port in 8000 5173; do
    _pid="$(lsof -ti:${_port} 2>/dev/null || true)"
    if [[ -n "$_pid" ]]; then
      kill "$_pid" 2>/dev/null && green "  Stopped process on :${_port}" || true
      _stopped=1
    fi
  done
  (( _stopped )) || dim '  No processes found on :8000 or :5173.'
  green 'Done.'
  exit 0
fi

# ── GCP ───────────────────────────────────────────────────────────────────────
[[ -f "$ENV_FILE" ]] || { dim 'No .env.gcp found — nothing to tear down.'; exit 0; }
source "$ENV_FILE"

bold "GCP teardown — project: $GCP_PROJECT  region: $GCP_REGION"
printf '\n  This will delete:\n'
printf '    Cloud Run services: %s, %s\n' "$BACKEND_SVC" "$FRONTEND_SVC"
printf '    Artifact Registry:  images in %s\n' "$AR_REPO"
printf '    Secrets:            edgar-anthropic-key, edgar-openai-key\n'
printf '    Service account:    %s@%s.iam.gserviceaccount.com\n' "$SA_NAME" "$GCP_PROJECT"
printf '\n  Proceed? [Y/n]: '
read -r _CONFIRM
[[ "${_CONFIRM:-y}" =~ ^[Yy]$ ]] || { red 'Aborted.'; exit 1; }

echo ""
echo "[1/3] Deleting Cloud Run services..."
gcloud run services delete "$FRONTEND_SVC" \
  --region="$GCP_REGION" --project="$GCP_PROJECT" --quiet 2>/dev/null \
  && green "  $FRONTEND_SVC deleted" || dim "  $FRONTEND_SVC not found"
gcloud run services delete "$BACKEND_SVC" \
  --region="$GCP_REGION" --project="$GCP_PROJECT" --quiet 2>/dev/null \
  && green "  $BACKEND_SVC deleted" || dim "  $BACKEND_SVC not found"

echo ""
echo "[2/3] Deleting secrets and service account..."
for _secret in edgar-anthropic-key edgar-openai-key; do
  gcloud secrets delete "$_secret" --project="$GCP_PROJECT" --quiet 2>/dev/null \
    && green "  secret $_secret deleted" || dim "  secret $_secret not found"
done

SA_EMAIL="${SA_NAME}@${GCP_PROJECT}.iam.gserviceaccount.com"
gcloud iam service-accounts delete "$SA_EMAIL" --project="$GCP_PROJECT" --quiet 2>/dev/null \
  && green "  service account $SA_EMAIL deleted" || dim "  service account not found"

echo ""
echo "[3/3] Cleaning up Artifact Registry images and local state..."
if gcloud artifacts repositories describe "$AR_REPO" \
     --project="$GCP_PROJECT" --location="$GCP_REGION" &>/dev/null; then
  for _svc in "$BACKEND_SVC" "$FRONTEND_SVC"; do
    gcloud artifacts docker images delete \
      "${GCP_REGION}-docker.pkg.dev/${GCP_PROJECT}/${AR_REPO}/${_svc}" \
      --project="$GCP_PROJECT" --delete-tags --quiet 2>/dev/null \
      && green "  images deleted: ${_svc}" || dim "  no images found: ${_svc}"
  done
fi

rm -f "$ENV_FILE"
green "  .env.gcp removed"

green '\nGCP infrastructure torn down.'
printf '  Redeploy: ./scripts/deploy.sh\n'
