#!/bin/bash
#
# Clean Docs CLI Install Script
# Usage: curl -fsSL https://raw.githubusercontent.com/owner/clean-docs/main/install.sh | bash
#
# Environment variables:
#   WITH_SEMANTIC=1  - Install with semantic analysis support
#

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
PACKAGE_NAME="clean-docs"
MIN_PYTHON_VERSION="3.10"
INSTALL_DIR=""
WITH_SEMANTIC=false

# Functions
print_banner() {
    echo ""
    echo -e "${BLUE}╔════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║     Clean Docs CLI Installer           ║${NC}"
    echo -e "${BLUE}╚════════════════════════════════════════╝${NC}"
    echo ""
}

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Get Python version
get_python_version() {
    python3 --version 2>/dev/null | grep -oE '[0-9]+\.[0-9]+' | head -1 || echo "0"
}

# Compare version numbers
version_gte() {
    [ "$1" = "$(echo -e "$1\n$2" | sort -V | tail -n1)" ]
}

# Detect OS
detect_os() {
    case "$(uname -s)" in
        Linux*)     echo "linux";;
        Darwin*)    echo "macos";;
        CYGWIN*|MINGW*|MSYS*) echo "windows";;
        *)          echo "unknown";;
    esac
}

# Check and install Python
check_python() {
    log_info "Checking Python installation..."
    
    if command_exists python3; then
        PYTHON_VERSION=$(get_python_version)
        log_info "Found Python $PYTHON_VERSION"
        
        if version_gte "$PYTHON_VERSION" "$MIN_PYTHON_VERSION"; then
            log_success "Python version is compatible (>= $MIN_PYTHON_VERSION)"
            PYTHON_CMD="python3"
        else
            log_error "Python $MIN_PYTHON_VERSION or higher is required (found $PYTHON_VERSION)"
            log_info "Please upgrade Python: https://www.python.org/downloads/"
            exit 1
        fi
    else
        log_error "Python 3 is not installed"
        log_info "Please install Python ${MIN_PYTHON_VERSION}+: https://www.python.org/downloads/"
        exit 1
    fi
}

# Check pip
check_pip() {
    log_info "Checking pip installation..."
    
    if command_exists pip3; then
        PIP_CMD="pip3"
        log_success "Found pip3"
    elif $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
        PIP_CMD="$PYTHON_CMD -m pip"
        log_success "Found pip module"
    else
        log_warning "pip not found, attempting to install..."
        $PYTHON_CMD -m ensurepip --upgrade 2>/dev/null || true
        
        if $PYTHON_CMD -m pip --version >/dev/null 2>&1; then
            PIP_CMD="$PYTHON_CMD -m pip"
            log_success "pip installed successfully"
        else
            log_error "Failed to install pip"
            log_info "Please install pip manually: https://pip.pypa.io/en/stable/installation/"
            exit 1
        fi
    fi
}

# Check optional prerequisites
check_prerequisites() {
    log_info "Checking optional prerequisites..."
    echo ""
    
    PREREQ_WARNINGS=0
    
    # Check git
    if command_exists git; then
        GIT_VERSION=$(git --version | grep -oE '[0-9]+\.[0-9]+' | head -1)
        log_success "git $GIT_VERSION"
    else
        log_warning "git not found - needed for fix-prs command"
        PREREQ_WARNINGS=$((PREREQ_WARNINGS + 1))
    fi
    
    # Check GitHub CLI
    if command_exists gh; then
        GH_VERSION=$(gh --version | head -1 | grep -oE '[0-9]+\.[0-9]+' | head -1)
        log_success "GitHub CLI $GH_VERSION"
        
        # Check if authenticated
        if gh auth status >/dev/null 2>&1; then
            log_success "GitHub CLI authenticated"
        else
            log_warning "GitHub CLI not authenticated - run 'gh auth login'"
            PREREQ_WARNINGS=$((PREREQ_WARNINGS + 1))
        fi
    else
        log_warning "GitHub CLI (gh) not found - needed for GitHub link checking and fix-prs"
        log_info "  Install: https://cli.github.com/"
        PREREQ_WARNINGS=$((PREREQ_WARNINGS + 1))
    fi
    
    # Check curl (for external link checking)
    if command_exists curl; then
        log_success "curl available"
    else
        log_warning "curl not found - external link checking may be limited"
        PREREQ_WARNINGS=$((PREREQ_WARNINGS + 1))
    fi
    
    echo ""
    if [ $PREREQ_WARNINGS -gt 0 ]; then
        log_warning "$PREREQ_WARNINGS optional prerequisite(s) missing"
        log_info "clean-docs will work but some features may be limited"
    else
        log_success "All prerequisites available"
    fi
    echo ""
}

