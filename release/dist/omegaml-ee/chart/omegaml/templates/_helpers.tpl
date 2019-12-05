
#Template helper for dockerconfig secret

{{- define "imagePullSecret" }}
{{- printf "{\"auths\": {\"%s\": {\"auth\": \"%s\"}}}" .Values.dockerRegistry.url (printf "%s:%s" .Values.dockerRegistry.user .Values.dockerRegistry.pass | b64enc) | b64enc }}
{{- end }}
