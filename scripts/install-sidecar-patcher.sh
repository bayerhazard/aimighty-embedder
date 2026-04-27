#!/bin/bash
# Install Olares Sidecar Envoy ConfigMap Patcher as a systemd service
#
# WHAT:
#   Installs and enables a systemd service that periodically patches
#   olares-sidecar-config-* ConfigMaps to use idle_timeout: 3600s
#   instead of the hardcoded 10s default.
#
# REQUIREMENTS:
#   - Run on the Olares host as a user with sudo access
#   - kubectl available in PATH
#   - KUBECONFIG configured for the olares user
#
# USAGE:
#   bash install-sidecar-patcher.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "=== Installing olares-sidecar-patcher ==="

# Install patcher script
sudo cp "$SCRIPT_DIR/olares-sidecar-patcher.sh" /usr/local/bin/olares-sidecar-patcher.sh
sudo chmod +x /usr/local/bin/olares-sidecar-patcher.sh

# Install systemd unit
sudo cp "$SCRIPT_DIR/olares-sidecar-patcher.service" /etc/systemd/system/olares-sidecar-patcher.service

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable olares-sidecar-patcher.service
sudo systemctl start olares-sidecar-patcher.service

echo ""
echo "=== Service status ==="
sudo systemctl status olares-sidecar-patcher.service --no-pager | head -15

echo ""
echo "=== Recent logs ==="
sudo journalctl -u olares-sidecar-patcher.service --no-pager -n 5

echo ""
echo "Done. The patcher will keep idle_timeout=3600s on:"
echo "  - olares-sidecar-config-ragflow"
echo "  - olares-sidecar-config-embedder-dev"
echo ""
echo "Monitor with: sudo journalctl -u olares-sidecar-patcher.service -f"
