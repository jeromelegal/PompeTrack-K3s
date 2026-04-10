from prometheus_client import Counter, Gauge, Histogram

MEDICATION_PIPELINE_RUN_TOTAL = Counter(
    "medication_pipeline_run_total",
    "Nombre de lancements du pipeline medication",
)

MEDICATION_PIPELINE_RUN_SUCCESS_TOTAL = Counter(
    "medication_pipeline_run_success_total",
    "Nombre de runs réussis du pipeline medication",
)

MEDICATION_PIPELINE_RUN_FAILURE_TOTAL = Counter(
    "medication_pipeline_run_failure_total",
    "Nombre de runs échoués du pipeline medication",
)

MEDICATION_PIPELINE_OBJECT_TOTAL = Counter(
    "medication_pipeline_object_total",
    "Nombre d'objets MinIO traités par le pipeline medication",
)

MEDICATION_PIPELINE_OBJECT_SUCCESS_TOTAL = Counter(
    "medication_pipeline_object_success_total",
    "Nombre d'objets MinIO traités avec succès",
)

MEDICATION_PIPELINE_OBJECT_FAILURE_TOTAL = Counter(
    "medication_pipeline_object_failure_total",
    "Nombre d'objets MinIO en échec",
)

MEDICATION_PIPELINE_DURATION_SECONDS = Histogram(
    "medication_pipeline_duration_seconds",
    "Temps d'exécution du pipeline medication complet",
)

MEDICATION_PIPELINE_LAST_SUCCESS_UNIXTIME = Gauge(
    "medication_pipeline_last_success_unixtime",
    "Timestamp Unix du dernier succès du pipeline medication",
)