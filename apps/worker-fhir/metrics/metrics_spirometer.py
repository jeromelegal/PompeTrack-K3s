from prometheus_client import Counter, Gauge, Histogram

SPIROMETER_PIPELINE_RUN_TOTAL = Counter(
    "spirometer_pipeline_run_total",
    "Nombre de lancements du pipeline spirometer",
)

SPIROMETER_PIPELINE_RUN_SUCCESS_TOTAL = Counter(
    "spirometer_pipeline_run_success_total",
    "Nombre de runs réussis du pipeline spirometer",
)

SPIROMETER_PIPELINE_RUN_FAILURE_TOTAL = Counter(
    "spirometer_pipeline_run_failure_total",
    "Nombre de runs échoués du pipeline spirometer",
)

SPIROMETER_PIPELINE_OBJECT_TOTAL = Counter(
    "spirometer_pipeline_object_total",
    "Nombre d'objets MinIO traités par le pipeline spirometer",
)

SPIROMETER_PIPELINE_OBJECT_SUCCESS_TOTAL = Counter(
    "spirometer_pipeline_object_success_total",
    "Nombre d'objets MinIO traités avec succès",
)

SPIROMETER_PIPELINE_OBJECT_FAILURE_TOTAL = Counter(
    "spirometer_pipeline_object_failure_total",
    "Nombre d'objets MinIO en échec",
)

SPIROMETER_PIPELINE_DURATION_SECONDS = Histogram(
    "spirometer_pipeline_duration_seconds",
    "Temps d'exécution du pipeline spirometer complet",
)

SPIROMETER_PIPELINE_LAST_SUCCESS_UNIXTIME = Gauge(
    "spirometer_pipeline_last_success_unixtime",
    "Timestamp Unix du dernier succès du pipeline spirometer",
)