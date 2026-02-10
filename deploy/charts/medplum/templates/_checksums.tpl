{{- define "pompetrack.secretChecksum" -}}
{{- $name := index . 0 -}}
{{- $ctx := index . 1 -}}
{{- $secret := lookup "v1" "Secret" $ctx.Release.Namespace $name -}}
{{- if $secret -}}
{{- toJson $secret.data | sha256sum -}}
{{- else -}}
missing-secret
{{- end -}}
{{- end -}}