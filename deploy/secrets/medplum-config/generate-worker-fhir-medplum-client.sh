#!/usr/bin/env bash
set -euo pipefail

# === Config ===
MEDPLUM_NS="medplum"
PROJECT_NAME="pompetrack"

SVC_NAME="medplum-service"
LOCAL_PORT="18080"

# Output files
WORKER_FHIR_OUT_FILE="deploy/secrets/pompetrack-core/worker-fhir-medplum-client.env"
WORKER_STREAM_OUT_FILE="deploy/secrets/pompetrack-core/worker-stream-medplum-client.env"
WORKER_SQLITE_OUT_FILE="deploy/secrets/pompetrack-core/worker-sqlite-medplum-client.env"
STREAMLIT_OUT_FILE="deploy/secrets/pompetrack-core/streamlit-medplum-client.env"
INGESTION_OUT_FILE="deploy/secrets/pompetrack-core/ingestion-medplum-client.env"
AIRFLOW_OUT_FILE="deploy/secrets/airflow/airflow-medplum-client.env"
PROVIDER_OUT_FILE="deploy/secrets/medplum/provider-medplum-client.env"
IDS_OUT_FILE="deploy/outputs/pompetrack-core/medplum-ids.env"

# NEW: Global file containing all client_ids
CLIENT_IDS_OUT_FILE="deploy/secrets/pompetrack-core/medplum-client-ids.env"

# Practitioner
PRACTITIONER_IDENTIFIER_SYSTEM="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.PRACTITIONER_IDENTIFIER_SYSTEM}' | base64 -d)"
PRACTITIONER_IDENTIFIER_VALUE="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.PRACTITIONER_IDENTIFIER_VALUE}' | base64 -d)"
PRACTITIONER_LOGIN_EMAIL="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.PRACTITIONER_LOGIN_EMAIL}' | base64 -d)"
PRACTITIONER_GIVEN="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.PRACTITIONER_GIVEN}' | base64 -d)"
PRACTITIONER_FAMILY="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.PRACTITIONER_FAMILY}' | base64 -d)"
USER_PASSWORD="$(kubectl -n "$MEDPLUM_NS" get secret practitioner-infos -o jsonpath='{.data.USER_PASSWORD}' | base64 -d)"

# Patient
PATIENT_IDENTIFIER_SYSTEM="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_IDENTIFIER_SYSTEM}' | base64 -d)"
PATIENT_IDENTIFIER_VALUE="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_IDENTIFIER_VALUE}' | base64 -d)"
PATIENT_GIVEN="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_GIVEN}' | base64 -d)"
PATIENT_FAMILY="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_FAMILY}' | base64 -d)"
PATIENT_BIRTHDATE="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_BIRTHDATE}' | base64 -d)"
PATIENT_GENDER="$(kubectl -n "$MEDPLUM_NS" get secret patient-infos -o jsonpath='{.data.PATIENT_GENDER}' | base64 -d)"

# Device
DEVICE_IDENTIFIER_SYSTEM="https://pompetrack.phylcero.fr/identifiers/device"
DEVICE_IDENTIFIER_VALUE="iphone-garth"
DEVICE_DISPLAY="iPhone (Apple Health)"
DEVICE_MANUFACTURER="Apple"
DEVICE_MODEL="iPhone 12 mini"

need() { command -v "$1" >/dev/null 2>&1 || { echo "Missing dependency: $1" >&2; exit 1; }; }
need kubectl
need curl
need jq
need openssl
need python3

# store all client IDs and secrets (by client name)
declare -A CLIENT_IDS
declare -A CLIENT_SECRETS

# normalize names into env keys
to_env_key() {
  echo "$1" | tr '[:lower:]-' '[:upper:]_'
}

urlencode() {
  python3 - <<'PY'
import sys, urllib.parse
print(urllib.parse.quote(sys.argv[1], safe=""))
PY
}

echo "==> Wait Medplum pods Ready (namespace: $MEDPLUM_NS)"
kubectl -n "$MEDPLUM_NS" wait --for=condition=Ready pod -l app.kubernetes.io/instance=medplum --timeout=300s 2>/dev/null \
  || kubectl -n "$MEDPLUM_NS" wait --for=condition=Ready pod --all --timeout=300s

echo "==> Port-forward Medplum service locally"
PF_LOG="$(mktemp -t medplum-portforward.XXXX.log)"
kubectl -n "$MEDPLUM_NS" port-forward "svc/${SVC_NAME}" "${LOCAL_PORT}:80" >"$PF_LOG" 2>&1 &
PF_PID=$!

