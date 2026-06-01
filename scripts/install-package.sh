#!/usr/bin/env bash
# scripts/install-package.sh — Install logical project packages through the host package manager.

set -euo pipefail

readonly SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/system.sh
source "${SCRIPT_DIR}/lib/system.sh"

DRY_RUN=0
FORCE=0

usage() {
    cat >&2 <<'EOF'
Usage: scripts/install-package.sh [--dry-run] [--force] <package> [package...]

Logical packages:
  azure-cli
  azd
  uv
  azure-functions-core-tools
  curl
  gpg
  node
  ollama
  nvidia-container-toolkit
EOF
}

quote_command() {
    local first=1
    local arg

    for arg in "$@"; do
        if [[ ${first} -eq 0 ]]; then
            printf ' '
        fi
        printf '%q' "${arg}"
        first=0
    done
    printf '\n'
}

run_cmd() {
    if [[ ${DRY_RUN} -eq 1 ]]; then
        printf '+ '
        quote_command "$@"
        return
    fi

    "$@"
}

run_sudo_cmd() {
    if [[ ${DRY_RUN} -eq 1 ]]; then
        if [[ ${EUID} -eq 0 ]]; then
            printf '+ '
            quote_command "$@"
        else
            printf '+ '
            quote_command sudo "$@"
        fi
        return
    fi

    system_sudo "$@"
}

package_command() {
    case "$1" in
        azure-cli) printf 'az\n' ;;
        azd) printf 'azd\n' ;;
        uv) printf 'uv\n' ;;
        azure-functions-core-tools) printf 'func\n' ;;
        curl) printf 'curl\n' ;;
        gpg) printf 'gpg\n' ;;
        node) printf 'npm\n' ;;
        ollama) printf 'ollama\n' ;;
        nvidia-container-toolkit) printf 'nvidia-ctk\n' ;;
        *) return 1 ;;
    esac
}

ensure_supported_package() {
    if ! package_command "$1" >/dev/null; then
        echo "Unsupported logical package: $1" >&2
        usage
        exit 2
    fi
}

download_and_run_user_script() {
    local url="$1"
    local label="$2"
    local tmp_file

    if [[ ${DRY_RUN} -eq 1 ]]; then
        run_cmd curl -fsSL "${url}" -o "<tmp-${label}.sh>"
        run_cmd bash "<tmp-${label}.sh>"
        return
    fi

    tmp_file="$(mktemp)"
    cleanup_download() {
        rm -f "${tmp_file}"
    }
    trap cleanup_download RETURN

    curl -fsSL "${url}" -o "${tmp_file}"
    bash "${tmp_file}"
}

download_and_run_sudo_script() {
    local url="$1"
    local label="$2"
    local tmp_file

    if [[ ${DRY_RUN} -eq 1 ]]; then
        run_cmd curl -fsSL "${url}" -o "<tmp-${label}.sh>"
        run_sudo_cmd bash "<tmp-${label}.sh>"
        return
    fi

    tmp_file="$(mktemp)"
    cleanup_download() {
        rm -f "${tmp_file}"
    }
    trap cleanup_download RETURN

    curl -fsSL "${url}" -o "${tmp_file}"
    system_sudo bash "${tmp_file}"
}

install_with_npm_global() {
    local package_name="$1"

    if ! system_has_command npm; then
        install_package node
    fi

    run_cmd npm install -g "${package_name}" --unsafe-perm true
}

install_apt_packages() {
    run_sudo_cmd apt-get update
    run_sudo_cmd apt-get install -y "$@"
}

install_pacman_packages() {
    run_sudo_cmd pacman -S --needed --noconfirm "$@"
}

install_dnf_packages() {
    run_sudo_cmd dnf install -y "$@"
}

install_yum_packages() {
    run_sudo_cmd yum install -y "$@"
}

install_apk_packages() {
    run_sudo_cmd apk add --no-cache "$@"
}

install_apt_nvidia_container_toolkit() {
    install_apt_packages curl gpg

    if [[ ${DRY_RUN} -eq 1 ]]; then
        run_cmd curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o "<tmp-nvidia-gpgkey>"
        run_sudo_cmd gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg "<tmp-nvidia-gpgkey>"
        run_cmd curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list -o "<tmp-nvidia-container-toolkit.list>"
        run_sudo_cmd install -m 0644 "<tmp-nvidia-container-toolkit.list>" /etc/apt/sources.list.d/nvidia-container-toolkit.list
        run_sudo_cmd apt-get update
        run_sudo_cmd apt-get install -y nvidia-container-toolkit
        return
    fi

    local key_file
    local list_file
    key_file="$(mktemp)"
    list_file="$(mktemp)"
    cleanup_nvidia_repo_files() {
        rm -f "${key_file}" "${list_file}"
    }
    trap cleanup_nvidia_repo_files RETURN

    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey -o "${key_file}"
    system_sudo gpg --dearmor --yes -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg "${key_file}"
    curl -fsSL https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
        | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#' \
        > "${list_file}"
    system_sudo install -m 0644 "${list_file}" /etc/apt/sources.list.d/nvidia-container-toolkit.list
    system_sudo apt-get update
    system_sudo apt-get install -y nvidia-container-toolkit
}

unsupported_package() {
    local package_name="$1"
    local manager="$2"
    local note="${3:-}"

    echo "Cannot install ${package_name} automatically with package manager '${manager}'." >&2
    if [[ -n "${note}" ]]; then
        echo "${note}" >&2
    fi
    return 1
}

