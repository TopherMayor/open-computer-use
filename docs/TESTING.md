# Testing Guide

## Test Tiers

### Tier 1: Unit / Fake Backend

Fast, no display required. Uses the `fake` backend which returns deterministic responses.

```bash
GSD_CU_BACKEND=fake python3 -m pytest tests/ -v
```

These tests cover MCP contract, tool schemas, handler logic, safety controls, audit logging, vision utilities, element matching, and recording infrastructure.

### Tier 2: Docker / X11

Containerized desktop tests using Xvfb, a fixture GTK app, and the Linux X11 backend.

```bash
# Standard tests (no recording)
docker compose -f docker/desktop-test/docker-compose.yml up --abort-on-container-exit --exit-code-from desktop-tests desktop-tests

# With video recording
./docker/desktop-test/run-and-record.sh
```

The recorded run produces `test-recordings/desktop-test.mp4` as a verification artifact.

### Tier 3: Real Desktop

Manual tests against the macOS or live Linux backend. Not automated. Requires real display, permissions, and desktop apps.

## Running Tests

### All local tests

```bash
GSD_CU_BACKEND=fake python3 -m pytest tests/ -v
```

### Specific test file

```bash
GSD_CU_BACKEND=fake python3 -m pytest tests/test_mcp_contract.py -v
```

### Docker contract tests only

```bash
docker compose -f docker/desktop-test/docker-compose.yml run --rm contract-tests
```

### Docker desktop smoke tests with video

```bash
./docker/desktop-test/run-and-record.sh
```

## Test Markers

| Marker | Meaning |
|--------|---------|
| `@pytest.mark.requires_fake` | Test only works with the fake backend, skipped with real backends |

Tests marked `requires_fake` are automatically skipped when running against a real display backend.

## Test Files

| File | What it tests |
|------|--------------|
| `test_mcp_contract.py` | Server startup, tool listing, schema validation, error handling |
| `test_desktop_smoke.py` | GUI smoke tests (Docker X11 only) |
| `test_failure_modes.py` | Backend unavailable, display errors, stale elements |
| `test_safety.py` | Action budgets, rate limiting, emergency stop |
| `test_audit.py` | JSONL audit log format and content |
| `test_clipboard.py` | Clipboard preservation around text input |
| `test_vision.py` | OCR, screenshot annotation, diff, element descriptions |
| `test_visual_click.py` | Element matching, scoring, and visual click flow |
| `test_linux_parity.py` | Backend interface consistency |
| `test_coverage_gaps.py` | Edge cases in tool handlers |
| `test_unit_coverage.py` | Unit tests for individual components |
| `test_recording.py` | Docker recording infrastructure validation |

## Video Recording Artifacts

When running `./docker/desktop-test/run-and-record.sh`:

- `test-recordings/desktop-test.mp4` — video of the entire test run
- `test-recordings/*.png` — failure screenshots (captured automatically by `conftest.py`)

Video files are gitignored (`test-recordings/*.mp4`). The `test-recordings/` directory is kept in the repo via `.gitkeep`.

## Interpreting Results

- **All green**: Tests pass, implementation matches contract
- **`requires_fake` skipped**: You're running against a real backend; these tests are expected to skip
- **Docker test failure**: Check `test-recordings/` for failure screenshots. Run `docker compose -f docker/desktop-test/docker-compose.yml up novnc-debug` and open `http://localhost:6080` to visually debug
- **Import errors**: Ensure `PYTHONPATH=.` is set or run from the repo root with `python3 -m pytest`
