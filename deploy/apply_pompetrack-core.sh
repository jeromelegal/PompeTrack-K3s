#!/usr/bin/env bash
set -euo pipefail

helm -n pompetrack-core uninstall pompetrack-core || true
kubectl delete namespace pompetrack-core || true

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

helm_post_renderer_arg() {
  local plugin_name="$1"
  local renderer_path="$2"
  local plugin_dir="$3"
  local helm_major

  helm_major="$(helm version 2>/dev/null | sed -n 's/.*Version:"v\([0-9][0-9]*\).*/\1/p; s/^v\([0-9][0-9]*\).*/\1/p' | head -n1)"

  if [ "${helm_major:-0}" = 3 ]; then
    printf '%s\n' "$renderer_path"
  else
    if ! helm plugin list 2>/dev/null | awk -v name="$plugin_name" '$1 == name { found = 1 } END { exit found ? 0 : 1 }'; then
      echo "==> Helm 4 post-renderer plugin install: $plugin_name" >&2
      helm plugin install "$plugin_dir" >&2
    fi
    printf '%s\n' "$plugin_name"
  fi
}

# Namespaces create
echo "==> Namespaces (must come first for Istio injection)"
apply_file_if_exists deploy/namespaces/pompetrack-core/00-namespace.yaml

# Safety: ensure namespaces exist even if YAML missing
kubectl get ns pompetrack-core >/dev/null 2>&1 || kubectl apply -f deploy/namespaces/pompetrack-core/00-namespace.yaml

# Registry credentials
echo "==> Registry imagePull secrets"
./deploy/secrets/registry/init-secrets.sh

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
POMPETRACK_CORE_POST_RENDERER="$(helm_post_renderer_arg \
  pompetrack-core-post-renderer \
  ./deploy/post-renderer/pompetrack-core/kustomize.sh \
  ./deploy/post-renderer/pompetrack-core)"
helm upgrade --install pompetrack-core deploy/charts/pompetrack-core \
  -f deploy/charts/pompetrack-core/values-minio.yaml \
  -n pompetrack-core \
  --post-renderer "$POMPETRACK_CORE_POST_RENDERER"

# Ingress policies
echo "==> Ingress (Traefik objects - always reapplied)"
apply_dir_ordered deploy/namespaces/pompetrack-core/ingress

# Verify
echo "==> Done"
kubectl get pods -n pompetrack-core