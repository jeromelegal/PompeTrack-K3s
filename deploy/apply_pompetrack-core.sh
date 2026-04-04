#!/usr/bin/env bash
set -euo pipefail

helm -n pompetrack-core uninstall pompetrack-core || true
kubectl delete namespace pompetrack-core

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
apply_file_if_exists deploy/namespaces/pompetrack-core/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns pompetrack-core >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/pompetrack-core/00-namespace.yaml

# Net Policies
echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/pompetrack-core/netpol

# Istio policies
echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/pompetrack-core/istio

# Secrets scripts
echo "==> Pompetrack-core secrets"
./deploy/secrets/pompetrack-core/init-secrets.sh

# ==> Publish IDs as ConfigMap (non-secret) for pompetrack-core
echo "==> Publish Medplum IDs (ConfigMap)"
kubectl -n pompetrack-core create configmap medplum-ids \
  --from-env-file=deploy/outputs/pompetrack-core/medplum-ids.env \
  -o yaml --dry-run=client \
| kubectl apply -f -

### Helm umbrella Pompetrack-core namespace
echo "==> Helm install/upgrade pompetrack-core (with post-renderer patches)"
helm upgrade --install pompetrack-core deploy/charts/pompetrack-core \
  -f deploy/charts/pompetrack-core/values-minio.yaml \
  -n pompetrack-core \
  --post-renderer ./deploy/post-renderer/pompetrack-core/kustomize.sh

# Ingress policies
echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/pompetrack-core/ingress

# Verify
echo "==> Done"
kubectl get pods -n pompetrack-core