cleanup() {
  kill "$PF_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

MEDPLUM_BASE=""
for _ in $(seq 1 50); do
  if curl -fsS "http://127.0.0.1:${LOCAL_PORT}/healthcheck" >/dev/null 2>&1; then
    MEDPLUM_BASE="http://127.0.0.1:${LOCAL_PORT}"
    break
  fi
  sleep 0.2
done

if [[ -z "${MEDPLUM_BASE}" ]]; then
  echo "ERROR: port-forward OK but /healthcheck not reachable" >&2
  echo "Port-forward logs:" >&2
  tail -n 120 "$PF_LOG" >&2 || true
  exit 1
fi

echo "==> Using MEDPLUM_BASE=${MEDPLUM_BASE}"
FHIR_BASE="${MEDPLUM_BASE}/fhir/R4"

echo "==> Read superadmin credentials from Kubernetes"
SUPERADMIN_EMAIL="$(kubectl -n "$MEDPLUM_NS" get deploy -l app.kubernetes.io/instance=medplum -o json \
  | jq -r '.. | objects | select(.name?=="MEDPLUM_DEFAULT_SUPER_ADMIN_EMAIL") | .value' | head -n 1)"

if [[ -z "${SUPERADMIN_EMAIL:-}" || "${SUPERADMIN_EMAIL}" == "null" ]]; then
  echo "ERROR: could not read MEDPLUM_DEFAULT_SUPER_ADMIN_EMAIL from deployment env." >&2
  exit 1
fi

SUPERADMIN_PASSWORD="$(kubectl -n "$MEDPLUM_NS" get secret medplum-superadmin -o jsonpath='{.data.password}' | base64 -d)"
if [[ -z "${SUPERADMIN_PASSWORD:-}" ]]; then
  echo "ERROR: superadmin password is empty (secret medplum-superadmin / key password)" >&2
  exit 1
fi

echo "==> OAuth: /auth/login -> (/auth/profile if needed) -> /oauth2/token (PKCE plain)"
CODE_VERIFIER="$(openssl rand -hex 16 2>/dev/null || cat /proc/sys/kernel/random/uuid | tr -d '-')"

LOGIN_JSON="$(curl -fsS -X POST "${MEDPLUM_BASE}/auth/login" \
  -H 'Content-Type: application/json' \
  -d "$(jq -n \
    --arg email "$SUPERADMIN_EMAIL" \
    --arg password "$SUPERADMIN_PASSWORD" \
    --arg cc "$CODE_VERIFIER" \
    '{email:$email,password:$password,codeChallengeMethod:"plain",codeChallenge:$cc}')" )"

AUTH_CODE="$(echo "$LOGIN_JSON" | jq -r '.code // empty')"

if [[ -z "${AUTH_CODE:-}" ]]; then
  LOGIN_ID="$(echo "$LOGIN_JSON" | jq -r '.login // empty')"
  if [[ -z "${LOGIN_ID:-}" ]]; then
    echo "ERROR: /auth/login did not return .code nor .login. Response:" >&2
    echo "$LOGIN_JSON" >&2
    exit 1
  fi

  MEMBERSHIP_ID="$(echo "$LOGIN_JSON" | jq -r --arg pn "$PROJECT_NAME" '
      ( .memberships // [] ) as $m
      | ( $m[]? | select(.project.display==$pn) | .id ) // empty
    ' | head -n1)"

  if [[ -z "${MEMBERSHIP_ID:-}" ]]; then
    MEMBERSHIP_ID="$(echo "$LOGIN_JSON" | jq -r '
      ( .memberships // [] ) as $m
      | if ($m|length)==1 then $m[0].id else empty end
    ' | head -n1)"
  fi

  if [[ -z "${MEMBERSHIP_ID:-}" ]]; then
    echo "ERROR: multiple memberships returned and none matched PROJECT_NAME='${PROJECT_NAME}'." >&2
    echo "Memberships were:" >&2
    echo "$LOGIN_JSON" | jq -c '.memberships[]? | {id, project:.project.display, profile:.profile.display}' >&2 || true
    exit 1
  fi

  PROFILE_JSON="$(curl -fsS -X POST "${MEDPLUM_BASE}/auth/profile" \
    -H 'Content-Type: application/json' \
    -d "$(jq -n --arg login "$LOGIN_ID" --arg profile "$MEMBERSHIP_ID" \
      '{login:$login,profile:$profile}')" )"

  AUTH_CODE="$(echo "$PROFILE_JSON" | jq -r '.code // empty')"
  if [[ -z "${AUTH_CODE:-}" ]]; then
    echo "ERROR: /auth/profile did not return .code. Response:" >&2
    echo "$PROFILE_JSON" >&2
    exit 1
  fi
fi

TOKEN_JSON="$(curl -fsS -X POST "${MEDPLUM_BASE}/oauth2/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=authorization_code' \
  --data-urlencode "code=${AUTH_CODE}" \
  --data-urlencode "code_verifier=${CODE_VERIFIER}")"

ACCESS_TOKEN="$(echo "$TOKEN_JSON" | jq -r '.access_token // empty')"
if [[ -z "${ACCESS_TOKEN:-}" ]]; then
  echo "ERROR: /oauth2/token did not return access_token. Response:" >&2
  echo "$TOKEN_JSON" >&2
  exit 1
fi

AUTHZ_HEADER="Authorization: Bearer ${ACCESS_TOKEN}"
# Save token
SUPERADMIN_AUTHZ_HEADER="$AUTHZ_HEADER"

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

  PROJECT_ID="$(echo "$PROJECT_JSON" | jq -r '.id // empty')"
  if [[ -z "${PROJECT_ID:-}" ]]; then
    echo "ERROR: Project/\$init did not return .id. Response:" >&2
    echo "$PROJECT_JSON" >&2
    exit 1
  fi
fi

# Creates clients
echo "==> Project ID: ${PROJECT_ID}"
ensure_client() {
  local client_name="$1"
  local out_file="$2"
  local description="$3"
  local scopes="$4"
  local redirect_uri="${5:-}"
  local origin="${6:-}"

  echo "==> Ensure ClientApplication exists: $client_name"

  local client_id client_secret
  client_id=$(curl -s "${FHIR_BASE}/ClientApplication?name=${client_name}" \
    -H "$AUTHZ_HEADER" \
    | jq -r '.entry[0].resource.id // empty')

  if [[ -z "$client_id" ]]; then
    echo "==> Creating client $client_name"
    client_json=$(curl -s "${MEDPLUM_BASE}/admin/projects/${PROJECT_ID}/client" \
      -X POST \
      -H "$SUPERADMIN_AUTHZ_HEADER" \
      -H "Content-Type: application/json" \
      -d "{\"name\":\"$client_name\",\"description\":\"$description\"}")

    client_id=$(echo "$client_json" | jq -r '.id')
    client_secret=$(echo "$client_json" | jq -r '.secret')
  else
    echo "==> Client exists ($client_name), reading secret"
    client_secret=$(curl -s "${FHIR_BASE}/ClientApplication/${client_id}" \
      -H "$AUTHZ_HEADER" | jq -r '.secret // empty')
  fi

  # Save for practitioner/user create
  CLIENT_IDS["$client_name"]="$client_id"
  CLIENT_SECRETS["$client_name"]="$client_secret"

  mkdir -p "$(dirname "$out_file")"
  cat > "$out_file" <<EOF
MEDPLUM_BASE_URL=${MEDPLUM_BASE}
MEDPLUM_PROJECT_ID=${PROJECT_ID}
MEDPLUM_CLIENT_ID=${client_id}
MEDPLUM_CLIENT_SECRET=${client_secret}
EOF
  chmod 600 "$out_file"

  scopes_json=$(echo "$scopes" | tr ',' ' ' | xargs -n1 | jq -R . | jq -s .)

  curl -s -X PATCH "${FHIR_BASE}/ClientApplication/${client_id}" \
    -H "$AUTHZ_HEADER" \
    -H "Content-Type: application/json-patch+json" \
    -d "[{\"op\":\"add\",\"path\":\"/defaultScope\",\"value\":${scopes_json}}]" \
    || true

  if [[ -n "$redirect_uri" ]]; then
    curl -s -X PATCH "${FHIR_BASE}/ClientApplication/${client_id}" \
      -H "$AUTHZ_HEADER" \
      -H "Content-Type: application/json-patch+json" \
      -d "[{\"op\":\"add\",\"path\":\"/redirectUris\",\"value\":[\"$redirect_uri\"]}]" \
      || true
  fi

  if [[ -n "$origin" ]]; then
    curl -s -X PATCH "${FHIR_BASE}/ClientApplication/${client_id}" \
      -H "$AUTHZ_HEADER" \
      -H "Content-Type: application/json-patch+json" \
      -d "[{\"op\":\"add\",\"path\":\"/allowedOrigin\",\"value\":[\"$origin\"]}]" \
      || true
  fi

  echo "==> Client configured: $client_name (id: $client_id)"
}

# === Clients ===
ensure_client "worker-fhir"    "$WORKER_FHIR_OUT_FILE"    "PompeTrack worker-fhir (machine-to-machine)"    "ingest:fhir object:list download:json object:move fhir:logs ingest:generic"
ensure_client "worker-stream"  "$WORKER_STREAM_OUT_FILE"  "PompeTrack worker-stream (machine-to-machine)"  "stream:fhir stream:generic"
ensure_client "streamlit"      "$STREAMLIT_OUT_FILE"      "PompeTrack streamlit (machine-to-machine)"      "ingest:manual ingest:generic download:df stream:fhir ingest:iphone ingest:spirometer ingest:sqlite"
ensure_client "worker-sqlite"  "$WORKER_SQLITE_OUT_FILE"  "PompeTrack worker-sqlite (machine-to-machine)"  "object:list object:move object:delete download:object ingest:spirometer"
ensure_client "ingestion"      "$INGESTION_OUT_FILE"     "PompeTrack ingestion (machine-to-machine)"      "svc:ingestion ingest:generic"
ensure_client "airflow"        "$AIRFLOW_OUT_FILE"        "PompeTrack airflow (machine-to-machine)"        "object:list airflow:iphone airflow:manual airflow:spirometer airflow:strength fhir:logs"
ensure_client "provider"       "$PROVIDER_OUT_FILE"       "Provider frontend login"                        "openid profile email medplum:base"  "https://provider.phylcero.fr/auth/callback"  "https://provider.phylcero.fr"

# === Write global Client IDs file ===
echo "==> Write global Client IDs file: ${CLIENT_IDS_OUT_FILE}"
mkdir -p "$(dirname "$CLIENT_IDS_OUT_FILE")"
{
  echo "# Generated by generate-worker-fhir-medplum-client.sh (Client IDs + TOKEN_AUDIENCE)"
  echo "MEDPLUM_BASE_URL=${MEDPLUM_BASE}"
  echo "MEDPLUM_PROJECT_ID=${PROJECT_ID}"

  for name in "${!CLIENT_IDS[@]}"; do
    key="$(to_env_key "$name")"
    client_id="${CLIENT_IDS[$name]}"
    echo "TOKEN_AUDIENCE_${key}=${client_id}"
  done | LC_ALL=C sort
} > "$CLIENT_IDS_OUT_FILE"
chmod 600 "$CLIENT_IDS_OUT_FILE"
echo "==> Wrote ${CLIENT_IDS_OUT_FILE}"


# Client token
echo "==> Obtain project-scoped token via worker-fhir client_credentials"
PROJECT_CLIENT_ID="${CLIENT_IDS[worker-fhir]}"
PROJECT_CLIENT_SECRET="${CLIENT_SECRETS[worker-fhir]}"

if [[ -z "${PROJECT_CLIENT_ID:-}" || -z "${PROJECT_CLIENT_SECRET:-}" ]]; then
  echo "ERROR: worker-fhir client_id or secret is empty" >&2
  exit 1
fi

PROJECT_TOKEN_JSON="$(curl -fsS -X POST "${MEDPLUM_BASE}/oauth2/token" \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  --data-urlencode 'grant_type=client_credentials' \
  --data-urlencode "client_id=${PROJECT_CLIENT_ID}" \
  --data-urlencode "client_secret=${PROJECT_CLIENT_SECRET}")"

PROJECT_ACCESS_TOKEN="$(echo "$PROJECT_TOKEN_JSON" | jq -r '.access_token // empty')"
if [[ -z "${PROJECT_ACCESS_TOKEN:-}" ]]; then
  echo "ERROR: client_credentials token exchange failed. Response:" >&2
  echo "$PROJECT_TOKEN_JSON" >&2
  exit 1
fi

AUTHZ_HEADER="Authorization: Bearer ${PROJECT_ACCESS_TOKEN}"
echo "==> Now using project-scoped token (client: worker-fhir)"
# ============================================================

export PROJECT_ID
echo "==> Project ID: ${PROJECT_ID}"

## Practitioner
echo "==> Ensure Practitioner exists (identifier=${PRACTITIONER_IDENTIFIER_VALUE})"
PRACTITIONER_Q="$(python3 - <<PY
import urllib.parse
print(urllib.parse.quote("${PRACTITIONER_IDENTIFIER_SYSTEM}|${PRACTITIONER_IDENTIFIER_VALUE}", safe=""))
PY
)"

if ! PRACTITIONER_ID="$(curl -fsS "${FHIR_BASE}/Practitioner?identifier=${PRACTITIONER_Q}&_count=1" \
  -H "$AUTHZ_HEADER" -H 'Accept: application/fhir+json' \
  | jq -r '.entry[0].resource.id // empty' 2>/dev/null)"; then
  echo "ERROR: Failed to query Practitioner" >&2
  exit 1
fi

if [[ -z "${PRACTITIONER_ID:-}" ]]; then
  echo "==> Practitioner not found, creating"
  if ! PRACTITIONER_JSON="$(curl -fsS "${FHIR_BASE}/Practitioner" \
    -X POST \
    -H "$AUTHZ_HEADER" \
    -H 'Content-Type: application/fhir+json' \
    -d "$(jq -n \
      --arg sys "$PRACTITIONER_IDENTIFIER_SYSTEM" \
      --arg val "$PRACTITIONER_IDENTIFIER_VALUE" \
      --arg email "$PRACTITIONER_LOGIN_EMAIL" \
      --arg given "$PRACTITIONER_GIVEN" \
      --arg family "$PRACTITIONER_FAMILY" \
      '{
        resourceType: "Practitioner",
        identifier: [{ system: $sys, value: $val }],
        name: [{ given: [$given], family: $family }],
        telecom: [{ system: "email", value: $email }]
      }' )" 2>/dev/null)"; then
    echo "ERROR: Failed to create Practitioner" >&2
    exit 1
  fi

  PRACTITIONER_ID="$(echo "$PRACTITIONER_JSON" | jq -r '.id // empty')"
  echo "DEBUG Practitioner meta: $(echo "$PRACTITIONER_JSON" | jq '{id, meta}')"
  if [[ -z "${PRACTITIONER_ID:-}" ]]; then
    echo "ERROR: Practitioner creation failed (no ID returned)" >&2
    echo "Response: $PRACTITIONER_JSON" >&2
    exit 1
  fi
  echo "==> Practitioner created with ID: ${PRACTITIONER_ID}"
else
  echo "==> Practitioner found with ID: ${PRACTITIONER_ID}"
fi

# Add user attached to practitioner
echo "==> Ensure User exists for Practitioner (email=${PRACTITIONER_LOGIN_EMAIL})"

# Use SUPERADMIN_AUTHZ_HEADER for ProjectMembership and invite
MEMBERSHIP_ID="$(curl -fsS \
  "${FHIR_BASE}/ProjectMembership" \
  -H "$SUPERADMIN_AUTHZ_HEADER" \
  | jq -r --arg pid "Practitioner/${PRACTITIONER_ID}" \
    '.entry[]?.resource | select(.profile.reference == $pid) | .id // empty' \
  | head -1)"

if [[ -n "${MEMBERSHIP_ID:-}" ]]; then
  echo "==> Membership already exists (ID: ${MEMBERSHIP_ID}), skipping invite"
else
  echo "==> No membership found, inviting user"
  INVITE_JSON="$(curl -sS \
    "${MEDPLUM_BASE}/admin/projects/${PROJECT_ID}/invite" \
    -X POST \
    -H "$SUPERADMIN_AUTHZ_HEADER" \
    -H "Content-Type: application/json" \
    -d "$(jq -n \
      --arg email     "$PRACTITIONER_LOGIN_EMAIL" \
      --arg given     "$PRACTITIONER_GIVEN" \
      --arg family    "$PRACTITIONER_FAMILY" \
      --arg password  "$USER_PASSWORD" \
      --arg pid       "$PRACTITIONER_ID" \
      --arg projectId "$PROJECT_ID" \
      '{
        resourceType:   "Practitioner",
        firstName:      $given,
        lastName:       $family,
        email:          $email,
        password:       $password,
        sendEmail:      false,
        membership: {
          project: {
            reference: ("Project/" + $projectId)
          },
          profile: {
            reference: ("Practitioner/" + $pid)
          }
        }
      }')")"

  #echo "DEBUG invite response: $INVITE_JSON"

  MEMBERSHIP_ID="$(echo "$INVITE_JSON" | jq -r '.id // empty')"
  if [[ -z "${MEMBERSHIP_ID:-}" ]]; then
    echo "WARN: invite returned no ID. Response:"
    echo "$INVITE_JSON"
  else
    echo "==> User invited, membership ID: ${MEMBERSHIP_ID}"
  fi
fi

## Patient
echo "==> Ensure Patient exists (identifier=${PATIENT_IDENTIFIER_VALUE})"
PATIENT_Q="$(python3 - <<PY
import urllib.parse
print(urllib.parse.quote("${PATIENT_IDENTIFIER_SYSTEM}|${PATIENT_IDENTIFIER_VALUE}", safe=""))
PY
)"
PATIENT_ID="$(curl -fsS "${FHIR_BASE}/Patient?identifier=${PATIENT_Q}&_count=1" \
  -H "$AUTHZ_HEADER" -H 'Accept: application/fhir+json' \
  | jq -r '.entry[0].resource.id // empty')"

if [[ -z "${PATIENT_ID:-}" ]]; then
  echo "==> Patient not found, creating"
  PATIENT_JSON="$(curl -fsS "${FHIR_BASE}/Patient" \
    -X POST \
    -H "$AUTHZ_HEADER" \
    -H 'Content-Type: application/fhir+json' \
    -d "$(jq -n \
      --arg sys "$PATIENT_IDENTIFIER_SYSTEM" \
      --arg val "$PATIENT_IDENTIFIER_VALUE" \
      --arg given "$PATIENT_GIVEN" \
      --arg family "$PATIENT_FAMILY" \
      --arg birth "$PATIENT_BIRTHDATE" \
      --arg gender "$PATIENT_GENDER" \
      '{
        resourceType:"Patient",
        identifier:[{system:$sys,value:$val}],
        name:[{given:[$given],family:$family}],
        birthDate: ($birth|select(length>0)),
        gender: ($gender|select(length>0))
      }' )")"
  PATIENT_ID="$(echo "$PATIENT_JSON" | jq -r '.id // empty')"
fi

if [[ -z "${PATIENT_ID:-}" ]]; then
  echo "ERROR: could not determine Patient ID" >&2
  exit 1
fi
echo "==> Patient ID: ${PATIENT_ID}"

## Device
echo "==> Ensure Device exists (identifier=${DEVICE_IDENTIFIER_VALUE})"
DEVICE_Q="$(python3 - <<PY
import urllib.parse
print(urllib.parse.quote("${DEVICE_IDENTIFIER_SYSTEM}|${DEVICE_IDENTIFIER_VALUE}", safe=""))
PY
)"
DEVICE_ID="$(curl -fsS "${FHIR_BASE}/Device?identifier=${DEVICE_Q}&_count=1" \
  -H "$AUTHZ_HEADER" -H 'Accept: application/fhir+json' \
  | jq -r '.entry[0].resource.id // empty')"