install_with_brew() {
    local package_name="$1"

    case "${package_name}" in
        azure-cli)
            run_cmd brew install azure-cli
            ;;
        azd)
            run_cmd brew tap azure/azd
            run_cmd brew install azure/azd/azd
            ;;
        uv)
            run_cmd brew install uv
            ;;
        azure-functions-core-tools)
            run_cmd brew tap azure/functions
            run_cmd brew install azure-functions-core-tools@4
            ;;
        curl)
            run_cmd brew install curl
            ;;
        gpg)
            run_cmd brew install gnupg
            ;;
        node)
            run_cmd brew install node
            ;;
        ollama)
            run_cmd brew install ollama
            ;;
        nvidia-container-toolkit)
            unsupported_package "${package_name}" brew "NVIDIA container runtime setup is Linux-only; skip dev-setup-gpu on macOS."
            ;;
    esac
}

install_with_apt() {
    local package_name="$1"

    case "${package_name}" in
        azure-cli)
            download_and_run_sudo_script https://aka.ms/InstallAzureCLIDeb azure-cli
            ;;
        azd)
            download_and_run_user_script https://aka.ms/install-azd.sh azd
            ;;
        uv)
            download_and_run_user_script https://astral.sh/uv/install.sh uv
            ;;
        azure-functions-core-tools)
            install_with_npm_global azure-functions-core-tools@4
            ;;
        curl)
            install_apt_packages curl
            ;;
        gpg)
            install_apt_packages gpg
            ;;
        node)
            install_apt_packages nodejs npm
            ;;
        ollama)
            download_and_run_user_script https://ollama.com/install.sh ollama
            ;;
        nvidia-container-toolkit)
            install_apt_nvidia_container_toolkit
            ;;
    esac
}

install_with_pacman() {
    local package_name="$1"

    case "${package_name}" in
        azure-cli)
            install_pacman_packages azure-cli
            ;;
        azd)
            download_and_run_user_script https://aka.ms/install-azd.sh azd
            ;;
        uv)
            install_pacman_packages uv
            ;;
        azure-functions-core-tools)
            install_with_npm_global azure-functions-core-tools@4
            ;;
        curl)
            install_pacman_packages curl
            ;;
        gpg)
            install_pacman_packages gnupg
            ;;
        node)
            install_pacman_packages nodejs npm
            ;;
        ollama)
            install_pacman_packages ollama
            ;;
        nvidia-container-toolkit)
            install_pacman_packages nvidia-container-toolkit
            ;;
    esac
}

install_with_linux_other() {
    local package_name="$1"
    local manager="$2"

    case "${manager}" in
        dnf)
            case "${package_name}" in
                azd) download_and_run_user_script https://aka.ms/install-azd.sh azd ;;
                uv) download_and_run_user_script https://astral.sh/uv/install.sh uv ;;
                azure-functions-core-tools) install_with_npm_global azure-functions-core-tools@4 ;;
                curl) install_dnf_packages curl ;;
                gpg) install_dnf_packages gnupg2 ;;
                node) install_dnf_packages nodejs npm ;;
                ollama) download_and_run_user_script https://ollama.com/install.sh ollama ;;
                *) unsupported_package "${package_name}" "${manager}" ;;
            esac
            ;;
        yum)
            case "${package_name}" in
                azd) download_and_run_user_script https://aka.ms/install-azd.sh azd ;;
                uv) download_and_run_user_script https://astral.sh/uv/install.sh uv ;;
                azure-functions-core-tools) install_with_npm_global azure-functions-core-tools@4 ;;
                curl) install_yum_packages curl ;;
                gpg) install_yum_packages gnupg2 ;;
                node) install_yum_packages nodejs npm ;;
                ollama) download_and_run_user_script https://ollama.com/install.sh ollama ;;
                *) unsupported_package "${package_name}" "${manager}" ;;
            esac
            ;;
        apk)
            case "${package_name}" in
                azd) download_and_run_user_script https://aka.ms/install-azd.sh azd ;;
                uv) download_and_run_user_script https://astral.sh/uv/install.sh uv ;;
                azure-functions-core-tools) install_with_npm_global azure-functions-core-tools@4 ;;
                curl) install_apk_packages curl ;;
                gpg) install_apk_packages gnupg ;;
                node) install_apk_packages nodejs npm ;;
                ollama) download_and_run_user_script https://ollama.com/install.sh ollama ;;
                *) unsupported_package "${package_name}" "${manager}" ;;
            esac
            ;;
        *)
            unsupported_package "${package_name}" "${manager}"
            ;;
    esac
}

install_package() {
    local package_name="$1"
    local command_name
    local manager

    ensure_supported_package "${package_name}"
    command_name="$(package_command "${package_name}")"

    if [[ ${FORCE} -eq 0 ]] && system_has_command "${command_name}"; then
        echo "  ${package_name} already installed ($(command -v "${command_name}"))"
        return
    fi

    manager="$(system_package_manager)"
    case "${manager}" in
        brew)
            install_with_brew "${package_name}"
            ;;
        apt)
            install_with_apt "${package_name}"
            ;;
        pacman)
            install_with_pacman "${package_name}"
            ;;
        dnf|yum|apk)
            install_with_linux_other "${package_name}" "${manager}"
            ;;
        none)
            unsupported_package "${package_name}" "${manager}" "Detected category: $(system_category). Install a supported package manager first."
            ;;
        *)
            unsupported_package "${package_name}" "${manager}" "Detected category: $(system_category)."
            ;;
    esac
}

parse_args() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --dry-run)
                DRY_RUN=1
                shift
                ;;
            --force)
                FORCE=1
                shift
                ;;
            -h|--help)
                usage
                exit 0
                ;;
            --)
                shift
                break
                ;;
            -* )
                echo "Unknown option: $1" >&2
                usage
                exit 2
                ;;
            *)
                break
                ;;
        esac
    done

    if [[ $# -eq 0 ]]; then
        usage
        exit 2
    fi

    for package_name in "$@"; do
        install_package "${package_name}"
    done
}

parse_args "$@"