from prometheus_client import Counter, Gauge, Histogram

STRENGTH_PIPELINE_RUN_TOTAL = Counter(
    "strength_pipeline_run_total",
    "Nombre de lancements du pipeline strength",
)

STRENGTH_PIPELINE_RUN_SUCCESS_TOTAL = Counter(
    "strength_pipeline_run_success_total",
    "Nombre de runs réussis du pipeline strength",
)

STRENGTH_PIPELINE_RUN_FAILURE_TOTAL = Counter(
    "strength_pipeline_run_failure_total",
    "Nombre de runs échoués du pipeline strength",
)

STRENGTH_PIPELINE_OBJECT_TOTAL = Counter(
    "strength_pipeline_object_total",
    "Nombre d'objets MinIO traités par le pipeline strength",
)

STRENGTH_PIPELINE_OBJECT_SUCCESS_TOTAL = Counter(
    "strength_pipeline_object_success_total",
    "Nombre d'objets MinIO traités avec succès",
)

STRENGTH_PIPELINE_OBJECT_FAILURE_TOTAL = Counter(
    "strength_pipeline_object_failure_total",
    "Nombre d'objets MinIO en échec",
)

STRENGTH_PIPELINE_DURATION_SECONDS = Histogram(
    "strength_pipeline_duration_seconds",
    "Temps d'exécution du pipeline strength complet",
)

STRENGTH_PIPELINE_LAST_SUCCESS_UNIXTIME = Gauge(
    "strength_pipeline_last_success_unixtime",
    "Timestamp Unix du dernier succès du pipeline strength",
)