# Architecture Flux 1 - Routes HTTP Entrantes

Ce fichier donne une vue Mermaid des flux north-south: navigateur ou integration externe vers Traefik, puis vers les Services Kubernetes.

Pour les commandes de debug et les details de chaque host, voir `docs/routage.md` et `docs/tips.md`.

## Vue Globale

```mermaid
flowchart LR
  internet["Client Internet"]
  lan["Client LAN"]
  yunohost["Yunohost / nginx\nTLS + reverse proxy"]
  traefik["Traefik\nkube-system\nLoadBalancer 192.168.2.88\nweb:80 nodePort:32110"]

  internet -->|"HTTPS domaines publics"| yunohost -->|"HTTP, Host conserve"| traefik
  lan -->|"HTTP hosts .lan ou nip.io"| traefik

  subgraph medplum["Namespace medplum"]
    med_ir["IngressRoute medplum-app\nHost medplum.phylcero.fr"]
    med_provider_ing["Ingress medplum-provider\nHost provider.phylcero.fr"]
    med_app_svc["Service medplum-app:3000"]
    med_api_svc["Service medplum-service:80"]
    med_provider_svc["Service medplum-provider:80"]
    med_app["Pod medplum-app"]
    med_api["Pod medplum API"]
    med_provider["Pod medplum-provider"]
  end

  subgraph core["Namespace pompetrack-core"]
    core_streamlit_ir["IngressRoute streamlit-ui\nstreamlit.lan"]
    core_minio_ir["IngressRoute minio-console\nminio.lan"]
    core_ingestion_ir["IngressRoutes ingestion\n/ingest/strength\n/ingest/iphone_api"]
    core_streamlit_svc["Service pompetrack-core-streamlit-ui:8501"]
    core_minio_svc["Service pompetrack-core-minio-console:9001"]
    core_ingestion_svc["Service ingestion:80"]
  end

  subgraph airflow["Namespace airflow"]
    airflow_ir["IngressRoute airflow-ui\nairflow.lan"]
    airflow_svc["Service airflow-api-server:8080"]
  end

  subgraph monitoring["Namespace monitoring"]
    grafana_ir["IngressRoute grafana\ngrafana.lan"]
    prometheus_ir["IngressRoute prometheus\nprometheus.lan"]
    grafana_svc["Service monitoring-grafana:80"]
    prometheus_svc["Service prometheus-prometheus:9090"]
  end

  subgraph llm["Namespace llm-agent"]
    openwebui_ir["IngressRoute open-webui-lan\nopen-webui.lan"]
    backend_ir["IngressRoute agent-backend-lan\nagent-backend.lan"]
    mcpo_ir["IngressRoute agent-backend-mcpo-lan\nagent-tools.lan"]
    agent_ui_ir["IngressRoute streamlit-ui-lan\nstreamlit-agent-llm.lan"]
    openwebui_svc["Service open-webui:8080"]
    backend_svc["Service agent-backend:8000"]
    mcpo_svc["Service agent-backend-mcpo:8000"]
    agent_ui_svc["Service streamlit-agent-llm:8501"]
  end

  traefik --> med_ir
  traefik --> med_provider_ing
  med_ir -->|"/api strip /api"| med_api_svc --> med_api
  med_ir -->|"/auth /oauth2 /.well-known /fhir"| med_api_svc
  med_ir -->|"catch-all"| med_app_svc --> med_app
  med_provider_ing --> med_provider_svc --> med_provider

  traefik --> core_streamlit_ir --> core_streamlit_svc
  traefik --> core_minio_ir --> core_minio_svc
  traefik --> core_ingestion_ir --> core_ingestion_svc

  traefik --> airflow_ir --> airflow_svc
  traefik --> grafana_ir --> grafana_svc
  traefik --> prometheus_ir --> prometheus_svc

  traefik --> openwebui_ir --> openwebui_svc
  traefik --> backend_ir --> backend_svc
  traefik --> mcpo_ir --> mcpo_svc
  traefik --> agent_ui_ir --> agent_ui_svc
```

## Zoom Medplum

```mermaid
flowchart TB
  client["Client HTTPS\nmedplum.phylcero.fr"]
  yunohost["Yunohost / nginx"]
  traefik["Traefik web"]
  ir["IngressRoute medplum/medplum-app"]

  api_rule["Host(medplum.phylcero.fr)\nPathPrefix(/api)"]
  api_mw["Middleware cors\nMiddleware strip-api-prefix"]
  api_svc["Service medplum-service:80"]
  api_pod["Pod Medplum API"]

  auth_rule["Host(medplum.phylcero.fr)\n/auth /oauth2 /.well-known /fhir"]
  ui_rule["Host(medplum.phylcero.fr)\ncatch-all"]
  app_svc["Service medplum-app:3000"]
  app_pod["Pod medplum-app"]

  client --> yunohost --> traefik --> ir
  ir --> api_rule --> api_mw --> api_svc --> api_pod
  ir --> auth_rule --> api_svc
  ir --> ui_rule --> app_svc --> app_pod
```

## Zoom llm-agent

```mermaid
flowchart LR
  client["Client LAN / Open WebUI"]
  traefik["Traefik"]
  lan_mw["Middleware lan-only"]

  subgraph llm["Namespace llm-agent"]
    openwebui["open-webui:8080"]
    backend["agent-backend:8000\nOpenAI-compatible /v1"]
    mcpo["agent-backend-mcpo:8000\nOpenAPI tools"]
    streamlit["streamlit-agent-llm:8501"]
  end

  client -->|"open-webui.lan"| traefik --> lan_mw --> openwebui
  client -->|"agent-backend.lan"| traefik --> lan_mw --> backend
  client -->|"agent-tools.lan"| traefik --> lan_mw --> mcpo
  client -->|"streamlit-agent-llm.lan"| traefik --> lan_mw --> streamlit

  openwebui -->|"provider http://agent-backend:8000/v1"| backend
  openwebui -->|"tools http://agent-backend-mcpo:8000"| mcpo
```
