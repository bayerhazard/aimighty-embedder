#!/bin/bash
# Embedder Envoy Config Patcher
# Patches route timeouts: 15s → 120s for large document embedding
set -e

NAMESPACE="embedding-dev-aimighty"
CONFIGMAP="olares-sidecar-config-embedding-dev"
RETRY_INTERVAL=2

echo "[INIT] Starting Envoy timeout patcher..."

# Wait for sidecar to create the ConfigMap
sleep 15

MAX_RETRIES=90
retry=0
while [ $retry -lt $MAX_RETRIES ]; do
    if python3 -c "
import json, urllib.request, os

token = open('/var/run/secrets/kubernetes.io/serviceaccount/token').read().strip()
ca = '/var/run/secrets/kubernetes.io/serviceaccount/ca.crt'
ns = '${NAMESPACE}'
cm = '${CONFIGMAP}'
url = f'https://kubernetes.default.svc/api/v1/namespaces/{ns}/configmaps/{cm}'

req = urllib.request.Request(url)
req.add_header('Authorization', f'Bearer {token}')
import ssl
ctx = ssl.create_default_context(cafile=ca)
try:
    resp = urllib.request.urlopen(req, context=ctx, timeout=5)
    data = json.loads(resp.read())
    envoy = data['data'].get('envoy.yaml', '')
    patched = envoy.replace('timeout: 15s', 'timeout: 120s')
    if patched != envoy:
        data['data']['envoy.yaml'] = patched
        for k in ['resourceVersion', 'uid', 'creationTimestamp', 'generation', 'managedFields']:
            data['metadata'].pop(k, None)
        data['metadata'].pop('annotations', None)
        body = json.dumps(data).encode()
        req2 = urllib.request.Request(url, data=body, method='PUT')
        req2.add_header('Authorization', f'Bearer {token}')
        req2.add_header('Content-Type', 'application/json')
        urllib.request.urlopen(req2, context=ctx, timeout=10)
        print('PATCHED')
    else:
        print('NO_CHANGE')
except urllib.error.HTTPError as e:
    print(f'ERROR:{e.code}')
    exit(1)
except Exception as e:
    print(f'ERROR:{e}')
    exit(1)
" 2>/dev/null | grep -q "PATCHED"; then
        echo "[INIT] ✓ Patched timeout 15s → 120s"
        break
    fi
    
    retry=$((retry + 1))
    echo "[INIT] Waiting for ConfigMap... ($retry/$MAX_RETRIES)"
    sleep $RETRY_INTERVAL
done

if [ $retry -eq $MAX_RETRIES ]; then
    echo "[INIT] WARNING: ConfigMap not found after $MAX_RETRIES attempts, continuing anyway..."
fi

echo "[INIT] Done. Passing control to main process..."

exec "$@"
