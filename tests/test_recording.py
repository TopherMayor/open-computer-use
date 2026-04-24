from __future__ import annotations

import os
import stat

import pytest

pytestmark = pytest.mark.requires_fake


REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
COMPOSE_PATH = os.path.join(REPO_ROOT, "docker", "desktop-test", "docker-compose.yml")
SCRIPT_PATH = os.path.join(REPO_ROOT, "docker", "desktop-test", "run-and-record.sh")
RECORDINGS_DIR = os.path.join(REPO_ROOT, "test-recordings")


def test_compose_service_exists():
    import yaml

    with open(COMPOSE_PATH) as f:
        config = yaml.safe_load(f)
    assert "desktop-tests-recorded" in config["services"]


def test_compose_has_ffmpeg_command():
    import yaml

    with open(COMPOSE_PATH) as f:
        config = yaml.safe_load(f)
    cmd = config["services"]["desktop-tests-recorded"]["command"]
    assert "ffmpeg" in cmd
    assert "x11grab" in cmd
    assert "desktop-test.mp4" in cmd


def test_compose_has_volume_mount():
    import yaml

    with open(COMPOSE_PATH) as f:
        config = yaml.safe_load(f)
    volumes = config["services"]["desktop-tests-recorded"].get("volumes", [])
    assert any("test-recordings" in v for v in volumes)


def test_run_and_record_script_exists():
    assert os.path.isfile(SCRIPT_PATH)


def test_run_and_record_script_executable():
    st = os.stat(SCRIPT_PATH)
    assert st.st_mode & stat.S_IXUSR, "run-and-record.sh is not executable by owner"


def test_recordings_directory_exists():
    os.makedirs(RECORDINGS_DIR, exist_ok=True)
    assert os.path.isdir(RECORDINGS_DIR)
