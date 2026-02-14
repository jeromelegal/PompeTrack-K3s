#!/usr/bin/env bash
set -euo pipefail

echo "==> create/update registry secrets from .env"
REGISTRY_ENV="deploy/secrets/registry/registry-token.env"
NAMESPACE=pompetrack-core

if [ -f "$REGISTRY_ENV" ]; then
  # shellcheck disable=SC1090
  source "$REGISTRY_ENV"

  : "${registry:?Missing 'registry' in registry-token.env}"
  : "${username:?Missing 'username' in registry-token.env}"
  : "${token:?Missing 'token' in registry-token.env}"

  echo "==> create/update imagePull secret for registry: $registry"
  kubectl -n "$NAMESPACE" create secret docker-registry gitlab-regcred \
    --docker-server="$registry" \
    --docker-username="$username" \
    --docker-password="$token" \
    --dry-run=client -o yaml \
  | kubectl apply -f -
else
  echo "==> registry-token.env missing: skip registry imagePullSecret"
fi
