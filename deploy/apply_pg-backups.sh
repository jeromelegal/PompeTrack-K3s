#!/usr/bin/env bash
set -euo pipefail

kubectl delete namespace pg-backups || true

apply_dir_ordered() {
  local dir="$1"
  if [ -d "$dir" ] && ls -1 "$dir"/*.yaml >/dev/null 2>&1; then
    echo "==> apply (ordered): $dir"
    # Ordre lexical (00-, 01-, 02-...) = déterministe
    while IFS= read -r f; do
      kubectl apply -f "$f"
    done < <(ls -1 "$dir"/*.yaml | sort)
  else
    echo "==> skip (empty): $dir"
  fi
}

apply_file_if_exists() {
  local f="$1"
  if [ -f "$f" ]; then
    echo "==> apply file: $f"
    kubectl apply -f "$f"
  else
    echo "==> skip (missing): $f"
  fi
}

# Namespaces create
echo "==> Namespaces (must come first for Istio injection)"
apply_file_if_exists deploy/namespaces/pg-backups/00-namespace.yaml
# apply rbac for pg-backups
apply_file_if_exists deploy/charts/pg-backups/00-rbac.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns pg-backups >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/pg-backups/00-namespace.yaml

# Net Policies
echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/pg-backups/netpol

# Wait for Istio
echo "==> Wait for istiod (validation webhook needs ready endpoints)"
kubectl -n istio-system rollout status deploy/istiod --timeout=180s
kubectl -n istio-system wait --for=condition=Available deploy/istiod --timeout=180s
kubectl -n istio-system get endpoints istiod

# Istio policies
echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/pg-backups/istio

# Secrets scripts
echo "==> Medplum secrets"
./deploy/secrets/registry/init-secrets.sh

# PG-BACKUPS
echo "==> Apply pg-backups secrets"
kubectl apply -f deploy/secrets/pg-backups/secret.yaml
echo "==> Apply pg-backups configmap-script"
kubectl apply -f deploy/charts/pg-backups/configmap-script.yaml
echo "==> Apply pg-backups cronjobs"
kubectl apply -f deploy/charts/pg-backups/cronjobs.yaml

# Verify
echo "==> Done"
kubectl -n pg-backups get cronjob
