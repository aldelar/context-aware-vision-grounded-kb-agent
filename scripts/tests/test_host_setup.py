from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest


@pytest.fixture
def project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def run_script(
    project_root: Path,
    args: list[str],
    env_overrides: dict[str, str],
) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.update(env_overrides)
    return subprocess.run(
        ["bash", *args],
        cwd=project_root,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


@pytest.mark.parametrize(
    ("uname_s", "os_name", "os_family", "package_manager", "category"),
    [
        ("Darwin", "macos", "macos", "brew", "macos-brew"),
        ("Linux", "ubuntu", "ubuntu debian", "apt", "linux-apt"),
        ("Linux", "arch", "arch", "pacman", "linux-pacman"),
        ("Linux", "fedora", "fedora", "dnf", "linux-other"),
    ],
)
def test_system_check_reports_host_category(
    project_root: Path,
    uname_s: str,
    os_name: str,
    os_family: str,
    package_manager: str,
    category: str,
) -> None:
    completed = run_script(
        project_root,
        ["scripts/system-check.sh"],
        {
            "KB_AGENT_SYSTEM_UNAME_S": uname_s,
            "KB_AGENT_SYSTEM_OS_NAME": os_name,
            "KB_AGENT_SYSTEM_OS_FAMILY": os_family,
            "KB_AGENT_SYSTEM_PACKAGE_MANAGER": package_manager,
            "KB_AGENT_SYSTEM_ARCH": "arm64",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert f"Category: {category}" in completed.stdout
    assert "Ollama" not in completed.stdout


def test_install_package_dry_run_uses_brew_commands(project_root: Path) -> None:
    completed = run_script(
        project_root,
        [
            "scripts/install-package.sh",
            "--dry-run",
            "--force",
            "azure-cli",
            "azd",
            "uv",
            "node",
            "azure-functions-core-tools",
        ],
        {
            "KB_AGENT_SYSTEM_UNAME_S": "Darwin",
            "KB_AGENT_SYSTEM_OS_NAME": "macos",
            "KB_AGENT_SYSTEM_OS_FAMILY": "macos",
            "KB_AGENT_SYSTEM_PACKAGE_MANAGER": "brew",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert "+ brew install azure-cli" in completed.stdout
    assert "+ brew tap azure/azd" in completed.stdout
    assert "+ brew install azure/azd/azd" in completed.stdout
    assert "+ brew install uv" in completed.stdout
    assert "+ brew install node" in completed.stdout
    assert "+ brew tap azure/functions" in completed.stdout
    assert "+ brew install azure-functions-core-tools@4" in completed.stdout
    assert "apt-get" not in completed.stdout
    assert "pacman" not in completed.stdout


def test_install_package_dry_run_uses_apt_commands(project_root: Path) -> None:
    completed = run_script(
        project_root,
        [
            "scripts/install-package.sh",
            "--dry-run",
            "--force",
            "azure-cli",
            "curl",
            "gpg",
        ],
        {
            "KB_AGENT_SYSTEM_UNAME_S": "Linux",
            "KB_AGENT_SYSTEM_OS_NAME": "ubuntu",
            "KB_AGENT_SYSTEM_OS_FAMILY": "ubuntu debian",
            "KB_AGENT_SYSTEM_PACKAGE_MANAGER": "apt",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert "https://aka.ms/InstallAzureCLIDeb" in completed.stdout
    assert "apt-get update" in completed.stdout
    assert "apt-get install -y curl" in completed.stdout
    assert "apt-get install -y gpg" in completed.stdout
    assert "brew install" not in completed.stdout
    assert "pacman" not in completed.stdout


def test_install_package_dry_run_uses_pacman_commands(project_root: Path) -> None:
    completed = run_script(
        project_root,
        [
            "scripts/install-package.sh",
            "--dry-run",
            "--force",
            "azure-cli",
            "uv",
            "node",
            "curl",
        ],
        {
            "KB_AGENT_SYSTEM_UNAME_S": "Linux",
            "KB_AGENT_SYSTEM_OS_NAME": "arch",
            "KB_AGENT_SYSTEM_OS_FAMILY": "arch",
            "KB_AGENT_SYSTEM_PACKAGE_MANAGER": "pacman",
        },
    )

    assert completed.returncode == 0, completed.stderr
    assert "pacman -S --needed --noconfirm azure-cli" in completed.stdout
    assert "pacman -S --needed --noconfirm uv" in completed.stdout
    assert "pacman -S --needed --noconfirm nodejs npm" in completed.stdout
    assert "pacman -S --needed --noconfirm curl" in completed.stdout
    assert "brew install" not in completed.stdout
    assert "apt-get" not in completed.stdout


def test_install_package_rejects_nvidia_toolkit_on_macos(project_root: Path) -> None:
    completed = run_script(
        project_root,
        [
            "scripts/install-package.sh",
            "--dry-run",
            "--force",
            "nvidia-container-toolkit",
        ],
        {
            "KB_AGENT_SYSTEM_UNAME_S": "Darwin",
            "KB_AGENT_SYSTEM_OS_NAME": "macos",
            "KB_AGENT_SYSTEM_OS_FAMILY": "macos",
            "KB_AGENT_SYSTEM_PACKAGE_MANAGER": "brew",
        },
    )

    assert completed.returncode == 1
    assert "Linux-only" in completed.stderr