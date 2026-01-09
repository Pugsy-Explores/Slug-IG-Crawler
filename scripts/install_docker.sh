#!/usr/bin/env bash
#
# Production-grade, idempotent installation script for Docker and Docker Compose v2
# Supports: macOS (Intel/Apple Silicon), Linux (Ubuntu 20.04+, Debian 11+, Amazon Linux 2, RHEL/CentOS 8+)
#
# Usage:
#   DRY_RUN=1 ./scripts/install_docker.sh  # Dry-run mode
#   ./scripts/install_docker.sh            # Normal installation
#

set -Eeuo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Configuration
readonly DRY_RUN="${DRY_RUN:-0}"
readonly SCRIPT_NAME="$(basename "$0")"

# Global state
OS_TYPE=""
OS_ARCH=""
DISTRO=""
DISTRO_VERSION=""
NEEDS_SUDO=false

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $(date '+%Y-%m-%d %H:%M:%S') - $*" >&2
}

log_dry_run() {
    if [ "$DRY_RUN" = "1" ]; then
        echo -e "${YELLOW}[DRY-RUN]${NC} $*"
    fi
}

# Error handler
error_handler() {
    local line_number=$1
    log_error "Script failed at line $line_number"
    exit 1
}

trap 'error_handler $LINENO' ERR

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check if running as root
is_root() {
    [ "$(id -u)" -eq 0 ]
}

# Check sudo availability
check_sudo() {
    if ! is_root && ! sudo -n true 2>/dev/null; then
        if [ "$DRY_RUN" = "1" ]; then
            log_dry_run "Would check sudo access"
            return 0
        fi
        log_error "This script requires sudo privileges. Please run with sudo or ensure passwordless sudo is configured."
        exit 1
    fi
    NEEDS_SUDO=true
}

# Execute command with optional sudo
run_cmd() {
    local cmd="$*"
    log_dry_run "Would execute: $cmd"
    
    if [ "$DRY_RUN" = "1" ]; then
        return 0
    fi
    
    if [ "$NEEDS_SUDO" = "true" ] && ! is_root; then
        sudo $cmd
    else
        $cmd
    fi
}

# Detect OS and architecture
detect_os() {
    log_info "Detecting operating system..."
    
    case "$(uname -s)" in
        Darwin)
            OS_TYPE="macos"
            case "$(uname -m)" in
                x86_64)
                    OS_ARCH="x86_64"
                    ;;
                arm64)
                    OS_ARCH="arm64"
                    ;;
                *)
                    log_error "Unsupported macOS architecture: $(uname -m)"
                    exit 1
                    ;;
            esac
            log_info "Detected: macOS ($OS_ARCH)"
            ;;
        Linux)
            OS_TYPE="linux"
            case "$(uname -m)" in
                x86_64)
                    OS_ARCH="x86_64"
                    ;;
                aarch64|arm64)
                    OS_ARCH="aarch64"
                    ;;
                *)
                    log_error "Unsupported Linux architecture: $(uname -m)"
                    exit 1
                    ;;
            esac            
            detect_linux_distro
            log_info "Detected: Linux - $DISTRO $DISTRO_VERSION ($OS_ARCH)"
            ;;
        *)
            log_error "Unsupported operating system: $(uname -s)"
            exit 1
            ;;
    esac
}

# Detect Linux distribution
detect_linux_distro() {
    if [ -f /etc/os-release ]; then
        # shellcheck source=/dev/null
        . /etc/os-release
        DISTRO="$ID"
        DISTRO_VERSION="$VERSION_ID"
        
        # Normalize distribution names
        case "$ID" in
            ubuntu)
                # Verify Ubuntu 20.04+
                if [ "$(echo "$VERSION_ID" | cut -d. -f1)" -lt 20 ]; then
                    log_error "Ubuntu 20.04+ required. Found: $VERSION_ID"
                    exit 1
                fi
                ;;
            debian)
                # Verify Debian 11+
                if [ "$(echo "$VERSION_ID" | cut -d. -f1)" -lt 11 ]; then
                    log_error "Debian 11+ required. Found: $VERSION_ID"
                    exit 1
                fi
                ;;
            rhel|centos)
                # RHEL/CentOS 8+
                if [ "$(echo "$VERSION_ID" | cut -d. -f1)" -lt 8 ]; then
                    log_error "RHEL/CentOS 8+ required. Found: $VERSION_ID"
                    exit 1
                fi
                ;;
            amzn)
                # Amazon Linux 2
                DISTRO="amazonlinux"
                if [ "$VERSION_ID" != "2" ]; then
                    log_warn "Amazon Linux 2 recommended. Found: $VERSION_ID"
                fi
                ;;
            *)
                log_error "Unsupported Linux distribution: $ID"
                exit 1
                ;;
        esac
    else
        log_error "Cannot detect Linux distribution. /etc/os-release not found."
        exit 1
    fi
}

