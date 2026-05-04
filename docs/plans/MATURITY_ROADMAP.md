# Production Readiness Roadmap

Full background: `docs/maturity-roadmap.md`

## Completed

- [x] Milestone 1: Architecture split (server/backends/tools/types)
- [x] Milestone 2: Docker container test lab (Xvfb + ATSPI + noVNC)
- [x] Fake backend with full tool coverage
- [x] Linux X11 backend with AT-SPI2 integration
- [x] 152 tests (143 pass + 9 skip locally, 133 pass + 19 skip in Docker)
- [x] Docker smoke tests validate real X11 + ATSPI on ARM64
- [x] Vision module (OCR, annotate, diff) with graceful degradation
- [x] Type hints on all public methods
- [x] Consistent backend signatures matching ABC

## Remaining for Production

### Real-Desktop Testing

- [ ] Test against real desktop apps (browser, text editor, file manager)
- [ ] Multi-window and multi-monitor scenarios
- [ ] Verify coordinate accuracy on Retina/HiDPI displays
- [ ] App lifecycle edge cases (app crash, slow launch, permission denial)
- [ ] Accessibility tree quality on real GTK/Qt/Electron apps

### CI Pipeline

- [ ] GitHub Actions workflow: fake-backend tests on every PR
- [ ] Weekly/nightly Docker desktop test run
- [ ] Code coverage reporting (target: >80% on server.py + backends)
- [ ] Lint + typecheck gate (ruff, mypy)
- [ ] Automated release tagging on merge to main

### npm Package Integration

- [ ] Publish as npm package with bundled Python server
- [ ] MCP client configuration template (Claude Desktop, Cursor, etc.)
- [ ] `npx open-computer-use --self-test` smoke check
- [ ] Auto-detect Python path or bundle via PyInstaller
- [ ] Document install steps for macOS + Linux

### Safety and Observability

- [ ] App allowlist/denylist configuration
- [ ] Per-action confirmation policy (optional)
- [ ] Structured JSONL audit log
- [ ] Screenshot before/after capture on failure
- [ ] Emergency stop signal (file or signal)
- [ ] Rate limiting and action budgets

### Hardening

- [ ] macOS permission diagnostics (`doctor` command)
- [ ] Clipboard preservation guarantees
- [ ] Stable element paths (not just numeric indexes)
- [ ] Multi-monitor coordinate model
- [ ] Browser/WebView accessibility extraction

## Target Platforms

| Platform | Backend | Status |
|----------|---------|--------|
| macOS (ARM64) | AppKit/Quartz | Implemented, needs real-app testing |
| Linux (ARM64) | X11 + AT-SPI2 | Tested in Docker |
| Linux (x86_64) | X11 + AT-SPI2 | Not yet tested |
| Windows | Not started | Low priority |

## Success Criteria

Production-ready when:

1. CI passes on every PR with fake + Docker backends
2. Real-desktop smoke tests pass on macOS and Linux
3. npm package installs and runs `--self-test` cleanly
4. Safety controls (allowlist, audit log) are configurable
5. Documentation covers install, configure, and troubleshoot
