# Plan de routage bout en bout

## A) Medplum public — Host `app.phylcero.fr`

### A1) UI / assets

**Entrée :** `https://app.phylcero.fr/` (et `/assets/*`)

1. **Client (navigateur)**
2. **Yunohost / nginx**

   * termine TLS (HTTP/2 côté client)
   * SSO (header observé : `x-sso-wat: You've just been SSOed`)
   * reverse proxy vers Traefik en interne (NodePort)
3. **Traefik (K3s, kube-system)**

   * entryPoint : `web` (port 80) → NodePort `192.168.2.88:31725`
   * provider : `kubernetescrd`
   * ressource : `IngressRoute` `medplum/medplum-app`
   * règle : `Host(\`app.phylcero.fr`)` (route “catch-all”)
   * backend : Service `medplum-app` port `3000`
4. **Service K8s** `medplum-app.medplum.svc.cluster.local:3000`
5. **Istio data plane (Envoy)** sur le pod (réponse observée `Server: istio-envoy`)
6. **Pod** `medplum-app` → réponse HTML/JS/CSS

✅ Preuve observée : `X-Envoy-Decorator-Operation: medplum-app.medplum.svc.cluster.local:3000/*` et HTTP 200.

---

### A2) API

**Entrée :** `https://app.phylcero.fr/api/...` (ex: `/api/healthcheck`)

1. **Client**
2. **Yunohost / nginx** (TLS + SSO) → reverse proxy vers Traefik
3. **Traefik** (`web` / NodePort 31725)
4. **IngressRoute** `medplum/medplum-app`, route prioritaire :

   * match : `Host(\`app.phylcero.fr`) && PathPrefix(`/api`)`
   * middleware : `strip-api-prefix`

     * config : `stripPrefix.prefixes: ["/api"]`
   * backend : Service `medplum-service` port `80`
5. **Réécriture de chemin**

   * requête client `/api/healthcheck`
   * devient `/healthcheck` côté backend `medplum-service:80`
6. **Service K8s** `medplum-service.medplum.svc.cluster.local:80`
7. **Istio data plane (Envoy)** → pod API Medplum
8. **Pod** Medplum API → JSON 200

✅ Preuve observée : `X-Envoy-Decorator-Operation: medplum-service.medplum.svc.cluster.local:80/*` et HTTP 200.

---

## B) MinIO console (LAN) — Host `minio.lan`

**Entrée :** `http://minio.lan/` (via DNS/hosts LAN)

1. **Client LAN**
2. **Traefik** (`web` port 80 / NodePort 31725 selon ton accès)
3. **IngressRoute** `pompetrack-core/minio-console`

   * match : `Host(\`minio.lan`)`
   * middleware : `lan-only`

     * `ipAllowList.sourceRange` :

       * `192.168.2.0/24` (LAN)
       * `10.42.0.0/16` (Pods K3s)
       * `10.43.0.0/16` (Services K3s)
   * backend : service `pompetrack-core-minio-console` port `9001`
4. **Service K8s** `pompetrack-core-minio-console.pompetrack-core.svc.cluster.local:9001`
5. (Potentiellement Envoy si pod dans mesh) → console MinIO

✅ Ici, le contrôle d’accès réseau est fait au niveau Traefik middleware (IP allowlist).

---

# Diagramme texte (propre, “lecture rapide”)

**Medplum UI**
`Client` → `Yunohost/nginx (TLS+SSO)` → `Traefik web :31725 (Host=app.phylcero.fr)` → `IngressRoute medplum-app (Host match)` → `svc medplum-app:3000` → `istio-envoy` → `pod medplum-app`

**Medplum API**
`Client` → `Yunohost/nginx (TLS+SSO)` → `Traefik web :31725 (Host=app.phylcero.fr)` → `IngressRoute medplum-app (Host && PathPrefix /api)` → `Middleware stripPrefix(/api)` → `svc medplum-service:80` → `istio-envoy` → `pod medplum API`

**MinIO console LAN**
`Client LAN (IP ∈ allowlist)` → `Traefik web` → `IngressRoute minio-console (Host=minio.lan)` → `Middleware ipAllowList(192.168.2.0/24,10.42/16,10.43/16)` → `svc pompetrack-core-minio-console:9001` → `pod console`

---

# Diagramme Mermaid

## 1) Vue “bout en bout” (global)

```mermaid
flowchart LR
  %% Actors
  U["Client navigateur"]
  Y["Yunohost / nginx\nTLS termination + SSO"]
  T["Traefik (K3s)\nentryPoint: web\nNodePort 31725"]
  IR_MED["IngressRoute: medplum/medplum-app"]
  IR_MINIO["IngressRoute: pompetrack-core/minio-console"]

  %% Medplum services/pods
  SVC_APP["svc: medplum-app\nport 3000"]
  SVC_API["svc: medplum-service\nport 80"]
  MW_STRIP["Middleware: strip-api-prefix\nstripPrefix: /api"]
  POD_APP["pod: medplum-app\n+ istio-envoy"]
  POD_API["pod: medplum (API)\n+ istio-envoy"]

  %% Minio services
  MW_LAN["Middleware: lan-only\nipAllowList:\n192.168.2.0/24\n10.42.0.0/16\n10.43.0.0/16"]
  SVC_MINIO_CONSOLE["svc: pompetrack-core-minio-console\nport 9001"]
  POD_MINIO_CONSOLE["pod: minio console\n(mesh si injecté)"]

  %% UI path
  U -->|"HTTPS app.phylcero.fr\n/ or /assets/*"| Y
  Y -->|"HTTP to NodePort\nHost: app.phylcero.fr"| T
  T -->|"match Host(app.phylcero.fr)"| IR_MED
  IR_MED --> SVC_APP --> POD_APP

  %% API path
  U -->|"HTTPS app.phylcero.fr\n/api/*"| Y
  T -->|"match Host(app.phylcero.fr) AND PathPrefix(/api)"| IR_MED
  IR_MED --> MW_STRIP --> SVC_API --> POD_API

  %% Minio console path
  U -->|"HTTP minio.lan"| T
  T -->|"match Host(minio.lan)"| IR_MINIO
  IR_MINIO --> MW_LAN --> SVC_MINIO_CONSOLE --> POD_MINIO_CONSOLE
```

## 2) Zoom Medplum (routes Traefik)

```mermaid
flowchart TB
  T["Traefik\nentryPoint: web"]
  IR["IngressRoute\nmedplum/medplum-app"]

  R1["Rule 1:\nHost(app.phylcero.fr) AND PathPrefix(/api)"]
  MW["Middleware: strip-api-prefix\nstripPrefix: /api"]
  SAPI["Service: medplum-service:80"]

  R2["Rule 2:\nHost(app.phylcero.fr)"]
  SAPP["Service: medplum-app:3000"]

  T --> IR
  IR --> R1 --> MW --> SAPI
  IR --> R2 --> SAPP
```

---