# Check if Docker is installed and running
check_docker() {
    log_info "Checking Docker installation..."
    
    if ! command_exists docker; then
        log_info "Docker is not installed"
        return 1
    fi
    
    # Check Docker version
    local docker_version
    docker_version=$(docker --version 2>/dev/null || echo "")
    if [ -z "$docker_version" ]; then
        log_warn "Docker command exists but version check failed"
        return 1
    fi
    log_info "Docker found: $docker_version"
    
    # Check if Docker daemon is running
    if ! docker info >/dev/null 2>&1; then
        log_warn "Docker is installed but daemon is not running"
        return 2
    fi
    
    log_success "Docker is installed and running"
    return 0
}

# Install Docker on Linux
install_docker_linux() {
    log_info "Installing Docker on Linux ($DISTRO)..."
    
    case "$DISTRO" in
        ubuntu|debian)
            install_docker_debian
            ;;
        rhel|centos|amazonlinux)
            install_docker_rhel
            ;;
        *)
            log_error "Unsupported distribution for Docker installation: $DISTRO"
            exit 1
            ;;
    esac
    
    # Start and enable Docker service
    log_info "Starting Docker service..."
    run_cmd systemctl start docker
    run_cmd systemctl enable docker
    
    # Add current user to docker group (if not root)
    if ! is_root; then
        local current_user
        current_user=$(whoami)
        if ! groups "$current_user" | grep -q docker; then
            log_info "Adding user $current_user to docker group..."
            run_cmd usermod -aG docker "$current_user"
            log_warn "User added to docker group. You may need to log out and back in for changes to take effect."
            log_warn "Alternatively, run: newgrp docker"
        else
            log_info "User $current_user is already in docker group"
        fi
    fi
    
    # Verify Docker is running
    log_info "Verifying Docker installation..."
    sleep 2  # Give Docker a moment to start
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker installation completed but daemon is not running"
        log_error "Please check: systemctl status docker"
        exit 1
    fi
    
    log_success "Docker installed and running successfully"
}

# Install Docker on Debian/Ubuntu
install_docker_debian() {
    log_info "Installing Docker on Debian/Ubuntu..."
    
    # Remove old versions
    run_cmd apt-get remove -y docker docker-engine docker.io containerd runc 2>/dev/null || true
    
    # Install prerequisites
    run_cmd apt-get update -y
    run_cmd apt-get install -y \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    local gpg_key="/usr/share/keyrings/docker-archive-keyring.gpg"
    if [ ! -f "$gpg_key" ]; then
        log_info "Adding Docker GPG key..."
        run_cmd install -m 0755 -d /etc/apt/keyrings
        run_cmd curl -fsSL https://download.docker.com/linux/$DISTRO/gpg -o "$gpg_key"
        run_cmd chmod a+r "$gpg_key"
    else
        log_info "Docker GPG key already exists"
    fi
    
    # Set up Docker repository
    local repo_file="/etc/apt/sources.list.d/docker.list"
    if [ ! -f "$repo_file" ]; then
        log_info "Adding Docker repository..."
        local arch="$OS_ARCH"
        [ "$arch" = "aarch64" ] && arch="arm64"
        echo "deb [arch=$arch signed-by=$gpg_key] https://download.docker.com/linux/$DISTRO $(lsb_release -cs) stable" | \
            run_cmd tee "$repo_file" > /dev/null
    else
        log_info "Docker repository already configured"
    fi
    
    # Install Docker Engine
    run_cmd apt-get update -y
    run_cmd apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
}

# Install Docker on RHEL/CentOS/Amazon Linux
install_docker_rhel() {
    log_info "Installing Docker on RHEL/CentOS/Amazon Linux..."
    
    # Remove old versions
    run_cmd yum remove -y docker docker-client docker-client-latest docker-common docker-latest docker-latest-logrotate docker-logrotate docker-engine 2>/dev/null || true
    
    # Install prerequisites
    run_cmd yum install -y yum-utils
    
    # Add Docker repository
    local repo_file="/etc/yum.repos.d/docker-ce.repo"
    if [ ! -f "$repo_file" ]; then
        log_info "Adding Docker repository..."
        run_cmd yum-config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
    else
        log_info "Docker repository already configured"
    fi
    
    # Install Docker Engine
    run_cmd yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    
    # Start Docker service
    run_cmd systemctl start docker
    run_cmd systemctl enable docker
}

