#!/usr/bin/env bash
#
# Environment validation script for ig_profile_scraper
# 
# This script:
# 1. Checks if .env file exists
# 2. Validates all required variables from .env.example are set
# 3. Creates directories specified in environment variables if they don't exist
#
# Usage:
#   ./scripts/validate_env.sh
#

set -Eeuo pipefail

# Color codes for output
readonly RED='\033[0;31m'
readonly GREEN='\033[0;32m'
readonly YELLOW='\033[1;33m'
readonly BLUE='\033[0;34m'
readonly NC='\033[0m' # No Color

# Script directory and project root
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
ENV_FILE="$PROJECT_ROOT/.env"
ENV_EXAMPLE_FILE="$PROJECT_ROOT/.env.example"
CONFIG_FILE="${IGSCRAPER_CONFIG:-$PROJECT_ROOT/config.toml}"

# Validation state
ERRORS=0
WARNINGS=0

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $*"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $*"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $*"
    ((WARNINGS++)) || true
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $*" >&2
    ((ERRORS++)) || true
}

# Error handler
error_handler() {
    local line_number=$1
    log_error "Script failed at line $line_number"
    exit 1
}

trap 'error_handler $LINENO' ERR

# Check if .env file exists
check_env_file() {
    log_info "Checking for .env file..."
    
    if [ ! -f "$ENV_FILE" ]; then
        log_error ".env file not found at: $ENV_FILE"
        log_info "Please create .env file from .env.example:"
        log_info "  cp .env.example .env"
        log_info "  # Then edit .env with your values"
        return 1
    fi
    
    log_success ".env file found"
    return 0
}

# Source .env file
source_env_file() {
    log_info "Loading environment variables from .env..."
    
    # Use set -a to automatically export variables
    set -a
    # shellcheck source=/dev/null
    source "$ENV_FILE"
    set +a
    
    log_success "Environment variables loaded"
}

# Extract variable names from .env.example
extract_env_vars() {
    local example_file="$1"
    local vars=()
    
    if [ ! -f "$example_file" ]; then
        log_error ".env.example file not found at: $example_file"
        return 1
    fi
    
    # Extract variable names (lines that start with a letter and contain =)
    # Exclude comments and empty lines
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        
        # Extract variable name (everything before =)
        if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)= ]]; then
            vars+=("${BASH_REMATCH[1]}")
        fi
    done < "$example_file"
    
    # Return array (bash workaround)
    printf '%s\n' "${vars[@]}"
}

