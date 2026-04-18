#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_VERSION="3.12"

cd "$PROJECT_ROOT"

source "$HOME/.cargo/env" 2>/dev/null || true

ARCH="$(uname -m)"
if [ "$ARCH" = "arm64" ]; then
    TARGET_TRIPLE="aarch64-apple-darwin"
else
    TARGET_TRIPLE="x86_64-apple-darwin"
fi

echo "Detected architecture: $ARCH -> $TARGET_TRIPLE"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

install_homebrew() {
    if command_exists brew; then
        echo "Homebrew already installed: $(brew --version | head -1)"
        return
    fi

    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

    if [ "$ARCH" = "arm64" ]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
        echo 'eval "$(/opt/homebrew/bin/brew shellenv)"' >> "$HOME/.zprofile"
    else
        eval "$(/usr/local/bin/brew shellenv)"
        echo 'eval "$(/usr/local/bin/brew shellenv)"' >> "$HOME/.zprofile"
    fi
}

install_node() {
    if command_exists node; then
        echo "Node.js already installed: $(node -v)"
        return
    fi

    brew install node@20
    brew link node@20 --force
}

install_rust() {
    if command_exists cargo; then
        echo "Rust already installed: $(cargo --version)"
        return
    fi

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"

    if [ "$ARCH" = "arm64" ]; then
        rustup target add aarch64-apple-darwin
    else
        rustup target add x86_64-apple-darwin
    fi
}

install_python() {
    if command_exists python${PYTHON_VERSION}; then
        echo "Python ${PYTHON_VERSION} already installed"
        return
    fi

    brew install python@${PYTHON_VERSION}
    brew link python@${PYTHON_VERSION} --force
}

setup_venv() {
    if [ ! -d "venv" ]; then
        python${PYTHON_VERSION} -m venv venv
    fi

    source venv/bin/activate
    pip install --upgrade pip
    pip install -r requirements.txt
    pip install nuitka
}

install_tauri_cli() {
    cargo install tauri-cli --locked || true
}

install_frontend_deps() {
    npm install
}

build_python_sidecar() {
    source venv/bin/activate

    python -m nuitka \
        --standalone \
        --onefile \
        --include-package=cv2 \
        --macos-target-arch="$ARCH" \
        main.py

    mkdir -p src-tauri/bin

    SIDECAR_DEST="src-tauri/bin/main-${TARGET_TRIPLE}"

    if [ -f "main.bin" ]; then
        mv "main.bin" "$SIDECAR_DEST"
    elif [ -f "main" ]; then
        mv "main" "$SIDECAR_DEST"
    else
        echo "Python sidecar output not found"
        exit 1
    fi

    chmod +x "$SIDECAR_DEST"
}

build_tauri() {
    npm run tauri build
}

main() {
    install_homebrew
    install_node
    install_rust
    install_python
    setup_venv
    install_tauri_cli
    install_frontend_deps
    build_python_sidecar
    build_tauri

    echo "Build completed successfully ($TARGET_TRIPLE)"
}

main