set -e

cd /opt/advisor

if [ ! -f ".env" ]; then
    echo "Error: .env file not found"
    exit 1
fi

docker-compose build
docker-compose up -d

for i in $(seq 1 30); do
    if curl -sf http://localhost:8000/health > /dev/null; then
        echo "API started successfully"
        exit 0
    fi
    sleep 2
done

echo "API failed to start"
docker-compose logs api
exit 1