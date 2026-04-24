#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/../.."

mkdir -p test-recordings

echo "=== Building Docker image with ffmpeg support ==="
docker compose -f docker/desktop-test/docker-compose.yml build desktop-tests-recorded

echo "=== Running desktop tests with video recording ==="
docker compose -f docker/desktop-test/docker-compose.yml up --abort-on-container-exit --exit-code-from desktop-tests-recorded desktop-tests-recorded

echo ""
echo "=== Test artifacts ==="
ls -lh test-recordings/

if [ -f test-recordings/desktop-test.mp4 ]; then
    echo ""
    echo "Video recording: test-recordings/desktop-test.mp4"
    echo "Play with: ffplay test-recordings/desktop-test.mp4"
fi
