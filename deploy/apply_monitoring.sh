#!/usr/bin/env bash
set -euo pipefail

helm -n monitoring uninstall airflow || true
kubectl delete namespace monitoring

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
apply_file_if_exists deploy/namespaces/monitoring/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns monitoring >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/monitoring/00-namespace.yaml

# Net Policies
echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/monitoring/netpol

# Istio policies
echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/monitoring/istio

# Secrets scripts
echo "==> Monitoring secrets"
./deploy/secrets/monitoring/init-secrets.sh

## Helm umbrella Airflow namespace
echo "==> Helm install/upgrade monitoring"
helm upgrade --install monitoring deploy/charts/monitoring \
  -f deploy/charts/monitoring/values.yaml \
  -n monitoring 

# Ingress policies
echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/monitoring/ingress


# Verify
echo "==> Done"
kubectl get pods -n monitoring
