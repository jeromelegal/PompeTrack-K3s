#!/usr/bin/env bash
set -euo pipefail

# === Config ===
MEDPLUM_NS="medplum"
PROJECT_NAME="pompetrack"
CLIENT_NAME="worker-fhir"
OUT_FILE="deploy/secrets/pompetrack-core/worker-fhir-medplum-client.env"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need kubectl
need curl
need jq

echo "==> Wait Medplum pods Ready (namespace: $MEDPLUM_NS)"
# On attend *ce qui est prêt* plutôt que de supposer un nom de Deployment.
kubectl -n "$MEDPLUM_NS" wait --for=condition=Ready pod -l app.kubernetes.io/instance=medplum --timeout=300s 2>/dev/null \
  || kubectl -n "$MEDPLUM_NS" wait --for=condition=Ready pod --all --timeout=300s

echo "==> Port-forward Medplum service locally"
LOCAL_PORT="18080"
SVC_NAME="medplum-service"

kubectl -n "$MEDPLUM_NS" port-forward "svc/${SVC_NAME}" "${LOCAL_PORT}:80" >/tmp/medplum-portforward.log 2>&1 &
PF_PID=$!
cleanup() { kill "$PF_PID" >/dev/null 2>&1 || true; }
trap cleanup EXIT

# Wait for port-forward to be usable
for i in $(seq 1 50); do
  if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/healthcheck" >/dev/null 2>&1; then
    MEDPLUM_BASE="http://127.0.0.1:${LOCAL_PORT}"
    break
  fi
  sleep 0.2
done

if [[ -z "${MEDPLUM_BASE:-}" ]]; then
  echo "ERROR: port-forward OK but /healthcheck not reachable" >&2
  echo "Port-forward logs:" >&2
  tail -n 80 /tmp/medplum-portforward.log >&2 || true
  exit 1
fi

echo "==> Using MEDPLUM_BASE=${MEDPLUM_BASE}"
FHIR_BASE="${MEDPLUM_BASE}/fhir/R4"

echo "==> Read superadmin credentials from Kubernetes secrets"
SUPERADMIN_EMAIL="$(kubectl -n "$MEDPLUM_NS" get deploy -l app.kubernetes.io/instance=medplum -o json \
  | jq -r '.. | objects | select(.name?=="MEDPLUM_DEFAULT_SUPER_ADMIN_EMAIL") | .value' | head -n 1)"

if [[ -z "${SUPERADMIN_EMAIL:-}" || "$SUPERADMIN_EMAIL" == "null" ]]; then
  # fallback: tu l’as en dur dans values, mais on évite de “supposer” en prod.
  echo "ERROR: could not read MEDPLUM_DEFAULT_SUPER_ADMIN_EMAIL from deployment env." >&2
  exit 1
fi

SUPERADMIN_PASSWORD="$(kubectl -n "$MEDPLUM_NS" get secret medplum-superadmin -o jsonpath='{.data.password}' | base64 -d)"

if [[ -z "${SUPERADMIN_PASSWORD:-}" ]]; then
  echo "ERROR: superadmin password is empty (secret medplum-superadmin / key password)" >&2
  exit 1
fi

echo "==> OAuth: /auth/login -> /oauth2/token (PKCE plain)"
CODE_VERIFIER="$(openssl rand -hex 16 2>/dev/null || cat /proc/sys/kernel/random/uuid | tr -d '-')"

LOGIN_JSON="$(curl -fsS "${MEDPLUM_BASE}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg email "$SUPERADMIN_EMAIL" \
    --arg password "$SUPERADMIN_PASSWORD" \
    --arg cc "$CODE_VERIFIER" \
    '{email:$email,password:$password,codeChallengeMethod:"plain",codeChallenge:$cc}')" )"

AUTH_CODE="$(echo "$LOGIN_JSON" | jq -r '.code')"
if [[ -z "${AUTH_CODE:-}" || "$AUTH_CODE" == "null" ]]; then
  echo "ERROR: /auth/login did not return .code. Response:" >&2
  echo "$LOGIN_JSON" >&2
  exit 1
fi

