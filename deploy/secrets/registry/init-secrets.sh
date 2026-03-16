#!/usr/bin/env bash
set -euo pipefail

echo "==> create/update registry secrets from .env"
REGISTRY_ENV="deploy/secrets/registry/registry-token.env"

NAMESPACES=("pompetrack-core" "medplum" "pg-backups")

if [ -f "$REGISTRY_ENV" ]; then
  source "$REGISTRY_ENV"

  : "${registry:?Missing 'registry' in registry-token.env}"
  : "${username:?Missing 'username' in registry-token.env}"
  : "${token:?Missing 'token' in registry-token.env}"

  for ns in "${NAMESPACES[@]}"; do
    echo "==> create/update imagePull secret in namespace: $ns"

    kubectl -n "$ns" create secret docker-registry gitlab-regcred \
      --docker-server="$registry" \
      --docker-username="$username" \
      --docker-password="$token" \
      --dry-run=client -o yaml \
    | kubectl apply -f -
  done
else
  echo "==> registry-token.env missing: skip registry imagePullSecret"
fi
