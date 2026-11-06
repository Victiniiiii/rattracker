SHELL := bash
.DEFAULT_GOAL := help

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
VENV        ?= venv
VIDEO       ?= input/1.mp4
ARGS        ?=
VERSION     ?= 1.1.0

ENTRY       := app_qt.py
CLI_ENTRY   := main.py
PY_SOURCES  := $(ENTRY) $(CLI_ENTRY) $(wildcard ui/*.py) $(wildcard tracker/*.py) requirements.txt
DATA        := appicon.png packaging/windows/appicon.ico packaging/macos/appicon.icns $(wildcard ui/assets/*)
BUILD_DIR   := build
DIST_DIR    ?= dist
APP_NAME    := rattracker
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
  PYTHON     ?= py -3.12
  VENV_PY    := $(VENV)/Scripts/python.exe
  PIP        := $(VENV)/Scripts/pip.exe
  EXE        := .exe
  STOCK_DIR  := $(BUILD_DIR)/app_qt.dist
  BIN        := $(STOCK_DIR)/$(APP_NAME)$(EXE)
  PLATFORM_FLAGS := --windows-console-mode=disable --windows-icon-from-ico=packaging/windows/appicon.ico
else ifeq ($(OS),macos)
  PYTHON     ?= python3.12
  VENV_PY    := $(VENV)/bin/python
  PIP        := $(VENV)/bin/pip
  EXE        :=
  STOCK_DIR  := $(BUILD_DIR)/app_qt.app
  BIN        := $(STOCK_DIR)/Contents/MacOS/$(APP_NAME)
  PLATFORM_FLAGS := --macos-create-app-bundle --macos-app-name=RatTracker --macos-app-icon=packaging/macos/appicon.icns
else
  PYTHON     ?= python3.12
  VENV_PY    := $(VENV)/bin/python
  PIP        := $(VENV)/bin/pip
  EXE        :=
  STOCK_DIR  := $(BUILD_DIR)/app_qt.dist
  BIN        := $(STOCK_DIR)/$(APP_NAME)
  PLATFORM_FLAGS :=
  # Qt's xcb plugin needs libxcb-cursor, which many desktops lack. Use the
  # bundled copy so `make run` works without installing system packages.
  RUN_ENV    := LD_LIBRARY_PATH="$(CURDIR)/packaging/linux/lib:$$LD_LIBRARY_PATH"
endif

.PHONY: help install run cli test build standalone bundle-libs smoke appimage deb dmg installer dist clean

# ---------------------------------------------------------------------------
# Help
# ---------------------------------------------------------------------------
help: ## Show these commands
	@echo "Rat Tracker (Qt)"
	@echo ""
	@echo "  make install                     first-time setup"
	@echo "  make run                         open the desktop app"
	@echo "  make cli VIDEO=input/1.mp4       analyse from the terminal"
	@echo "  make test                        run the headless test suite"
	@echo "  make build                       compile the standalone app"
	@echo "  make smoke                       run the compiled app end to end"
	@echo "  make dist                        compile installers into dist/"
	@echo "  make clean                       remove build files"
	@echo ""
	@echo "Add options: make cli VIDEO=input/1.mp4 ARGS=\"--autoconfig\""

# ---------------------------------------------------------------------------
# First-time setup
# ---------------------------------------------------------------------------
install: ## Install system tools and Python dependencies
ifeq ($(OS),linux)
	@if ! command -v python3.12 >/dev/null || ! command -v patchelf >/dev/null; then \
		sudo apt update && sudo apt install -y \
			curl wget file build-essential pkg-config patchelf \
			python3.12 python3.12-venv python3.12-dev \
			libgl1 libegl1 libxkbcommon0 libxkbcommon-x11-0 \
			libxcb-cursor0 libxcb-icccm4 libxcb-image0 libxcb-keysyms1 \
			libxcb-randr0 libxcb-render-util0 libxcb-shape0 libxcb-xinerama0 \
			libdbus-1-3 libfontconfig1 fontconfig; \
	fi
else ifeq ($(OS),macos)
	@command -v brew >/dev/null || /bin/bash -c "$$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
	@brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
else
	@installed=0; \
	if ! py -3.12 --version >/dev/null 2>&1; then \
		winget install --silent --accept-package-agreements --accept-source-agreements Python.Python.3.12; installed=1; \
	fi; \
	if [ ! -f "/c/Program Files (x86)/Microsoft Visual Studio/Installer/vswhere.exe" ]; then \
		winget install --silent --accept-package-agreements --accept-source-agreements Microsoft.VisualStudio.2022.BuildTools \
			--override "--wait --passive --add Microsoft.VisualStudio.Workload.VCTools"; installed=1; \
	fi; \
	if [ "$$installed" = "1" ]; then \
		echo "Tools were installed. Close this terminal, reopen it, and run 'make install' again."; exit 1; \
	fi
endif
	@test -d $(VENV) || $(PYTHON) -m venv $(VENV)
	@$(PIP) install --upgrade pip
	@$(PIP) install -r requirements.txt
	@echo "Ready. Now run: make run"

# ---------------------------------------------------------------------------
# Run and test
# ---------------------------------------------------------------------------
run: ## Open the desktop app
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	$(RUN_ENV) $(VENV_PY) $(ENTRY)

cli: ## Analyse a video from the terminal (VIDEO=path, ARGS=extra flags)
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	@test -f "$(VIDEO)" || { echo "Video not found: $(VIDEO)"; exit 1; }
	$(VENV_PY) $(CLI_ENTRY) --video "$(VIDEO)" $(ARGS)

test: ## Run the headless test suite
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	QT_QPA_PLATFORM=offscreen RATTRACKER_AUTOCONFIRM=1 \
		$(VENV_PY) -m unittest discover -s tests -v

smoke: build ## Run the compiled app end to end (headless)
	@tmp=$$(mktemp -d); \
	trap 'rm -rf "$$tmp"' EXIT; \
	if [ "$(OS)" = "windows" ]; then wtmp=$$(cygpath -w "$$tmp"); else wtmp="$$tmp"; fi; \
	cp tests/fixtures/1.mp4 "$$tmp/1.mp4"; \
	QT_QPA_PLATFORM=offscreen RATTRACKER_AUTOCONFIRM=1 \
	RATTRACKER_CONFIG_DIR="$$wtmp/config" \
	RATTRACKER_LOG="$$wtmp/run.log" \
	RATTRACKER_AUTORUN="$$wtmp/1.mp4" \
	RATTRACKER_AUTOEXIT=1 \
	"$(BIN)"; \
	status=$$?; \
	if ! grep -q '"done": true' "$$tmp/run.log"; then \
		echo "Frozen smoke failed (exit $$status)"; cat "$$tmp/run.log"; exit 1; \
	fi; \
	test -f "$$tmp/1"_*_coordinates.csv || { echo "Missing CSV output"; exit 1; }; \
	test -f "$$tmp/1"_*_summary.txt || { echo "Missing summary output"; exit 1; }; \
	echo "Frozen smoke OK"; \
	test $$status -eq 0

# ---------------------------------------------------------------------------
# Compile
# ---------------------------------------------------------------------------
build: $(BIN) ## Compile the standalone app

standalone: build ## Alias for build

$(BIN): $(PY_SOURCES) $(DATA)
	@test -x $(VENV_PY) || { echo "Run 'make install' first."; exit 1; }
	rm -rf $(STOCK_DIR)
	$(VENV_PY) -m nuitka \
		--standalone \
		--enable-plugin=pyside6 \
		--include-package=ui \
		--include-package=tracker \
		--include-package=cv2 \
		--include-data-file=appicon.png=appicon.png \
		--include-data-dir=ui/assets=ui/assets \
		--noinclude-qt-translations \
		--noinclude-dlls=libQt5* \
		--output-dir=$(BUILD_DIR) \
		--output-filename=$(APP_NAME) \
		$(PLATFORM_FLAGS) \
		$(NUITKA_ARGS) \
		$(ENTRY)
	@test -x "$(BIN)" || { echo "Build finished but $(BIN) is missing."; exit 1; }
	@echo "Standalone app: $(STOCK_DIR)"

bundle-libs: build ## Linux: copy xcb libs Nuitka does not bundle
	@test "$(OS)" = "linux" || { echo "bundle-libs is Linux only."; exit 1; }
	@for lib in libxcb-cursor.so.0; do \
		src=""; \
		for d in /usr/lib/*-linux-gnu /usr/lib64 /usr/lib; do \
			if [ -f "$$d/$$lib" ]; then src="$$d/$$lib"; break; fi; \
		done; \
		if [ -z "$$src" ]; then src="packaging/linux/lib/$$lib"; fi; \
		if [ -f "$$src" ]; then \
			cp -a "$$src" "$(STOCK_DIR)/$$lib"; \
			echo "Bundled $$lib from $$src"; \
		else \
			echo "WARNING: $$lib not found; the AppImage may fail on xcb."; \
		fi; \
	done

appimage: bundle-libs ## Linux: build the AppImage
	@test "$(OS)" = "linux" || { echo "AppImage is Linux only."; exit 1; }
	bash packaging/linux/build_appimage.sh $(VERSION) "$(STOCK_DIR)" "$(DIST_DIR)"

deb: bundle-libs ## Linux: build the .deb
	@test "$(OS)" = "linux" || { echo "deb is Linux only."; exit 1; }
	bash packaging/linux/build_deb.sh $(VERSION) "$(STOCK_DIR)" "$(DIST_DIR)"

dmg: build ## macOS: build the DMG
	@test "$(OS)" = "macos" || { echo "DMG is macOS only."; exit 1; }
	bash packaging/macos/build_dmg.sh $(VERSION) "$(STOCK_DIR)" "$(DIST_DIR)"

installer: build ## Windows: build the setup EXE (requires Inno Setup)
	@test "$(OS)" = "windows" || { echo "Installer is Windows only."; exit 1; }
	iscc /DMyAppVersion=$(VERSION) packaging/windows/rattracker.iss

dist: ## Compile the app and put installers in dist/
ifeq ($(OS),linux)
	@$(MAKE) --no-print-directory deb appimage
else ifeq ($(OS),macos)
	@$(MAKE) --no-print-directory dmg
else
	@$(MAKE) --no-print-directory installer
endif
	@echo "Installers are in $(DIST_DIR)/"
	@find $(DIST_DIR) -maxdepth 1 -type f | sed 's/^/  /'

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------
clean: ## Remove build files
	rm -rf $(BUILD_DIR) $(DIST_DIR) __pycache__ tracker/__pycache__ ui/__pycache__ tests/__pycache__
	@find . -type d -name __pycache__ \
		-not -path './$(VENV)/*' \
		-exec rm -rf {} + 2>/dev/null || true
