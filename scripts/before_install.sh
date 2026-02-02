set -e

cd /opt/advisor 2>/dev/null && docker-compose down --remove-orphans || true
rm -rf /opt/advisor
mkdir -p /opt/advisor