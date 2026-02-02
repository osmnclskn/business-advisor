set -e

for i in $(seq 1 10); do
    if curl -sf http://localhost:8000/health > /dev/null; then
        echo "Service is healthy"
        exit 0
    fi
    sleep 3
done

echo "Service validation failed"
exit 1