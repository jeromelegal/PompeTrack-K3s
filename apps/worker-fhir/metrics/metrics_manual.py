from prometheus_client import Counter, Gauge, Histogram

MANUAL_PIPELINE_RUN_TOTAL = Counter(
    "manual_pipeline_run_total",
    "Nombre de lancements du pipeline manual",
)

MANUAL_PIPELINE_RUN_SUCCESS_TOTAL = Counter(
    "manual_pipeline_run_success_total",
    "Nombre de runs réussis du pipeline manual",
)

MANUAL_PIPELINE_RUN_FAILURE_TOTAL = Counter(
    "manual_pipeline_run_failure_total",
    "Nombre de runs échoués du pipeline manual",
)

MANUAL_PIPELINE_OBJECT_TOTAL = Counter(
    "manual_pipeline_object_total",
    "Nombre d'objets MinIO traités par le pipeline manual",
)

MANUAL_PIPELINE_OBJECT_SUCCESS_TOTAL = Counter(
    "manual_pipeline_object_success_total",
    "Nombre d'objets MinIO traités avec succès",
)

MANUAL_PIPELINE_OBJECT_FAILURE_TOTAL = Counter(
    "manual_pipeline_object_failure_total",
    "Nombre d'objets MinIO en échec",
)

MANUAL_PIPELINE_DURATION_SECONDS = Histogram(
    "manual_pipeline_duration_seconds",
    "Temps d'exécution du pipeline manual complet",
)

MANUAL_PIPELINE_LAST_SUCCESS_UNIXTIME = Gauge(
    "manual_pipeline_last_success_unixtime",
    "Timestamp Unix du dernier succès du pipeline manual",
)