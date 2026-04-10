from prometheus_client import Counter, Gauge, Histogram

UNKNOWN_CATEGORY_TOTAL = Counter(
    "iphone_unknown_category_total",
    "Nombre de catégories JSON inconnues détectées",
    ["category"],
)

IPHONE_PIPELINE_RUN_TOTAL = Counter(
    "iphone_pipeline_run_total",
    "Nombre de lancements du pipeline iPhone",
)

IPHONE_PIPELINE_RUN_SUCCESS_TOTAL = Counter(
    "iphone_pipeline_run_success_total",
    "Nombre de runs réussis du pipeline iPhone",
)

IPHONE_PIPELINE_RUN_FAILURE_TOTAL = Counter(
    "iphone_pipeline_run_failure_total",
    "Nombre de runs échoués du pipeline iPhone",
)

IPHONE_PIPELINE_OBJECT_TOTAL = Counter(
    "iphone_pipeline_object_total",
    "Nombre d'objets MinIO traités par le pipeline iPhone",
)

IPHONE_PIPELINE_OBJECT_SUCCESS_TOTAL = Counter(
    "iphone_pipeline_object_success_total",
    "Nombre d'objets MinIO traités avec succès",
)

IPHONE_PIPELINE_OBJECT_FAILURE_TOTAL = Counter(
    "iphone_pipeline_object_failure_total",
    "Nombre d'objets MinIO en échec",
)

IPHONE_SUBPIPELINE_RUN_TOTAL = Counter(
    "iphone_subpipeline_run_total",
    "Nombre d'exécutions des sous-pipelines",
    ["stage"],
)

IPHONE_SUBPIPELINE_SUCCESS_TOTAL = Counter(
    "iphone_subpipeline_success_total",
    "Nombre d'exécutions réussies des sous-pipelines",
    ["stage"],
)

IPHONE_SUBPIPELINE_FAILURE_TOTAL = Counter(
    "iphone_subpipeline_failure_total",
    "Nombre d'échecs des sous-pipelines",
    ["stage", "error_type"],
)

SPLIT_JSON_DURATION_SECONDS = Histogram(
    "iphone_split_json_duration_seconds",
    "Temps d'exécution de split_json",
)

IPHONE_PIPELINE_DURATION_SECONDS = Histogram(
    "iphone_pipeline_duration_seconds",
    "Temps d'exécution du pipeline iPhone complet",
)

IPHONE_SUBPIPELINE_DURATION_SECONDS = Histogram(
    "iphone_subpipeline_duration_seconds",
    "Temps d'exécution des sous-pipelines",
    ["stage"],
)

IPHONE_PIPELINE_LAST_SUCCESS_UNIXTIME = Gauge(
    "iphone_pipeline_last_success_unixtime",
    "Timestamp Unix du dernier succès du pipeline iPhone",
)