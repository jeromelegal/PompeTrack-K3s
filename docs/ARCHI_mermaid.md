```mermaid
flowchart LR
  %% =========================
  %% EXTERNE / CLIENTS
  %% =========================
  subgraph External["Externe"]
    iphone["iPhone / Apple Health"]
    user["Utilisateur navigateur"]
    spirom["Spirometer (sqlite DB file)"]
  end

  %% =========================
  %% EDGE (DNS/TLS/Ingress)
  %% =========================
  subgraph Edge["Edge / Entrée cluster"]
    yunohost["Yunohost (TLS)"]
    traefik["Traefik IngressController"]
  end

  %% =========================
  %% NAMESPACE: pomptrack-core
  %% =========================
  subgraph NSCore["Namespace: pompetrack-core"]
    st_deploy["Deployment: streamlit"]
    st_svc["Service: streamlit\n(streamlit.pompetrack-core.svc)"]

    ing_deploy["Deployment: ingestion-api\n(FastAPI/Gunicorn)"]
    ing_svc["Service: ingestion\n(ingestion.pompetrack-core.svc)"]

    minio_sts["StatefulSet: minio"]
    minio_svc["Service: minio\n(minio.pompetrack-core.svc)"]
    minio_job["Job/CronJob: minio-init\n(create buckets)"]

    b1["Bucket: raw-iphone (json)"]
    b2["Bucket: raw-manual (json)"]
    b3["Bucket: raw-db-spirometer (sqlite)"]
    b4["Bucket: raw-spirometer (json)"]
    b5["Bucket: processed-fhir (json)"]
    b6["Bucket: reports (...)"]
  end

  %% =========================
  %% NAMESPACE: orchestration
  %% =========================
  subgraph NSOrch["Namespace: orchestration"]
    af_deploy["Deployment(s): Airflow\n(web/scheduler/worker)"]
    af_svc["Service: airflow (web UI)\n(airflow.orchestration.svc)"]
  end

  %% =========================
  %% NAMESPACE: pompetrack-workers
  %% =========================
  subgraph NSW["Namespace: pompetrack-workers"]
    ws_deploy["Deployment: worker-sqlite"]
    wf_deploy["Deployment/Job: worker-fhir"]
    wst_deploy["Deployment: worker-stream"]

    ws_svc["Service: worker-sqlite\n(worker-sqlite.pompetrack-workers.svc)"]
    wf_svc["Service: worker-fhir\n(worker-fhir.pompetrack-workers.svc)"]
    wst_svc["Service: worker-stream\n(worker-stream.pompetrack-workers.svc)"]
  end

  %% =========================
  %% NAMESPACE: medplum
  %% =========================
  subgraph NSMed["Namespace: medplum"]
    mp_server_deploy["Deployment: medplum-server"]
    mp_server_svc["Service: medplum-server\n(medplum-server.medplum.svc)"]

    mp_app_deploy["Deployment: medplum-app"]
    mp_app_svc["Service: medplum-app\n(medplum-app.medplum.svc)"]

    mp_chart_deploy["Deployment: medplum-chart (option)"]
    mp_chart_svc["Service: medplum-chart (option)"]

    pg_sts["StatefulSet: postgres"]
    pg_svc["Service: postgres\n(postgres.medplum.svc)"]
  end

  %% =========================
  %% NAMESPACE: observability
  %% =========================
  subgraph NSObs["Namespace: observability"]
    prom["Deployment/StatefulSet: prometheus"]
    graf["Deployment: grafana"]
    prom_svc["Service: prometheus"]
    graf_svc["Service: grafana"]
  end

  %% =========================
  %% (Option) NAMESPACE: security
  %% =========================
  subgraph NSSec["Namespace: security (option)"]
    redis_deploy["Deployment/StatefulSet: redis"]
    redis_svc["Service: redis"]
    seed_job["Job: seed-redis"]
  end

  %% =========================
  %% Flux NORTH-SOUTH (public)
  %% =========================
  user --> yunohost --> traefik
  traefik --> mp_app_svc
  traefik --> mp_server_svc
  traefik --> st_svc
  %% (si tu exposes ingestion publiquement plus tard)
  %% traefik --> ing_svc

  %% =========================
  %% Flux DATA IN (upload vers ingestion)
  %% =========================
  iphone -->|"upload/json"| traefik --> ing_svc
  spirom -->|"upload/sqlite"| traefik --> ing_svc
  st_svc -->|"upload mesures / fichiers"| ing_svc

  %% =========================
  %% Ingestion -> MinIO
  %% =========================
  ing_deploy -->|"PUT/GET via S3 API"| minio_svc
  minio_sts --- b1
  minio_sts --- b2
  minio_sts --- b3
  minio_sts --- b4
  minio_sts --- b5
  minio_sts --- b6
  minio_job --> minio_sts

  %% =========================
  %% Orchestration -> workers
  %% =========================
  af_deploy -->|"trigger"| ws_svc
  af_deploy -->|"trigger"| wf_svc

  %% =========================
  %% Workers <-> MinIO
  %% =========================
  ws_deploy -->|"GET raw-db-spirometer"| minio_svc
  ws_deploy -->|"PUT raw-spirometer"| minio_svc
  wf_deploy -->|"GET raw-iphone/raw-manual/raw-spirometer"| minio_svc
  wf_deploy -->|"PUT processed-fhir"| minio_svc

  %% =========================
  %% worker-fhir -> Medplum
  %% =========================
  wf_deploy -->|"FHIR batch"| mp_server_svc

  %% =========================
  %% worker-stream -> Medplum -> Streamlit
  %% =========================
  st_svc -->|"query"| wst_svc
  wst_deploy -->|"FHIR API"| mp_server_svc
  wst_svc -->|"results"| st_svc

  %% =========================
  %% Medplum -> Postgres
  %% =========================
  mp_server_deploy --> pg_svc

  %% =========================
  %% Observability
  %% =========================
  prom --> graf

  %% =========================
  %% Security (option)
  %% =========================
  seed_job --> redis_svc
