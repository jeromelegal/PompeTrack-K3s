#!/usr/bin/env bash
set -euo pipefail

# === Config ===
MEDPLUM_NS="medplum"
PROJECT_NAME="pompetrack"
CLIENT_NAME="worker-fhir"
OUT_FILE="deploy/secrets/pompetrack-core/worker-fhir-medplum-client.env"
IDS_OUT_FILE="deploy/outputs/pompetrack-core/medplum-ids.env"

# Patient
PATIENT_IDENTIFIER_SYSTEM="https://pompetrack.phylcero.fr/identifiers/patient"
PATIENT_IDENTIFIER_VALUE="garthcrow"
PATIENT_GIVEN="Jérôme"
PATIENT_FAMILY="LE GAL"
PATIENT_BIRTHDATE="1980-01-09"
PATIENT_GENDER="male"  

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

# Si pas de code, Medplum renvoie {login, memberships:[...]} => il faut choisir un profil via /auth/profile
if [[ -z "${AUTH_CODE:-}" ]]; then
  LOGIN_ID="$(echo "$LOGIN_JSON" | jq -r '.login // empty')"
  if [[ -z "${LOGIN_ID:-}" ]]; then
    echo "ERROR: /auth/login did not return .code nor .login. Response:" >&2
    echo "$LOGIN_JSON" >&2
    exit 1
  fi

  # Essaie de sélectionner la membership correspondant au projet voulu (display == PROJECT_NAME).
  # Fallback: si une seule membership, on la prend.
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

CLIENT_ID="$(echo "$CLIENT_JSON" | jq -r '.id // empty')"
CLIENT_SECRET="$(echo "$CLIENT_JSON" | jq -r '.secret // empty')"

if [[ -z "${CLIENT_ID:-}" || -z "${CLIENT_SECRET:-}" ]]; then
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


echo "==> Ensure Patient exists (identifier=${PATIENT_IDENTIFIER_VALUE})"
PATIENT_ID="$(curl -fsS \
  "${FHIR_BASE}/Patient?identifier=$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote("https://pompetrack.phylcero.fr/identifiers/patient|garthcrow"))
PY
)&_count=1" \
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

echo "==> Ensure Device exists (identifier=${DEVICE_IDENTIFIER_VALUE})"
DEVICE_ID="$(curl -fsS \
  "${FHIR_BASE}/Device?identifier=$(python3 - <<'PY'
import urllib.parse
print(urllib.parse.quote("https://pompetrack.phylcero.fr/identifiers/device|iphone-garth"))
PY
)&_count=1" \
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

# --- Write non-secret IDs output ---
cat > "$IDS_OUT_FILE" <<EOF
# Generated by generate-worker-fhir-medplum-client.sh (IDs only)
MEDPLUM_PROJECT_ID=${PROJECT_ID}
MEDPLUM_PATIENT_ID=${PATIENT_ID}
MEDPLUM_DEVICE_ID=${DEVICE_ID}
EOF

chmod 644 "$IDS_OUT_FILE"
echo "==> Wrote ${IDS_OUT_FILE}"