if [[ -z "${DEVICE_ID:-}" ]]; then
  echo "==> Device not found, creating"
  DEVICE_JSON="$(curl -fsS "${FHIR_BASE}/Device" \
    -X POST \
    -H "$AUTHZ_HEADER" \
    -H 'Content-Type: application/fhir+json' \
    -d "$(jq -n \
      --arg sys "$DEVICE_IDENTIFIER_SYSTEM" \
      --arg val "$DEVICE_IDENTIFIER_VALUE" \
      --arg disp "$DEVICE_DISPLAY" \
      --arg man "$DEVICE_MANUFACTURER" \
      --arg model "$DEVICE_MODEL" \
      '{
        resourceType:"Device",
        identifier:[{system:$sys,value:$val}],
        manufacturer: ($man|select(length>0)),
        modelNumber: ($model|select(length>0)),
        deviceName: [{name:$disp, type:"user-friendly-name"}]
      }' )")"
  DEVICE_ID="$(echo "$DEVICE_JSON" | jq -r '.id // empty')"
fi

if [[ -z "${DEVICE_ID:-}" ]]; then
  echo "ERROR: could not determine Device ID" >&2
  exit 1
fi
echo "==> Device ID: ${DEVICE_ID}"

mkdir -p "$(dirname "$IDS_OUT_FILE")"
cat > "$IDS_OUT_FILE" <<EOF
# Generated by generate-worker-fhir-medplum-client.sh (IDs only)
MEDPLUM_PROJECT_ID=${PROJECT_ID}
MEDPLUM_PATIENT_ID=${PATIENT_ID}
MEDPLUM_DEVICE_ID=${DEVICE_ID}
EOF
chmod 644 "$IDS_OUT_FILE"
echo "==> Wrote ${IDS_OUT_FILE}"
