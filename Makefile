SHELL := bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV        ?= venv
VIDEO       ?= input/1.mp4
ARGS        ?=

ENTRY       := main.py
PY_SOURCES  := $(ENTRY) $(wildcard tracker/*.py) requirements.txt
APP_DIR     := app
DIST_DIR    ?= dist
NUITKA_ARGS ?=

UNAME_S := $(shell uname -s 2>/dev/null || echo unknown)
UNAME_M := $(shell uname -m 2>/dev/null || echo unknown)

ifneq (,$(findstring MINGW,$(UNAME_S)))
  OS := windows
else ifneq (,$(findstring MSYS,$(UNAME_S)))
  OS := windows
else ifneq (,$(findstring CYGWIN,$(UNAME_S)))
  OS := windows
else ifeq ($(UNAME_S),Darwin)
  OS := macos
else ifeq ($(UNAME_S),Linux)
  OS := linux
else
  OS := windows
endif

ifeq ($(OS),windows)
  PYTHON       ?= py -3.12
  VENV_PY      := $(VENV)/Scripts/python.exe
  PIP          := $(VENV)/Scripts/pip.exe
  TARGET_TRIPLE := x86_64-pc-windows-msvc
  PLATFORM_FLAGS :=
  EXE          := .exe
else ifeq ($(OS),macos)
  PYTHON       ?= python3.12
  VENV_PY      := $(VENV)/bin/python
  PIP          := $(VENV)/bin/pip
  ifeq ($(UNAME_M),arm64)
    TARGET_TRIPLE := aarch64-apple-darwin
  else
    TARGET_TRIPLE := x86_64-apple-darwin
  endif
  PLATFORM_FLAGS := --macos-target-arch=$(UNAME_M)
  EXE          :=
  BREW ?= $(shell command -v brew 2>/dev/null || echo /opt/homebrew/bin/brew)
  export PATH := /opt/homebrew/bin:/usr/local/bin:$(HOME)/.cargo/bin:$(PATH)
else
  PYTHON       ?= python3.12
  VENV_PY      := $(VENV)/bin/python
  PIP          := $(VENV)/bin/pip
  ifeq ($(UNAME_M),aarch64)
    TARGET_TRIPLE := aarch64-unknown-linux-gnu
  else
    TARGET_TRIPLE := x86_64-unknown-linux-gnu
  endif
  PLATFORM_FLAGS :=
  EXE          :=
  export PATH := $(HOME)/.cargo/bin:$(PATH)
endif

SIDECAR := $(APP_DIR)/src-tauri/bin/main-$(TARGET_TRIPLE)$(EXE)

APPIMAGE_DIR    := $(APP_DIR)/src-tauri/target/release/bundle/appimage
APPIMAGE_PLUGIN := $(HOME)/.cache/tauri/linuxdeploy-plugin-appimage.AppImage
GST_PLUGIN_DIR  ?= /usr/lib/$(shell gcc -print-multiarch 2>/dev/null)/gstreamer-1.0

ifeq ($(OS),linux)
  BUNDLES := --bundles deb,appimage
else
  BUNDLES :=
endif

.PHONY: help install run sidecar appimage fix-appimage build dist clean

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show these commands
	@echo "Morris Water Maze Analysis"
	@echo ""
	@echo "  make install                         first-time setup"
	@echo "  make run VIDEO=input/1.mp4       analyse a video"
	@echo "  make appimage                        compile only the AppImage (faster)"
	@echo "  make dist                            compile the app (installers in dist/)"
	@echo "  make clean                           remove build files"
	@echo ""
	@echo "Add options: make run VIDEO=input/1.mp4 ARGS=\"--autoconfig\""

# ---------------------------------------------------------------------------
# First-time setup
# ---------------------------------------------------------------------------
install: ## Install system tools, Python and app dependencies
ifeq ($(OS),linux)
	@if ! dpkg -s libwebkit2gtk-4.1-dev >/dev/null 2>&1 || ! command -v python3.12 >/dev/null; then \
		sudo apt update && sudo apt install -y \
			curl wget file build-essential pkg-config patchelf \
			libwebkit2gtk-4.1-dev libssl-dev libayatana-appindicator3-dev \
			librsvg2-dev libxdo-dev python3.12 python3.12-venv python3.12-dev; \
	fi
	@command -v node >/dev/null || { \
		curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs; }
else ifeq ($(OS),macos)
	@command -v $(BREW) >/dev/null || /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	@$(BREW) list python@3.12 >/dev/null 2>&1 || $(BREW) install python@3.12
	@command -v node >/dev/null || { $(BREW) install node@20 && $(BREW) link node@20 --force; }
else
	@installed=0; \
	if ! py -3.12 --version >/dev/null 2>&1; then \
		winget install --silent --accept-package-agreements --accept-source-agreements Python.Python.3.12; installed=1; \
	fi; \
	if ! command -v node >/dev/null 2>&1; then \
		winget install --silent --accept-package-agreements --accept-source-agreements OpenJS.NodeJS.LTS; installed=1; \
	fi; \
	if ! command -v cargo >/dev/null 2>&1; then \
		winget install --silent --accept-package-agreements --accept-source-agreements Rustlang.Rustup; installed=1; \
	fi; \
	if [ ! -f "/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" ]; then \
		winget install --silent --accept-package-agreements --accept-source-agreements Microsoft.VisualStudio.2022.BuildTools \
			--override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools"; installed=1; \
	fi; \
	if [ "$$installed" = "1" ]; then \
		echo "Tools were installed. Close this terminal, reopen it, and run 'make install' again."; exit 1; \
	fi
endif
	@command -v cargo >/dev/null || curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@cd $(APP_DIR) && npm install
	@echo "Ready. Now run: make run VIDEO=input/yourvideo.mp4"

# ---------------------------------------------------------------------------
# Analyse a video
# ---------------------------------------------------------------------------
run: ## Analyse a video (VIDEO=path, ARGS=extra flags)
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	@test -f "$(VIDEO)" || { echo "Video not found: $(VIDEO)"; exit 1; }
	$(VENV_PY) $(ENTRY) --video "$(VIDEO)" $(ARGS)

# ---------------------------------------------------------------------------
# Desktop app
# ---------------------------------------------------------------------------
sidecar: $(SIDECAR) ## Compile the Python part of the desktop app

$(SIDECAR): $(PY_SOURCES)
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	$(VENV_PY) -m nuitka \
		--standalone \
		--onefile \
		--include-package=cv2 \
		$(PLATFORM_FLAGS) \
		$(NUITKA_ARGS) \
		$(ENTRY)
	@mkdir -p $(dir $(SIDECAR))
	@set -e; \
	if [ -f main.bin ]; then mv -f main.bin "$(SIDECAR)"; \
	elif [ -f main.exe ]; then mv -f main.exe "$(SIDECAR)"; \
	else mv -f main "$(SIDECAR)"; fi
	@chmod +x "$(SIDECAR)" 2>/dev/null || true
	@echo "Python sidecar ready"

build: sidecar ## Compile the desktop app
	@test -d $(APP_DIR)/node_modules || (cd $(APP_DIR) && npm install)
	rm -rf $(APP_DIR)/src-tauri/target/release/bundle
	cd $(APP_DIR) && npm run tauri build -- $(BUNDLES)
ifneq (,$(findstring appimage,$(BUNDLES)))
	@$(MAKE) --no-print-directory fix-appimage
endif

appimage: sidecar ## Compile only the AppImage (Linux, faster)
	@test "$(OS)" = "linux" || { echo "AppImage is Linux only."; exit 1; }
	@test -d $(APP_DIR)/node_modules || (cd $(APP_DIR) && npm install)
	rm -rf $(APPIMAGE_DIR)
	cd $(APP_DIR) && npm run tauri build -- --bundles appimage
	@$(MAKE) --no-print-directory fix-appimage
	@mkdir -p $(DIST_DIR)
	@rm -f $(DIST_DIR)/*.AppImage
	@find $(APPIMAGE_DIR) -maxdepth 1 -name '*.AppImage' -exec cp -f {} $(DIST_DIR)/ \;
	@echo "AppImage copied to $(DIST_DIR)/"

# Tauri's AppImage bundler runs patchelf/strip on the Nuitka one-file sidecar,
# which destroys its attached payload. Put the original sidecar back and
# repackage the AppImage with the cached linuxdeploy plugin. The AppRun hook
# points GStreamer at usr/lib/gstreamer-1.0, so bundle the host plugins there
# or WebKit cannot decode the preview video (black window / no calibration).
fix-appimage:
	@test "$(OS)" = "linux" || { echo "AppImage is Linux only."; exit 1; }
	@APP_DIR=$$(find "$(CURDIR)/$(APPIMAGE_DIR)" -maxdepth 1 -name '*.AppDir' 2>/dev/null | head -1); \
	if [ -z "$$APP_DIR" ]; then echo "No AppDir found; skipping AppImage repair."; exit 0; fi; \
	test -x "$(APPIMAGE_PLUGIN)" || { echo "Missing $(APPIMAGE_PLUGIN); run 'make appimage' once."; exit 1; }; \
	OUT=$$(find "$(CURDIR)/$(APPIMAGE_DIR)" -maxdepth 1 -name '*.AppImage' | head -1); \
	cp -f "$(SIDECAR)" "$$APP_DIR/usr/bin/main"; \
	chmod +x "$$APP_DIR/usr/bin/main"; \
	if [ -d "$(GST_PLUGIN_DIR)" ]; then \
		mkdir -p "$$APP_DIR/usr/lib/gstreamer-1.0"; \
		cp -a "$(GST_PLUGIN_DIR)/." "$$APP_DIR/usr/lib/gstreamer-1.0/"; \
	fi; \
	[ -n "$$OUT" ] && rm -f "$$OUT"; \
	( cd "$(CURDIR)/$(APPIMAGE_DIR)" && ARCH=$$(uname -m) "$(APPIMAGE_PLUGIN)" --appimage-extract-and-run --appdir="$$APP_DIR" >/dev/null ); \
	NEW=$$(find "$(CURDIR)/$(APPIMAGE_DIR)" -maxdepth 1 -name '*.AppImage' | head -1); \
	if [ -z "$$NEW" ]; then echo "AppImage rebuild failed."; exit 1; fi; \
	if [ -n "$$OUT" ] && [ "$$NEW" != "$$OUT" ]; then mv -f "$$NEW" "$$OUT"; NEW=$$OUT; fi; \
	echo "AppImage repaired: $$NEW"

dist: build ## Compile the app and put installers in dist/
	rm -rf $(DIST_DIR)
	mkdir -p $(DIST_DIR)
	@find $(APP_DIR)/src-tauri/target/release/bundle -mindepth 2 -maxdepth 2 -type f \
		-exec cp {} $(DIST_DIR)/ \;
	@echo "Installers are in $(DIST_DIR)/"
	@find $(DIST_DIR) -maxdepth 1 -type f | sed 's/^/  /'

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove build files
	rm -rf main.build main.dist main.onefile-build __pycache__ tracker/__pycache__ $(DIST_DIR)
	@find . -type d -name __pycache__ \
		-not -path './$(VENV)/*' \
		-not -path './$(APP_DIR)/node_modules/*' \
		-exec rm -rf {} + 2>/dev/null || true
