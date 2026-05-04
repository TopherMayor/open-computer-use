"""Tests for packaging, version propagation, and entrypoint registration."""

from __future__ import annotations

import importlib
import importlib.metadata
import subprocess
import sys

import pytest


class TestVersionPropagation:
    def test_version_exists_and_is_string(self):
        from open_computer_use import __version__

        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_is_semver_like(self):
        from open_computer_use import __version__

        parts = __version__.split(".")
        assert len(parts) >= 2, f"Version '{__version__}' should have at least major.minor"
        for part in parts:
            assert part.isdigit(), f"Version part '{part}' should be numeric"

    def test_server_version_matches_init(self):
        from open_computer_use import SERVER_VERSION, __version__

        assert __version__ == SERVER_VERSION

    def test_server_initialize_uses_version(self):
        from open_computer_use.server import handle_request

        resp = handle_request({"jsonrpc": "2.0", "id": 1, "method": "initialize"})
        assert resp is not None
        from open_computer_use import __version__

        assert resp["result"]["serverInfo"]["version"] == __version__


class TestPackageMetadata:
    def test_package_importable(self):
        import open_computer_use

        assert hasattr(open_computer_use, "__version__")
        assert hasattr(open_computer_use, "SERVER_NAME")
        assert hasattr(open_computer_use, "SERVER_VERSION")

    def test_server_main_callable(self):
        from open_computer_use.server import main

        assert callable(main)

    def test_pyproject_toml_exists(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        pyproject = project_root / "pyproject.toml"
        assert pyproject.exists(), "pyproject.toml must exist at project root"

    def test_pyproject_has_entrypoint(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        content = (project_root / "pyproject.toml").read_text()
        assert "open-computer-use-mcp" in content, "pyproject.toml must declare open-computer-use-mcp entrypoint"
        assert "open_computer_use.server:main" in content, "Entrypoint must point to open_computer_use.server:main"

    def test_pyproject_has_dynamic_version(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        content = (project_root / "pyproject.toml").read_text()
        assert 'dynamic = ["version"]' in content, "pyproject.toml must declare dynamic version"
        assert "open_computer_use.__version__" in content, "pyproject.toml must read version from open_computer_use.__version__"

    def test_pyproject_has_setuptools_packages(self):
        from pathlib import Path

        project_root = Path(__file__).resolve().parent.parent
        content = (project_root / "pyproject.toml").read_text()
        assert "[tool.setuptools.packages.find]" in content
        assert '"open_computer_use*"' in content


class TestEntrypointCallable:
    def test_self_test_flag_works(self):
        result = subprocess.run(
            [sys.executable, "-m", "open_computer_use.server", "--self-test"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"self-test failed: {result.stderr}"

    def test_list_tools_flag_works(self):
        result = subprocess.run(
            [sys.executable, "-m", "open_computer_use.server", "--list-tools"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0, f"list-tools failed: {result.stderr}"
        assert "tools" in result.stdout

    def test_version_flag(self):
        result = subprocess.run(
            [sys.executable, "-m", "open_computer_use.server", "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert result.returncode == 0
        from open_computer_use import __version__

        assert __version__ in result.stdout.strip()


class TestInstallEditable:
    def test_editable_install_and_entrypoint(self):
        try:
            metadata = importlib.metadata.metadata("open-computer-use")
        except importlib.metadata.PackageNotFoundError:
            pytest.skip("open-computer-use not installed (run: pip install -e .)")

        assert metadata["Name"] == "open-computer-use"

        from open_computer_use import __version__

        installed_version = metadata["Version"]
        assert installed_version == __version__, (
            f"Installed version {installed_version} != __version__ {__version__}"
        )

        eps = importlib.metadata.entry_points()
        ocu_eps = eps.select(group="console_scripts", name="open-computer-use-mcp")
        ocu_eps = list(ocu_eps)
        assert len(ocu_eps) >= 1, "open-computer-use-mcp console_scripts entrypoint not found"

        entrypoint_value = str(ocu_eps[0].value)
        assert "open_computer_use.server:main" in entrypoint_value
