#!/usr/bin/env bash
#
# Install PostgreSQL client + server locally if missing (macOS Homebrew, Linux apt/yum/dnf).
# Idempotent: exits early if `psql` is already on PATH.
#
# Usage:
#   ./scripts/install_postgres_local.sh
#   DRY_RUN=1 ./scripts/install_postgres_local.sh
#
# After install, ensure Postgres listens on the port you use in PUGSY_PG_PORT (default 5433
# in this project). Native packages often use 5432; adjust postgresql.conf or your env.
#
set -Eeuo pipefail

readonly DRY_RUN="${DRY_RUN:-0}"
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m'

log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }
log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_err() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

command_exists() { command -v "$1" >/dev/null 2>&1; }

run() {
  if [[ "$DRY_RUN" == "1" ]]; then
    log_info "[DRY_RUN] $*"
    return 0
  fi
  log_info "Running: $*"
  eval "$@"
}

require_sudo_linux() {
  if [[ "$(id -u)" -eq 0 ]]; then
    return 0
  fi
  if command_exists sudo; then
    return 0
  fi
  log_err "Need root or sudo on Linux to install packages."
  exit 1
}

install_macos() {
  if ! command_exists brew; then
    log_err "Homebrew not found. Install from https://brew.sh then re-run."
    exit 1
  fi
  log_info "Installing PostgreSQL via Homebrew..."
  run "brew install postgresql"
  log_warn "Start the service when needed, e.g.: brew services start postgresql"
  log_warn "Default port is often 5432; this project defaults to PUGSY_PG_PORT=5433 for Docker-style setups."
}

install_linux_debian() {
  require_sudo_linux
  if [[ "$(id -u)" -eq 0 ]]; then
    run "apt-get update && apt-get install -y postgresql postgresql-contrib"
  else
    run "sudo apt-get update && sudo apt-get install -y postgresql postgresql-contrib"
  fi
  log_warn "On Debian/Ubuntu the service is usually postgresql; default port 5432 unless configured otherwise."
}

install_linux_rhel() {
  require_sudo_linux
  if command_exists dnf; then
    if [[ "$(id -u)" -eq 0 ]]; then
      run "dnf install -y postgresql-server postgresql"
    else
      run "sudo dnf install -y postgresql-server postgresql"
    fi
  elif command_exists yum; then
    if [[ "$(id -u)" -eq 0 ]]; then
      run "yum install -y postgresql-server postgresql"
    else
      run "sudo yum install -y postgresql-server postgresql"
    fi
  else
    log_err "Neither dnf nor yum found."
    exit 1
  fi
  log_warn "You may need: sudo postgresql-setup --initdb  && sudo systemctl enable --now postgresql"
}

main() {
  if command_exists psql; then
    log_ok "psql already on PATH ($(command -v psql)); nothing to install."
    exit 0
  fi

  case "$(uname -s)" in
    Darwin)
      install_macos
      ;;
    Linux)
      if [[ -f /etc/debian_version ]] || { [[ -f /etc/os-release ]] && grep -qiE 'debian|ubuntu' /etc/os-release; }; then
        install_linux_debian
      elif [[ -f /etc/redhat-release ]] || { [[ -f /etc/os-release ]] && grep -qiE 'rhel|fedora|centos|rocky|almalinux|amazon' /etc/os-release; }; then
        install_linux_rhel
      elif command_exists apt-get; then
        install_linux_debian
      elif command_exists dnf || command_exists yum; then
        install_linux_rhel
      else
        log_err "Unsupported Linux distribution for automatic install."
        exit 1
      fi
      ;;
    *)
      log_err "Unsupported OS: $(uname -s)"
      exit 1
      ;;
  esac

  if [[ "$DRY_RUN" != "1" ]] && command_exists psql; then
    log_ok "psql installed at $(command -v psql)"
  elif [[ "$DRY_RUN" != "1" ]]; then
    log_warn "Install finished but psql not on PATH yet; open a new shell or check package notes."
  fi
}

main "$@"