# Validate required environment variables
validate_env_vars() {
    log_info "Validating environment variables..."
    
    if [ ! -f "$ENV_EXAMPLE_FILE" ]; then
        log_warn ".env.example not found, skipping variable validation"
        return 0
    fi
    
    local missing_vars=()
    local optional_vars=()
    local required_vars=()
    
    # Extract all variables from .env.example
    while IFS= read -r var_name; do
        [ -z "$var_name" ] && continue
        
        # Safely check if variable is set and not empty
        # Use eval to safely handle indirect variable expansion with set -u
        local var_value=""
        if eval "[ -n \"\${${var_name}:-}\" ]" 2>/dev/null; then
            eval "var_value=\"\${${var_name}}\""
        fi
        
        if [ -z "$var_value" ]; then
            # Check if it's commented out in .env.example (optional)
            if grep -q "^[[:space:]]*#[[:space:]]*${var_name}=" "$ENV_EXAMPLE_FILE"; then
                optional_vars+=("$var_name")
            else
                required_vars+=("$var_name")
                missing_vars+=("$var_name")
            fi
        fi
    done < <(extract_env_vars "$ENV_EXAMPLE_FILE")
    
    # Report missing required variables
    if [ ${#missing_vars[@]} -gt 0 ]; then
        log_error "Missing required environment variables:"
        for var in "${missing_vars[@]}"; do
            log_error "  - $var"
        done
        log_info "Please set these variables in your .env file"
        return 1
    fi
    
    # Report optional variables that are not set (informational)
    if [ ${#optional_vars[@]} -gt 0 ]; then
        log_info "Optional variables not set (these are commented in .env.example):"
        for var in "${optional_vars[@]}"; do
            log_info "  - $var (optional)"
        done
    fi
    
    log_success "All required environment variables are set"
    return 0
}

# Check if a path is a directory path (ends with / or is a directory)
is_directory_path() {
    local path="$1"
    # Remove trailing slash for checking
    path="${path%/}"
    
    # If path ends with certain patterns, it's likely a directory
    if [[ "$path" =~ (outputs|logs|media|screens|data|tmp|shot_dir|log_dir|media_path)$ ]] || \
       [[ "$path" =~ /(outputs|logs|media|screens|data|tmp)/?$ ]]; then
        return 0
    fi
    
    # Check if it's an existing directory
    if [ -d "$path" ]; then
        return 0
    fi
    
    return 1
}

# Extract directory paths from config.toml
extract_directories_from_config() {
    local config_file="$1"
    local dirs=()
    
    if [ ! -f "$config_file" ]; then
        log_warn "Config file not found: $config_file"
        return 0
    fi
    
    log_info "Extracting directory paths from config.toml..."
    
    # Extract paths from [data] section that are likely directories
    while IFS= read -r line; do
        # Skip comments and empty lines
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        
        # Match key = value patterns
        if [[ "$line" =~ ^[[:space:]]*([a-z_]+)[[:space:]]*=[[:space:]]*\"?([^\"#]+)\"? ]]; then
            local key="${BASH_REMATCH[1]}"
            local value="${BASH_REMATCH[2]}"
            value="${value// }"  # Trim whitespace
            
            # Check if this key is likely a directory
            if [[ "$key" =~ (output_dir|shot_dir|log_dir|media_path|log_dir) ]] || \
               is_directory_path "$value"; then
                # Resolve path (handle placeholders by using PROJECT_ROOT as base)
                local resolved_path="$value"
                
                # Replace common placeholders with actual values
                resolved_path="${resolved_path//\{output_dir\}/outputs}"
                resolved_path="${resolved_path//\{date\}/$(date +%Y%m%d)}"
                
                # If relative, make it relative to project root
                if [[ "$resolved_path" != /* ]]; then
                    resolved_path="$PROJECT_ROOT/$resolved_path"
                fi
                
                # Remove placeholders that we can't resolve yet
                if [[ ! "$resolved_path" =~ \{ ]]; then
                    dirs+=("$resolved_path")
                fi
            fi
        fi
    done < "$config_file"
    
    # Also check environment variables for directory paths
    for var_name in output_dir shot_dir log_dir media_path IGSCRAPER_OUTPUT_DIR; do
        if [ -n "${!var_name:-}" ]; then
            local dir_path="${!var_name}"
            if [[ "$dir_path" != /* ]]; then
                dir_path="$PROJECT_ROOT/$dir_path"
            fi
            dirs+=("$dir_path")
        fi
    done
    
    # Return unique directories
    printf '%s\n' "${dirs[@]}" | sort -u
}

# Create directories if they don't exist
create_directories() {
    log_info "Checking and creating required directories..."
    
    local dirs_to_create=()
    
    # Get directories from config
    while IFS= read -r dir_path; do
        [ -z "$dir_path" ] && continue
        dirs_to_create+=("$dir_path")
    done < <(extract_directories_from_config "$CONFIG_FILE")
    
    # Also check for common output directories from env vars
    if [ -n "${output_dir:-}" ]; then
        local output_path="$output_dir"
        if [[ "$output_path" != /* ]]; then
            output_path="$PROJECT_ROOT/$output_path"
        fi
        dirs_to_create+=("$output_path")
    fi
    
    # Default output directory if nothing specified
    if [ ${#dirs_to_create[@]} -eq 0 ]; then
        dirs_to_create+=("$PROJECT_ROOT/outputs")
        dirs_to_create+=("$PROJECT_ROOT/outputs/logs")
    fi
    
    # Create directories
    local created_count=0
    for dir_path in "${dirs_to_create[@]}"; do
        # Skip if path contains unresolved placeholders
        if [[ "$dir_path" =~ \{ ]]; then
            continue
        fi
        
        if [ ! -d "$dir_path" ]; then
            log_info "Creating directory: $dir_path"
            mkdir -p "$dir_path"
            ((created_count++)) || true
        else
            log_info "Directory already exists: $dir_path"
        fi
    done
    
    if [ $created_count -gt 0 ]; then
        log_success "Created $created_count directory/directories"
    else
        log_success "All required directories exist"
    fi
}

# Validate specific important variables
validate_specific_vars() {
    log_info "Validating specific environment variables..."
    
    # PostgreSQL variables (required for enqueue_client)
    local pg_vars=("PUGSY_PG_HOST" "PUGSY_PG_PORT" "PUGSY_PG_DATABASE" "PUGSY_PG_USER" "PUGSY_PG_PASSWORD")
    local pg_missing=()
    
    for var in "${pg_vars[@]}"; do
        local var_value=""
        if eval "[ -n \"\${${var}:-}\" ]" 2>/dev/null; then
            eval "var_value=\"\${${var}}\""
        fi
        if [ -z "$var_value" ]; then
            pg_missing+=("$var")
        fi
    done
    
    if [ ${#pg_missing[@]} -gt 0 ]; then
        log_warn "PostgreSQL variables not set (required for enqueue_client):"
        for var in "${pg_missing[@]}"; do
            log_warn "  - $var"
        done
    else
        log_success "PostgreSQL configuration variables are set"
    fi
    
    # Validate PUGSY_PG_PORT is a number
    local pg_port="${PUGSY_PG_PORT:-}"
    if [ -n "$pg_port" ]; then
        if ! [[ "$pg_port" =~ ^[0-9]+$ ]]; then
            log_error "PUGSY_PG_PORT must be a number, got: $pg_port"
        fi
    fi
    
    # Check for Chrome binaries if specified
    local chrome_bin="${CHROME_BIN:-}"
    if [ -n "$chrome_bin" ] && [ ! -f "$chrome_bin" ]; then
        log_warn "CHROME_BIN specified but file not found: $chrome_bin"
    fi
    
    local chromedriver_bin="${CHROMEDRIVER_BIN:-}"
    if [ -n "$chromedriver_bin" ] && [ ! -f "$chromedriver_bin" ]; then
        log_warn "CHROMEDRIVER_BIN specified but file not found: $chromedriver_bin"
    fi
}

# Main validation function
main() {
    log_info "Starting environment validation for ig_profile_scraper"
    log_info "Project root: $PROJECT_ROOT"
    log_info "Config file: $CONFIG_FILE"
    
    # Check .env file exists
    if ! check_env_file; then
        exit 1
    fi
    
    # Source .env file
    source_env_file
    
    # Validate environment variables
    if ! validate_env_vars; then
        log_error "Environment variable validation failed"
        exit 1
    fi
    
    # Validate specific variables
    validate_specific_vars
    
    # Create directories
    create_directories
    
    # Summary
    echo ""
    if [ $ERRORS -eq 0 ] && [ $WARNINGS -eq 0 ]; then
        log_success "Environment validation completed successfully!"
        exit 0
    elif [ $ERRORS -eq 0 ]; then
        log_warn "Environment validation completed with $WARNINGS warning(s)"
        exit 0
    else
        log_error "Environment validation failed with $ERRORS error(s) and $WARNINGS warning(s)"
        exit 1
    fi
}

# Run main function
main "$@"