# Install clean-docs
install_package() {
    log_info "Installing $PACKAGE_NAME..."
    
    INSTALL_ARGS="--user"
    
    # Check if we're in a virtual environment
    if [ -n "$VIRTUAL_ENV" ]; then
        log_info "Detected virtual environment, installing without --user"
        INSTALL_ARGS=""
    fi
    
    # Install command
    if [ "$WITH_SEMANTIC" = true ]; then
        log_info "Installing with semantic analysis support..."
        INSTALL_CMD="$PIP_CMD install $INSTALL_ARGS $PACKAGE_NAME[semantic]"
    else
        INSTALL_CMD="$PIP_CMD install $INSTALL_ARGS $PACKAGE_NAME"
    fi
    
    log_info "Running: $INSTALL_CMD"
    if eval "$INSTALL_CMD"; then
        log_success "$PACKAGE_NAME installed successfully"
    else
        log_error "Failed to install $PACKAGE_NAME"
        exit 1
    fi
}

# Get user site bin directory for PATH
get_user_bin_dir() {
    $PYTHON_CMD -c "import site; print(site.USER_BASE + '/bin')" 2>/dev/null || \
    $PYTHON_CMD -c "import site, os; print(os.path.join(site.USER_BASE, 'bin'))"
}

# Check if clean-docs is in PATH
check_in_path() {
    if command_exists clean-docs; then
        return 0
    fi
    return 1
}

# Add to PATH instructions
add_to_path_instructions() {
    if check_in_path; then
        log_success "'clean-docs' is already available in PATH"
        return 0
    fi
    
    log_warning "'clean-docs' is installed but not in your PATH"
    
    USER_BIN=$(get_user_bin_dir)
    OS=$(detect_os)
    
    echo ""
    log_info "To add to your PATH, run one of these commands:"
    echo ""
    
    case $OS in
        macos)
            echo -e "${YELLOW}For zsh (default on macOS):${NC}"
            echo "  echo 'export PATH=\"$USER_BIN:\$PATH\"' >> ~/.zshrc"
            echo "  source ~/.zshrc"
            echo ""
            echo -e "${YELLOW}For bash:${NC}"
            echo "  echo 'export PATH=\"$USER_BIN:\$PATH\"' >> ~/.bash_profile"
            echo "  source ~/.bash_profile"
            ;;
        linux)
            echo -e "${YELLOW}For bash:${NC}"
            echo "  echo 'export PATH=\"$USER_BIN:\$PATH\"' >> ~/.bashrc"
            echo "  source ~/.bashrc"
            echo ""
            echo -e "${YELLOW}For zsh:${NC}"
            echo "  echo 'export PATH=\"$USER_BIN:\$PATH\"' >> ~/.zshrc"
            echo "  source ~/.zshrc"
            ;;
        *)
            echo "  export PATH=\"$USER_BIN:\$PATH\""
            ;;
    esac
    
    echo ""
    log_info "Then run 'clean-docs --version' to verify"
}

# Verify installation
verify_installation() {
    log_info "Verifying installation..."
    
    if check_in_path; then
        VERSION=$(clean-docs --version 2>/dev/null || echo "unknown")
        log_success "Clean Docs $VERSION is ready to use!"
        echo ""
        log_info "Quick start:"
        echo "  clean-docs doctor          # Check your setup"
        echo "  clean-docs scan ./docs     # Scan your documentation"
        echo "  clean-docs --help          # Show all commands"
    else
        log_warning "Installation complete but 'clean-docs' not in PATH"
        add_to_path_instructions
    fi
}

# Parse arguments
parse_args() {
    while [[ $# -gt 0 ]]; do
        case $1 in
            --semantic)
                WITH_SEMANTIC=true
                shift
                ;;
            --version)
                echo "Clean Docs Installer v1.0"
                exit 0
                ;;
            --help)
                echo "Clean Docs CLI Installer"
                echo ""
                echo "Usage: curl -fsSL [url] | bash"
                echo ""
                echo "Options (passed via environment variables):"
                echo "  WITH_SEMANTIC=1  Install with semantic analysis support"
                echo ""
                exit 0
                ;;
            *)
                shift
                ;;
        esac
    done
}

# Main installation
main() {
    print_banner
    
    # Parse environment variables
    if [ -n "$WITH_SEMANTIC" ] && [ "$WITH_SEMANTIC" = "1" ]; then
        WITH_SEMANTIC=true
    fi
    
    parse_args "$@"
    
    OS=$(detect_os)
    log_info "Detected OS: $OS"
    
    check_python
    check_pip
    check_prerequisites
    install_package
    verify_installation
    
    if ! check_in_path; then
        add_to_path_instructions
    fi
    
    echo ""
    echo -e "${GREEN}Installation complete! 🎉${NC}"
    echo ""
}

# Run main function
main "$@"
