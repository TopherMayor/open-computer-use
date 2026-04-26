# Docker Sandbox Test Plan

## Goal
Build and run the gsd-computer-use test suite inside the Docker sandbox environment on grizzley (ARM64). Verify that all tests pass in an isolated X11 + ATSPI environment.

## Context
- Working directory: /home/bear/projects/gsd-computer-use
- Docker test environment exists at docker/desktop-test/
- grizzley is ARM64 (aarch64) — the Dockerfile uses ubuntu:24.04 which supports ARM64
- Docker and docker compose are available on grizzley

## Phase 1: Build the Docker Image

```bash
cd /home/bear/projects/gsd-computer-use
docker compose -f docker/desktop-test/docker-compose.yml build --no-cache 2>&1 | tail -30
```

If the build fails, fix the Dockerfile. Common issues on ARM64:
- Package names may differ
- python3-gi and gir1.2-atspi-2.0 should be available on arm64 Ubuntu 24.04

## Phase 2: Run Contract Tests (fake backend)

These should always pass — they use the fake backend with no display needed:

```bash
cd /home/bear/projects/gsd-computer-use
docker compose -f docker/desktop-test/docker-compose.yml run --rm contract-tests 2>&1
```

## Phase 3: Run Desktop Smoke Tests (linux-x11 backend with Xvfb)

This starts Xvfb, openbox, a GTK test app, and runs tests against the real linux-x11 backend:

```bash
cd /home/bear/projects/gsd-computer-use
docker compose -f docker/desktop-test/docker-compose.yml run --rm desktop-tests 2>&1
```

This is the critical test — it verifies that:
- Xvfb provides a virtual display
- ATSPI accessibility works for the GTK test app
- wmctrl can list windows
- xdotool can activate windows
- Screenshots work via pyautogui/mss
- The full MCP tool chain works end-to-end

## Phase 4: Run Parity Tests Inside Container

Run the 22 parity tests inside the container to verify ATSPI mocking matches real ATSPI behavior:

```bash
cd /home/bear/projects/gsd-computer-use
docker compose -f docker/desktop-test/docker-compose.yml run --rm --entrypoint bash desktop-tests -c "
  cd /repo &&
  python3 -m pytest tests/test_linux_parity.py -v 2>&1
"
```

## Phase 5: Run All Tests Together

```bash
cd /home/bear/projects/gsd-computer-use
docker compose -f docker/desktop-test/docker-compose.yml run --rm --entrypoint bash desktop-tests -c "
  Xvfb :99 -screen 0 1280x800x24 &
  openbox &
  dbus-launch --exit-with-session python3 tests/fixtures/desktop_app.py &
  sleep 2
  DISPLAY=:99 GSD_CU_BACKEND=linux-x11 python3 -m pytest tests/ -v --tb=short 2>&1
"
```

## Phase 6: Fix Any Failures

If any tests fail:
1. Analyze the error output
2. Fix the test or the code as appropriate
3. Re-run until all tests pass
4. Commit fixes (DO NOT push to remote)

If the Dockerfile needs changes (e.g. missing ARM64 packages), fix it and rebuild.

## Phase 7: Report Results

Report:
- Total tests run, passed, failed, skipped
- Any issues found and fixed
- Whether the ARM64 Docker image builds cleanly
- Whether ATSPI accessibility works in the container

## Constraints
- DO NOT push to remote
- If the Dockerfile needs modification, commit the change
- If tests reveal code bugs, fix and commit
- Keep the existing docker-compose.yml structure
