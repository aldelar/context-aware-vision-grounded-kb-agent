#!/usr/bin/env bash
# Shared host OS and package manager detection for setup scripts.

system_has_command() {
    command -v "$1" >/dev/null 2>&1
}

system_uname_s() {
    if [[ -n "${KB_AGENT_SYSTEM_UNAME_S:-}" ]]; then
        printf '%s\n' "${KB_AGENT_SYSTEM_UNAME_S}"
        return
    fi

    uname -s 2>/dev/null || printf 'unknown\n'
}

system_arch() {
    if [[ -n "${KB_AGENT_SYSTEM_ARCH:-}" ]]; then
        printf '%s\n' "${KB_AGENT_SYSTEM_ARCH}"
        return
    fi

    uname -m 2>/dev/null || printf 'unknown\n'
}

system_os_name() {
    if [[ -n "${KB_AGENT_SYSTEM_OS_NAME:-}" ]]; then
        printf '%s\n' "${KB_AGENT_SYSTEM_OS_NAME}"
        return
    fi

    case "$(system_uname_s)" in
        Darwin)
            printf 'macos\n'
            ;;
        Linux)
            if [[ -r /etc/os-release ]]; then
                # shellcheck disable=SC1091
                source /etc/os-release
                printf '%s\n' "${ID:-linux}"
            else
                printf 'linux\n'
            fi
            ;;
        *)
            printf 'unknown\n'
            ;;
    esac
}

system_os_family() {
    if [[ -n "${KB_AGENT_SYSTEM_OS_FAMILY:-}" ]]; then
        printf '%s\n' "${KB_AGENT_SYSTEM_OS_FAMILY}"
        return
    fi

    case "$(system_uname_s)" in
        Darwin)
            printf 'macos\n'
            ;;
        Linux)
            if [[ -r /etc/os-release ]]; then
                # shellcheck disable=SC1091
                source /etc/os-release
                printf '%s %s\n' "${ID:-linux}" "${ID_LIKE:-}"
            else
                printf 'linux\n'
            fi
            ;;
        *)
            printf 'unknown\n'
            ;;
    esac
}

system_is_macos() {
    [[ "$(system_uname_s)" == "Darwin" || "$(system_os_name)" == "macos" ]]
}

system_is_linux() {
    [[ "$(system_uname_s)" == "Linux" ]]
}

system_package_manager() {
    if [[ -n "${KB_AGENT_SYSTEM_PACKAGE_MANAGER:-}" ]]; then
        printf '%s\n' "${KB_AGENT_SYSTEM_PACKAGE_MANAGER}"
        return
    fi

    if system_is_macos; then
        if system_has_command brew; then
            printf 'brew\n'
        else
            printf 'none\n'
        fi
        return
    fi

    if system_has_command apt-get; then
        printf 'apt\n'
    elif system_has_command pacman; then
        printf 'pacman\n'
    elif system_has_command dnf; then
        printf 'dnf\n'
    elif system_has_command yum; then
        printf 'yum\n'
    elif system_has_command apk; then
        printf 'apk\n'
    else
        printf 'none\n'
    fi
}

system_category() {
    case "$(system_package_manager)" in
        brew)
            printf 'macos-brew\n'
            ;;
        apt)
            printf 'linux-apt\n'
            ;;
        pacman)
            printf 'linux-pacman\n'
            ;;
        dnf|yum|apk)
            printf 'linux-other\n'
            ;;
        *)
            if system_is_macos; then
                printf 'macos-no-brew\n'
            elif system_is_linux; then
                printf 'linux-unknown\n'
            else
                printf 'unsupported\n'
            fi
            ;;
    esac
}

system_sudo() {
    if [[ ${EUID} -eq 0 ]]; then
        "$@"
    else
        sudo "$@"
    fi
}

system_install_package_script() {
    local scripts_dir

    scripts_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
    printf '%s/install-package.sh\n' "${scripts_dir}"
}

system_tool_version() {
    local version_command="$1"

    eval "${version_command}" 2>&1 | head -1
}

system_install_tool() {
    local command_name="$1"
    local package_name="$2"
    local label="$3"
    local version_command="$4"
    local rerun_hint="$5"

    echo "  ${label}          installing via scripts/install-package.sh (${package_name})..."
    bash "$(system_install_package_script)" "${package_name}"

    if ! system_has_command "${command_name}"; then
        echo "  ${label}          install finished, but '${command_name}' is still not on PATH." >&2
        echo "  ${label}          open a new shell or update PATH, then rerun ${rerun_hint}." >&2
        exit 1
    fi

    echo "  ${label}          available ($(system_tool_version "${version_command}"))"
}

system_port_owner_pid() {
    local port="$1"

    if system_has_command ss; then
        ss -ltnp "( sport = :${port} )" 2>/dev/null \
            | awk -F'pid=' 'NR > 1 && NF > 1 { split($2, parts, ","); print parts[1]; exit }' \
            || true
        return
    fi

    if system_has_command lsof; then
        lsof -nP -iTCP:"${port}" -sTCP:LISTEN -t 2>/dev/null | head -n 1 || true
        return
    fi
}

system_print_summary() {
    printf 'OS: %s\n' "$(system_os_name)"
    printf 'Family: %s\n' "$(system_os_family)"
    printf 'Architecture: %s\n' "$(system_arch)"
    printf 'Package manager: %s\n' "$(system_package_manager)"
    printf 'Category: %s\n' "$(system_category)"
}