TOKEN_JSON="$(curl -fsS "${MEDPLUM_BASE}/oauth2/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=authorization_code' \
  --data-urlencode "code=${AUTH_CODE}" \
  --data-urlencode "code_verifier=${CODE_VERIFIER}")"

ACCESS_TOKEN="$(echo "$TOKEN_JSON" | jq -r '.access_token')"
if [[ -z "${ACCESS_TOKEN:-}" || "$ACCESS_TOKEN" == "null" ]]; then
  echo "ERROR: /oauth2/token did not return access_token. Response:" >&2
  echo "$TOKEN_JSON" >&2
  exit 1
fi

AUTHZ_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"

echo "==> Ensure Project exists: ${PROJECT_NAME}"
PROJECT_ID="$(curl -fsS "${FHIR_BASE}/Project?name=${PROJECT_NAME}&_count=1" \
  -H "$AUTHZ_HEADER" -H 'Accept: application/fhir+json' \
  | jq -r '.entry[0].resource.id // empty')"

if [[ -z "${PROJECT_ID:-}" ]]; then
  echo "==> Project not found, creating via Project/\$init"
  PROJECT_JSON="$(curl -fsS "${FHIR_BASE}/Project/\$init" \
    -X POST \
    -H "$AUTHZ_HEADER" \
    -H 'Content-Type: application/fhir+json' \
    -d "$(jq -n --arg name "$PROJECT_NAME" \
      '{resourceType:"Parameters",parameter:[{name:"name",valueString:$name}] }')" )"

  PROJECT_ID="$(echo "$PROJECT_JSON" | jq -r '.id')"
  if [[ -z "${PROJECT_ID:-}" || "$PROJECT_ID" == "null" ]]; then
    echo "ERROR: Project/\$init did not return .id. Response:" >&2
    echo "$PROJECT_JSON" >&2
    exit 1
  fi
fi

echo "==> Project ID: ${PROJECT_ID}"

echo "==> Ensure ClientApplication exists: ${CLIENT_NAME}"
CLIENT_ID_EXISTING="$(curl -fsS "${FHIR_BASE}/ClientApplication?name=${CLIENT_NAME}&_count=1" \
  -H "$AUTHZ_HEADER" -H 'Accept: application/fhir+json' \
  | jq -r '.entry[0].resource.id // empty')"

if [[ -n "${CLIENT_ID_EXISTING:-}" ]]; then
  echo "==> Client already exists (id=${CLIENT_ID_EXISTING})."
  echo "    IMPORTANT: the secret is not reliably readable afterwards; create a new client name or implement secret rotation."
  echo "    For now, exiting without overwriting ${OUT_FILE}."
  exit 0
fi

echo "==> Creating client via /admin/projects/:projectId/client"
CLIENT_JSON="$(curl -fsS "${MEDPLUM_BASE}/admin/projects/${PROJECT_ID}/client" \
  -X POST \
  -H "$AUTHZ_HEADER" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg name "$CLIENT_NAME" \
    --arg desc "PompeTrack worker-fhir (machine-to-machine)" \
    '{name:$name,description:$desc}')" )"

CLIENT_ID="$(echo "$CLIENT_JSON" | jq -r '.id')"
CLIENT_SECRET="$(echo "$CLIENT_JSON" | jq -r '.secret')"

if [[ -z "${CLIENT_ID:-}" || "$CLIENT_ID" == "null" || -z "${CLIENT_SECRET:-}" || "$CLIENT_SECRET" == "null" ]]; then
  echo "ERROR: client creation did not return id+secret. Response:" >&2
  echo "$CLIENT_JSON" >&2
  exit 1
fi

mkdir -p "$(dirname "$OUT_FILE")"

cat > "$OUT_FILE" <<EOF
# Generated by generate-worker-fhir-medplum-client.sh
# Project: ${PROJECT_NAME} (${PROJECT_ID})
MEDPLUM_BASE_URL=${MEDPLUM_BASE}
MEDPLUM_PROJECT_ID=${PROJECT_ID}
MEDPLUM_CLIENT_ID=${CLIENT_ID}
MEDPLUM_CLIENT_SECRET=${CLIENT_SECRET}
EOF

chmod 600 "$OUT_FILE"
echo "==> Wrote ${OUT_FILE}"
