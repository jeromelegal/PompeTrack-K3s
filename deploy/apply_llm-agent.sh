#!/usr/bin/env bash
set -euo pipefail

helm -n llm-agent uninstall llm-agent || true
kubectl delete namespace llm-agent || true

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
apply_file_if_exists deploy/namespaces/llm-agent/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns llm-agent >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/llm-agent/00-namespace.yaml

# Net Policies
echo "==> Netpol (strict baseline + targeted allows)"
apply_dir_ordered deploy/namespaces/llm-agent/netpol

# Wait for Istio
echo "==> Wait for istiod (validation webhook needs ready endpoints)"
kubectl -n istio-system rollout status deploy/istiod --timeout=180s
kubectl -n istio-system wait --for=condition=Available deploy/istiod --timeout=180s
kubectl -n istio-system get endpoints istiod

# Istio policies
echo "==> Istio policies (PeerAuth/Authz)"
apply_dir_ordered deploy/namespaces/llm-agent/istio

# Secrets scripts
echo "==> Registry secrets"
./deploy/secrets/registry/init-secrets.sh

# Secrets scripts
echo "==> Monitoring secrets"
./deploy/secrets/llm-agent/init-secrets.sh

# Helm update
echo "==> Helm deps"
helm dependency update deploy/charts/llm-agent || true

## Helm umbrella llm-agent namespace
echo "==> Helm install/upgrade llm-agent"
helm upgrade --install llm-agent deploy/charts/llm-agent \
  -f deploy/charts/llm-agent/values.yaml \
  -n llm-agent 

# Ingress policies
echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/llm-agent/ingress

# Verify
echo "==> Done"
kubectl get pods -n llm-agent

