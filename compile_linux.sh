#!/usr/bin/env bash

set -e

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON_VERSION="3.12"

cd "$PROJECT_ROOT"

command_exists() {
    command -v "$1" >/dev/null 2>&1
}

install_apt_dependencies() {
    sudo apt install -y \
        curl \
        wget \
        file \
        build-essential \
        pkg-config \
        patchelf \
        libwebkit2gtk-4.1-dev \
        libssl-dev \
        libayatana-appindicator3-dev \
        librsvg2-dev \
        libxdo-dev \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev
}

install_node() {
    if command_exists node; then
        echo "Node.js already installed: $(node -v)"
        return
    fi

    curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
    sudo apt install -y nodejs
}

install_rust() {
    if command_exists cargo; then
        echo "Rust already installed: $(cargo --version)"
        return
    fi

    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
    source "$HOME/.cargo/env"
}

install_python() {
    if command_exists python${PYTHON_VERSION}; then
        echo "Python ${PYTHON_VERSION} already installed"
        return
    fi

    sudo apt install -y software-properties-common
    sudo add-apt-repository -y ppa:deadsnakes/ppa
    sudo apt update
    sudo apt install -y \
        python${PYTHON_VERSION} \
        python${PYTHON_VERSION}-venv \
        python${PYTHON_VERSION}-dev
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
    source "$HOME/.cargo/env"
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
        main.py

    mkdir -p src-tauri/bin

    if [ -f "main.bin" ]; then
        mv "main.bin" "src-tauri/bin/main-x86_64-unknown-linux-gnu"
    elif [ -f "main" ]; then
        mv "main" "src-tauri/bin/main-x86_64-unknown-linux-gnu"
    else
        echo "Python sidecar output not found"
        exit 1
    fi

    chmod +x "src-tauri/bin/main-x86_64-unknown-linux-gnu"
}

build_tauri() {
    source "$HOME/.cargo/env"
    npm run tauri build
}

main() {
    install_apt_dependencies
    install_node
    install_rust
    install_python
    install_tauri_cli
    setup_venv
    install_frontend_deps
    build_python_sidecar
    build_tauri

    echo "Build completed successfully"
}

main