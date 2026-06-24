#!/usr/bin/env bash
# scripts/dev-setup-gpu.sh — Configure Docker GPU support for local Linux engines.
# Run via: sudo make dev-setup-gpu

set -euo pipefail

readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly INSTALL_PACKAGE="${REPO_ROOT}/scripts/install-package.sh"

# shellcheck source=lib/system.sh
source "${REPO_ROOT}/scripts/lib/system.sh"

readonly WSL_NVIDIA_SMI="/usr/lib/wsl/lib/nvidia-smi"
readonly NVIDIA_CDI_SPEC="/etc/cdi/nvidia.yaml"
readonly CUDA_TEST_IMAGE="nvidia/cuda:12.4.1-base-ubuntu22.04"

require_root() {
    if [[ ${EUID} -ne 0 ]]; then
        echo "Run 'sudo make dev-setup-gpu'." >&2
        exit 1
    fi
}

has_command() {
    command -v "$1" >/dev/null 2>&1
}

is_wsl() {
    grep -qi microsoft /proc/version 2>/dev/null || [[ -e /dev/dxg ]]
}

nvidia_smi_path() {
    if has_command nvidia-smi; then
        command -v nvidia-smi
        return 0
    fi

    if [[ -x "${WSL_NVIDIA_SMI}" ]]; then
        printf '%s\n' "${WSL_NVIDIA_SMI}"
        return 0
    fi

    return 1
}

has_nvidia_gpu() {
    local nvidia_smi

    nvidia_smi="$(nvidia_smi_path 2>/dev/null)" || return 1
    "${nvidia_smi}" -L >/dev/null 2>&1
}

docker_backend() {
    local operating_system

    if ! has_command docker; then
        printf 'missing\n'
        return 0
    fi

    operating_system="$(docker info --format '{{.OperatingSystem}}' 2>/dev/null || true)"
    if [[ -z "${operating_system}" ]]; then
        printf 'unavailable\n'
    elif grep -qi 'Docker Desktop' <<<"${operating_system}"; then
        printf 'docker-desktop\n'
    else
        printf 'local-engine\n'
    fi
}

validate_docker_gpu_support() {
    echo "  gpu         validating Docker GPU access..."
    docker run --rm --gpus all "${CUDA_TEST_IMAGE}" nvidia-smi >/dev/null
}

install_nvidia_container_toolkit() {
    if has_command nvidia-ctk; then
        echo "  gpu         NVIDIA container toolkit already installed ($(nvidia-ctk --version 2>&1 | head -1))"
        return
    fi

    echo "  gpu         installing NVIDIA container toolkit via scripts/install-package.sh..."
    bash "${INSTALL_PACKAGE}" nvidia-container-toolkit
}

restart_docker_service() {
    echo "  gpu         restarting Docker to pick up NVIDIA runtime changes..."

    if has_command systemctl && systemctl status docker >/dev/null 2>&1; then
        systemctl restart docker
        return
    fi

    if has_command service; then
        service docker restart
        return
    fi

    echo "  gpu         unable to restart Docker automatically; restart dockerd manually before retrying validation." >&2
}

configure_local_docker_gpu_runtime() {
    install_nvidia_container_toolkit

    echo "  gpu         configuring Docker runtime and CDI for NVIDIA containers..."
    mkdir -p /etc/cdi
    nvidia-ctk runtime configure --runtime=docker
    nvidia-ctk cdi generate --output="${NVIDIA_CDI_SPEC}"
    restart_docker_service
}

main() {
    local backend

    require_root

    echo "Configuring Docker GPU support..."

    if system_is_macos; then
        echo "  gpu         macOS detected; Docker NVIDIA runtime setup is not applicable." >&2
        echo "  gpu         Use native Ollama for Apple Silicon acceleration." >&2
        exit 1
    fi

    if ! has_nvidia_gpu; then
        echo "  gpu         no NVIDIA GPU detected in this Linux environment; nothing to configure."
        return
    fi

    backend="$(docker_backend)"
    case "${backend}" in
        missing)
            echo "  gpu         Docker is not installed; install Docker first." >&2
            exit 1
            ;;
        unavailable)
            echo "  gpu         Docker is installed but the daemon is not reachable; start Docker first." >&2
            exit 1
            ;;
        docker-desktop)
            if is_wsl; then
                echo "  gpu         WSL + Docker Desktop engine detected; Linux-side NVIDIA toolkit setup is not required here."
                if validate_docker_gpu_support; then
                    echo "  gpu         Docker Desktop GPU passthrough is already working."
                    return
                fi

                echo "  gpu         Docker Desktop GPU passthrough is still failing. Fix it in Docker Desktop and Windows, then retry." >&2
                exit 1
            fi
            ;;
    esac

    if validate_docker_gpu_support; then
        echo "  gpu         Docker GPU support is already working."
        return
    fi

    if is_wsl; then
        echo "  gpu         WSL with a local Docker Engine detected; configuring NVIDIA container support inside this distro."
    else
        echo "  gpu         Native Linux Docker Engine detected; configuring NVIDIA container support on this host."
    fi

    configure_local_docker_gpu_runtime

    if validate_docker_gpu_support; then
        echo "  gpu         Docker GPU validation passed. Ollama can use the NVIDIA GPU."
        return
    fi

    echo "  gpu         Docker GPU validation still failed after configuration. Re-check the host NVIDIA driver and Docker daemon logs." >&2
    exit 1
}

main "$@"