{{- define "aimembqwen3vino.fullname" -}}
{{- .Values.fullnameOverride | default .Chart.Name | trunc 63 | trimSuffix "-" }}
{{- end -}}
