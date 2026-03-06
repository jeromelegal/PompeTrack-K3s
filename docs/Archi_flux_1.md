# Page 1 — Architecture & flux

## Légende (commune)

* **U** : client (navigateur)
* **Y** : Yunohost/nginx (TLS termination + SSO)
* **T** : Traefik (K3s, entryPoint `web`, NodePort `31725`)
* **IR_*** : IngressRoute Traefik
* **MW_*** : Middleware Traefik
* **SVC_*** : Service Kubernetes
* **POD_*** : Pod (souvent avec sidecar Istio)

## Diagramme A — Vue d’ensemble (routes HTTP)

```mermaid
flowchart LR
  U["U: Client navigateur"] -->|"HTTPS app.phylcero.fr"| Y["Y: Yunohost/nginx\nTLS termination + SSO"]
  Y -->|"HTTP vers NodePort 31725\nHost conservé"| T["T: Traefik (K3s)\nentryPoint: web\nNodePort: 31725"]

  subgraph MED["Namespace: medplum"]
    IR_MED["IR_MED: IngressRoute\nmedplum/medplum-app"]
    MW_STRIP["MW_STRIP: Middleware\nstripPrefix: /api"]
    SVC_APP["SVC_APP: Service\nmedplum-app:3000"]
    SVC_API["SVC_API: Service\nmedplum-service:80"]
    POD_APP["POD_APP: Pod\nmedplum-app\n(+ istio-envoy)"]
    POD_API["POD_API: Pod\nmedplum (server)\n(+ istio-envoy)\nport app: 8103"]
  end

  subgraph CORE["Namespace: pompetrack-core"]
    IR_MINIO["IR_MINIO: IngressRoute\nminio-console"]
    MW_LAN["MW_LAN: Middleware\nipAllowList (LAN)"]
    SVC_MINIO_CONSOLE["SVC_MINIO_CONSOLE: Service\npompetrack-core-minio-console:9001"]
    POD_MINIO["POD_MINIO: Pod\nminio\n(+ istio-envoy)\nAPI:9000 / Console:9001"]
  end

  T --> IR_MED
  IR_MED -->|"Host(app.phylcero.fr)"| SVC_APP --> POD_APP
  IR_MED -->|"Host(app.phylcero.fr) AND PathPrefix(/api)"| MW_STRIP --> SVC_API --> POD_API

  T --> IR_MINIO --> MW_LAN --> SVC_MINIO_CONSOLE --> POD_MINIO
```

## Diagramme B — Zoom Traefik (Medplum)

```mermaid
flowchart TB
  T["T: Traefik\nentryPoint: web"] --> IR_MED["IR_MED: IngressRoute\nmedplum/medplum-app"]

  R_API["Rule:\nHost(app.phylcero.fr) AND PathPrefix(/api)"]
  MW_STRIP["MW_STRIP: stripPrefix\n/api"]
  SVC_API["SVC_API: medplum-service:80\n(target pod:8103)"]

  R_UI["Rule:\nHost(app.phylcero.fr)"]
  SVC_APP["SVC_APP: medplum-app:3000"]

  IR_MED --> R_API --> MW_STRIP --> SVC_API
  IR_MED --> R_UI --> SVC_APP
```

---