# Install Docker on macOS
install_docker_macos() {
    log_info "Installing Docker on macOS..."
    
    # Check if Homebrew is available
    if command_exists brew; then
        log_info "Using Homebrew to install Docker Desktop..."
        
        if brew list --cask docker >/dev/null 2>&1; then
            log_info "Docker Desktop is already installed via Homebrew"
        else
            log_info "Installing Docker Desktop via Homebrew..."
            run_cmd brew install --cask docker
            log_warn "Docker Desktop has been installed. Please start it manually from Applications."
            log_warn "After starting Docker Desktop, run this script again to verify installation."
            return 0
        fi
    else
        log_warn "Homebrew not found. Manual installation required."
        log_warn "Please install Docker Desktop manually from: https://www.docker.com/products/docker-desktop"
        log_warn "Or install Homebrew first: /bin/bash -c \"\$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)\""
        log_warn "After installing Docker Desktop, run this script again to verify installation."
        return 0
    fi
    
    # Check if Docker Desktop is running
    if ! docker info >/dev/null 2>&1; then
        log_warn "Docker Desktop is installed but not running"
        log_warn "Please start Docker Desktop from Applications or run: open -a Docker"
        return 1
    fi
}

# Check if Docker Compose v2 is installed
check_docker_compose() {
    log_info "Checking Docker Compose v2 installation..."
    
    if ! command_exists docker; then
        log_error "Docker must be installed before Docker Compose"
        return 1
    fi
    
    # Check for Docker Compose v2 plugin
    if docker compose version >/dev/null 2>&1; then
        local compose_version
        compose_version=$(docker compose version)
        log_success "Docker Compose v2 found: $compose_version"
        return 0
    fi
    
    # Check for legacy docker-compose v1 (we don't want this)
    if command_exists docker-compose; then
        log_warn "Legacy docker-compose v1 detected. This script installs v2 plugin instead."
    fi
    
    log_info "Docker Compose v2 is not installed"
    return 1
}

# Install Docker Compose v2
install_docker_compose() {
    log_info "Installing Docker Compose v2..."
    
    if [ "$OS_TYPE" = "macos" ]; then
        # On macOS, Docker Compose v2 comes with Docker Desktop
        log_info "Docker Compose v2 should be included with Docker Desktop"
        if ! docker compose version >/dev/null 2>&1; then
            log_error "Docker Compose v2 not found. Please ensure Docker Desktop is fully installed and running."
            exit 1
        fi
    else
        # On Linux, install as plugin (should be installed with Docker)
        log_info "Docker Compose v2 should be installed with Docker Engine"
        if ! docker compose version >/dev/null 2>&1; then
            log_error "Docker Compose v2 plugin not found. Please reinstall Docker with compose plugin."
            exit 1
        fi
    fi
    
    log_success "Docker Compose v2 installed successfully"
}

# Main installation function
main() {
    log_info "Starting Docker and Docker Compose v2 installation script"
    log_info "Dry-run mode: $DRY_RUN"
    
    # Detect OS
    detect_os
    
    # Check sudo if needed (Linux)
    if [ "$OS_TYPE" = "linux" ]; then
        check_sudo
    fi
    
    # Check Docker
    local docker_status
    if check_docker; then
        docker_status=0
    else
        docker_status=$?
        if [ "$docker_status" -eq 1 ]; then
            # Docker not installed
            log_info "Docker is not installed. Proceeding with installation..."
            if [ "$OS_TYPE" = "linux" ]; then
                install_docker_linux
            else
                install_docker_macos
                # On macOS, we may need user to start Docker Desktop
                if ! check_docker; then
                    log_warn "Please start Docker Desktop and run this script again"
                    exit 0
                fi
            fi
        elif [ "$docker_status" -eq 2 ]; then
            # Docker installed but not running
            log_info "Starting Docker daemon..."
            if [ "$OS_TYPE" = "linux" ]; then
                run_cmd systemctl start docker
                sleep 2
                if ! check_docker; then
                    log_error "Failed to start Docker daemon"
                    exit 1
                fi
            else
                log_warn "Please start Docker Desktop manually"
                exit 1
            fi
        fi
    fi
    
    # Check Docker Compose
    if ! check_docker_compose; then
        install_docker_compose
    fi
    
    # Final verification
    log_info "Performing final verification..."
    local docker_ver docker_compose_ver
    docker_ver=$(docker --version)
    docker_compose_ver=$(docker compose version)
    
    log_success "Installation complete!"
    echo ""
    echo "Docker: $docker_ver"
    echo "Docker Compose: $docker_compose_ver"
    echo ""
    
    if [ "$OS_TYPE" = "linux" ] && ! is_root; then
        local current_user
        current_user=$(whoami)
        if groups "$current_user" | grep -q docker; then
            log_info "User $current_user is in docker group"
        else
            log_warn "User $current_user may need to log out and back in to use Docker without sudo"
        fi
    fi
    
    log_success "All checks passed. Docker and Docker Compose v2 are ready to use."
}

# Run main function
main "$@"

