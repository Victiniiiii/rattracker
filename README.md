# Morris Water Maze Analysis

Desktop app that tracks a rat in a water maze video and saves the results next to the video.

The interface is Qt Widgets. The tracking pipeline is Python + OpenCV. The GUI
starts the same executable with `--backend`, so a build ships one program, one
copy of OpenCV, and no web view or local HTTP server.

## Install

Pick the file for your computer:

| System | File | How to install |
|---|---|---|
| Windows | `-setup.exe` | Double-click and follow the installer |
| macOS | `.dmg` | Open it and drag the app to **Applications** |
| Linux | `.AppImage` | Make it executable, then double-click |
| Linux | `.deb` | Double-click, or run `sudo apt install ./file.deb` |

For the Linux AppImage, if double-clicking does nothing, run it once from a terminal:

```bash
chmod +x rattracker_*.AppImage
./rattracker_*.AppImage
```

macOS builds are unsigned. If Gatekeeper blocks the app, right-click it, choose **Open**, then confirm.

## Use

1. Open the app.
2. Click **Select Video** and choose your video.
3. Click **Run**.
4. A preview opens. Click the **4 edges of the pool** (west, north, east, south), then click **Confirm**.
5. Wait for it to finish. The results open in tabs: **Video**, **CSV**, **Summary**, **Tracemap**, **Heatmap**.

Everything is also saved next to your video:

- `*_summary.txt` - the main numbers
- `*_coordinates.csv` - position on every frame
- `*_tracemap.jpg` - the swim path
- `*_heatmap.jpg` - time spent in each area
- `*.mp4` - the video with tracking drawn on it

## Settings

Open the gear icon to turn extra analyses on or off (quadrant crossings, platform crossings, proximity, latency, colours, detection settings).

- Platform features also need the **4 platform corners**. You will be asked to click them after the pool.
- The app remembers your pool and platform points, so the next video from the same camera setup runs without clicking.
- Profiles are stored as JSON in the platform config directory. Share and import use the same `--flag value` string as earlier versions.
- If tracking misses the rat or picks up noise, click **Auto-Configure Detection**, then run again.

## Compile the app

Requirements: Python 3.12, GNU Make, and a C compiler. Node.js and Rust are
not needed.

```bash
make install    # once: install Python, Qt runtime libraries, and dependencies
make run        # open the app from source
make test       # headless test suite
make build      # standalone app in build/
make smoke      # run the compiled app end to end
make dist       # installers in dist/
```

`make install` sets up a virtual environment and installs
`PySide6-Essentials`, `opencv-python-headless`, `numpy`, and `nuitka`.

`make dist` builds the installer for the computer you compile on:

- Windows: `morriswatermazeanalysis_*_amd64-setup.exe` (needs [Inno Setup](https://jrsoftware.org/isinfo.php))
- macOS: `rattracker_*.dmg`
- Linux: `rattracker_*.deb` and `rattracker_*.AppImage`

Useful single targets:

```bash
make build          # Nuitka standalone directory
make smoke          # run the compiled app end to end
make appimage       # Linux only, faster than make dist
make deb            # Linux only
make dmg            # macOS only
make installer      # Windows only
```

To run the tracker from the terminal without the GUI:

```bash
make cli VIDEO=input/1.mp4 ARGS="--pool_west 274,128 --pool_north 665,92 --pool_east 730,382 --pool_south 349,443"
```

The terminal path needs pool points because the installed OpenCV build is
headless. Interactive calibration is a desktop-app feature.

## Tests

```bash
make test
```

The suite runs Qt with the offscreen platform. It checks config and share-string
round trips, both translations, calibration click mapping, the settings form,
argument building, byte-identical CSV/summary parity against a stored baseline,
and a full GUI-to-backend run on `tests/fixtures/1.mp4`.

`make smoke` builds the standalone app, launches it with the offscreen platform,
runs the fixture video through the real backend child process, and verifies the
CSV and summary were written.

Test-only automation hooks: `RATTRACKER_AUTOCONFIRM=1` answers calibration with
saved points, `RATTRACKER_AUTORUN=<video>` starts a run on launch,
`RATTRACKER_AUTOEXIT=1` closes after the run, `RATTRACKER_CONFIG_DIR=<dir>`
isolates the profile store, and `RATTRACKER_LOG=<file>` records backend traffic.
These are used by `make smoke` and CI.

## Continuous integration and verification status

`.github/workflows/build.yml` runs the tests, compiles the standalone app, runs
the frozen smoke test, and builds installers on Linux, Windows, and macOS,
uploading each platform's artifacts. The workflow has not yet run on a remote
CI host in this development environment (no `gh` CLI / hosted runners available
here), so treat the first push as the cross-platform proof point.

**Locally verified (Linux only, this host):**

- `make test` — 15 headless tests OK (config/share-string, i18n parity,
  calibration clicks + confirm + frozen E2E, backend byte-parity CSV/summary).
- `make smoke` — frozen `rattracker` runs the fixture video end to end.
- `make deb` / `make appimage` — `dist/rattracker_1.1.0_amd64.deb` (84M) and
  `dist/rattracker_1.1.0_x86_64.AppImage` (107M), extract-checked.

**NOT locally verified (scripts present, CI-only):**

- Windows `morriswatermazeanalysis_*_amd64-setup.exe` — `packaging/windows/rattracker.iss`
  (Inno Setup) plus Windows flags in `Makefile`. Never built on this Linux host;
  only YAML-validated and syntax-checked.
- macOS `rattracker_*.dmg` — `packaging/macos/build_dmg.sh` (`hdiutil create`)
  plus `--macos-create-app-bundle` in `Makefile`. Never built on this Linux host;
  only YAML-validated and `bash -n` syntax-checked.

Do not claim Windows/macOS completeness until a green CI run uploads those
artifacts.

## Project layout

```
app_qt.py          entry point: GUI, or --backend for the tracker
ui/                Qt Widgets interface
tracker/           tracking pipeline (unchanged)
tests/             headless tests and CSV/summary baseline
packaging/         Linux, macOS, Windows installer scripts
```

## Licence note

Qt is used through PySide6 under the LGPLv3. The build links Qt dynamically.
