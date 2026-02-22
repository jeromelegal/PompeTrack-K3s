{{/*
=============================================================================
Nom de base de la release
=============================================================================
*/}}
{{- define "airflow.name" -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
=============================================================================
Labels communs
=============================================================================
*/}}
{{- define "airflow.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
=============================================================================
Labels de sélection (selector)
=============================================================================
*/}}
{{- define "airflow.selectorLabels" -}}
app.kubernetes.io/name: {{ include "airflow.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
=============================================================================
Nom du service account
=============================================================================
*/}}
{{- define "airflow.serviceAccountName" -}}
{{- .Values.serviceAccount.name }}
{{- end }}

{{/*
=============================================================================
Image Airflow complète
=============================================================================
*/}}
{{- define "airflow.image" -}}
{{ .Values.images.airflow.repository }}:{{ .Values.images.airflow.tag }}
{{- end }}

{{/*
=============================================================================
Variables d'environnement communes à tous les composants
=============================================================================
*/}}
{{- define "airflow.commonEnv" -}}
- name: AIRFLOW__DATABASE__SQL_ALCHEMY_CONN
  valueFrom:
    secretKeyRef:
      name: airflow-db-credentials
      key: connection
- name: AIRFLOW__CORE__FERNET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.airflow.fernetKeySecret }}
      key: fernet-key
- name: AIRFLOW__API__SECRET_KEY
  valueFrom:
    secretKeyRef:
      name: {{ .Values.airflow.webserverSecretKey }}
      key: webserver-secret-key
{{- end }}
