# Morris Water Maze Analysis

Desktop app that tracks a rat in a water maze video and saves the results next to the video.

## Install

Pick the file for your computer:

| System | File | How to install |
|---|---|---|
| Windows | `.msi` or `-setup.exe` | Double-click and follow the installer |
| macOS | `.dmg` | Open it and drag the app to **Applications** |
| Linux | `.AppImage` | Make it executable, then double-click |
| Linux | `.deb` | Double-click, or run `sudo apt install ./file.deb` |

For the Linux AppImage, if double-clicking does nothing, run it once from a terminal:

```bash
chmod +x morriswatermazeanalysis_*.AppImage
./morriswatermazeanalysis_*.AppImage
```

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
- If tracking misses the rat or picks up noise, click **Auto-Configure Detection**, then run again.

## Compile the app

You only need this if you want to build the app yourself. Requirements: Python 3.12, Node.js 20, Rust, and GNU Make.

```bash
make install    # once: install everything needed
make dist       # compile the app and put the installers in dist/
```

On Linux, `make appimage` compiles **only** the AppImage (faster while developing).

`make dist` builds the installer for the computer you compile on:

- Windows: `.msi` or `-setup.exe`
- macOS: `.dmg`
- Linux: `.deb` and `.AppImage`

**Windows:** run these commands in **Git Bash** (install Git for Windows and GNU Make first). `make install` installs the rest with winget. PowerShell is not supported.

To run the tracker from the terminal without compiling the app:

```bash
make run VIDEO=input/1.mp4
```
