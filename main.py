import cv2
import numpy as np
import csv
import math
import json
import argparse
from pathlib import Path

# ─────────────────────────────────────────────
# DEFAULT CONFIG
# These values are used if no config.json exists.
# Once saved, config.json is the source of truth.
# ─────────────────────────────────────────────
DEFAULTS = {
    "mog2_history":       120,
    "mog2_threshold":     40,
    "mog2_detect_shadow": False,
    "morph_open_k":       3,
    "morph_close_k":      15,
    "min_contour_area":   300,
    "max_contour_area":   12000,
    "trail_len":          40,
    "debug_frames":       0,
    "pool_west":          None,
    "pool_north":         None,
    "pool_east":          None,
    "pool_south":         None,
}

CONFIG_FILE = Path(__file__).parent / "config.json"


# ─────────────────────────────────────────────
# CONFIG  I/O
# ─────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            # Merge: saved values override defaults,
            # but new keys added to DEFAULTS still appear.
            cfg = {**DEFAULTS, **saved}
            # Convert pool point lists back to tuples
            for key in ("pool_west", "pool_north", "pool_east", "pool_south"):
                if cfg[key] is not None:
                    cfg[key] = tuple(cfg[key])
            print(f"Config loaded from {CONFIG_FILE}")
            return cfg
        except Exception as e:
            print(f"Warning: could not read config.json ({e}). Using defaults.")
    return dict(DEFAULTS)


def save_config(cfg: dict):
    # Convert tuples to lists for JSON serialisation
    serialisable = {}
    for k, v in cfg.items():
        serialisable[k] = list(v) if isinstance(v, tuple) else v
    with open(CONFIG_FILE, "w") as f:
        json.dump(serialisable, f, indent=2)
    print(f"Config saved to {CONFIG_FILE}")


def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_west", "pool_north", "pool_east", "pool_south"))


# ─────────────────────────────────────────────
# POOL CALIBRATION  (cv2 interactive picker)
# ─────────────────────────────────────────────

CALIB_STEPS = [
    ("WEST",  "Click the WESTMOST  (left)   point of the pool edge"),
    ("NORTH", "Click the NORTHMOST (top)    point of the pool edge"),
    ("EAST",  "Click the EASTMOST  (right)  point of the pool edge"),
    ("SOUTH", "Click the SOUTHMOST (bottom) point of the pool edge"),
]

CALIB_COLORS = {
    "WEST":  (255, 140,   0),   # orange
    "NORTH": ( 50, 205,  50),   # lime
    "EAST":  ( 30, 144, 255),   # dodger blue
    "SOUTH": (238,  58, 140),   # deep pink
}


def run_calibration(frame: np.ndarray) -> dict | None:
    """
    Opens a cv2 window on `frame` and collects 4 pool boundary clicks.
    Returns dict with pool_west/north/east/south tuples, or None if aborted.
    """
    state = {
        "step":   0,
        "points": {},   # cardinal → (x, y)
        "frame":  frame.copy(),
    }

    window = "Pool Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    def draw(base):
        img = base.copy()
        # HUD panel background
        cv2.rectangle(img, (0, 0), (frame.shape[1], 70), (0, 0, 0), -1)

        step = state["step"]
        if step < len(CALIB_STEPS):
            cardinal, instruction = CALIB_STEPS[step]
            color = CALIB_COLORS[cardinal]
            cv2.putText(img, f"Step {step + 1}/4 — {instruction}",
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1)
            cv2.putText(img, "Press  R  to redo all points   |   ESC to abort",
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        else:
            cv2.putText(img, "All 4 points set — press ENTER to confirm or R to redo",
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
            cv2.putText(img, "Press  ESC  to abort without saving",
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)

        # Draw confirmed points
        for cardinal, pt in state["points"].items():
            col = CALIB_COLORS[cardinal]
            cv2.circle(img, pt, 7, col, -1)
            cv2.circle(img, pt, 9, (255, 255, 255), 1)
            cv2.putText(img, cardinal, (pt[0] + 11, pt[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)

        # Draw ellipse preview once all 4 points are set
        if len(state["points"]) == 4:
            p = state["points"]
            cx = (p["WEST"][0] + p["EAST"][0])  // 2
            cy = (p["NORTH"][1] + p["SOUTH"][1]) // 2
            rx = (p["EAST"][0] - p["WEST"][0])  // 2
            ry = (p["SOUTH"][1] - p["NORTH"][1]) // 2
            cv2.ellipse(img, (cx, cy), (rx, ry), 0, 0, 360, (100, 255, 180), 2)
            cv2.circle(img, (cx, cy), 5, (100, 255, 180), -1)

        return img

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        step = state["step"]
        if step >= len(CALIB_STEPS):
            return
        cardinal, _ = CALIB_STEPS[step]
        state["points"][cardinal] = (x, y)
        state["step"] += 1
        print(f"  {cardinal}: ({x}, {y})")
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    print("\n── Pool Calibration ──────────────────────────────")
    print("Click the 4 cardinal edge points of the pool.")
    print("Order: WEST → NORTH → EAST → SOUTH")
    print("R = redo all   |   ENTER = confirm   |   ESC = abort")
    print("──────────────────────────────────────────────────\n")

    result = None
    while True:
        key = cv2.waitKey(20) & 0xFF

        if key == 27:   # ESC — abort
            print("Calibration aborted.")
            break

        elif key in (ord('r'), ord('R')):   # Redo
            state["step"]   = 0
            state["points"] = {}
            cv2.imshow(window, draw(state["frame"]))
            print("Points cleared — starting over.")

        elif key in (13, 10):   # ENTER — confirm
            if state["step"] == 4:
                p = state["points"]
                result = {
                    "pool_west":  p["WEST"],
                    "pool_north": p["NORTH"],
                    "pool_east":  p["EAST"],
                    "pool_south": p["SOUTH"],
                }
                print("Calibration confirmed.")
                break
            else:
                remaining = 4 - state["step"]
                print(f"Please click {remaining} more point(s) before confirming.")

        # Redraw on every loop tick so the window stays responsive
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    return result


# ─────────────────────────────────────────────
# GEOMETRY HELPERS
# ─────────────────────────────────────────────

def pool_ellipse_from_nsew(west, north, east, south):
    cx = (west[0]  + east[0])  / 2
    cy = (north[1] + south[1]) / 2
    rx = (east[0]  - west[0])  / 2
    ry = (south[1] - north[1]) / 2
    return int(round(cx)), int(round(cy)), int(round(rx)), int(round(ry))


def make_ellipse_mask(shape, cx, cy, rx, ry):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    return mask


def point_in_ellipse(x, y, cx, cy, rx, ry) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def euclidean(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


# ─────────────────────────────────────────────
# RAT DETECTION
# ─────────────────────────────────────────────

def detect_rat(frame, subtractor, cfg, pool_mask=None, pool=None, frame_idx=0):
    fg_mask = subtractor.apply(frame)

    if pool_mask is not None:
        fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=pool_mask)

    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (cfg["morph_open_k"],  cfg["morph_open_k"]))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (cfg["morph_close_k"], cfg["morph_close_k"]))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  k_open)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k_close)

    if cfg["debug_frames"] > 0 and frame_idx < cfg["debug_frames"]:
        cv2.imwrite(f"debug_frame_{frame_idx:03d}.png", fg_mask)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best, best_area = None, 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < cfg["min_contour_area"] or area > cfg["max_contour_area"]:
            continue
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        bx = int(M["m10"] / M["m00"])
        by = int(M["m01"] / M["m00"])
        if pool is not None and not point_in_ellipse(bx, by, *pool):
            continue
        if area > best_area:
            best_area = area
            best = (bx, by)

    return best


# ─────────────────────────────────────────────
# INTERPOLATION
# ─────────────────────────────────────────────

def interpolate_missing(records: list) -> list:
    n      = len(records)
    result = list(records)
    i = 0
    while i < n:
        if result[i]["x"] is None:
            left = i - 1
            while left >= 0 and result[left]["x"] is None:
                left -= 1
            right = i
            while right < n and result[right]["x"] is None:
                right += 1
            if left >= 0 and right < n:
                x0, y0 = result[left]["x"],  result[left]["y"]
                x1, y1 = result[right]["x"], result[right]["y"]
                gap = right - left
                for j in range(left + 1, right):
                    t = (j - left) / gap
                    result[j]["x"]            = round(x0 + t * (x1 - x0), 2)
                    result[j]["y"]            = round(y0 + t * (y1 - y0), 2)
                    result[j]["interpolated"] = True
            i = right
        else:
            i += 1
    return result


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main(video_path: str):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    # ── Load config ──
    cfg = load_config()

    # ── Open video ──
    cap      = cv2.VideoCapture(str(video_path))
    fps      = cap.get(cv2.CAP_PROP_FPS) or 4.0
    frame_h  = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w  = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video : {video_path.name} | {frame_w}x{frame_h} | "
          f"FPS: {fps:.2f} | Frames: {total_frames}")

    ret, first_frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read first frame from video.")

    # ── Calibration (only if pool coords missing) ──
    if not pool_coords_valid(cfg):
        print("\nNo pool coordinates found — opening calibration window...")
        result = run_calibration(first_frame)
        if result is None:
            print("No pool boundary set. Tracking will use the full frame.")
        else:
            cfg.update(result)
            save_config(cfg)
    else:
        print("Pool coordinates loaded from config — skipping calibration.")

    # Reset video to beginning after reading first frame
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # ── Pool ellipse setup ──
    pool      = None
    pool_mask = None
    if pool_coords_valid(cfg):
        pool = pool_ellipse_from_nsew(
            cfg["pool_west"], cfg["pool_north"],
            cfg["pool_east"], cfg["pool_south"]
        )
        pool_mask = make_ellipse_mask((frame_h, frame_w), *pool)
        cx, cy, rx, ry = pool
        print(f"Pool ellipse → centre=({cx},{cy}), rx={rx}px, ry={ry}px")
    else:
        print("Pool boundary disabled — using full frame.")

    # ── Output paths ──
    out_dir   = video_path.parent
    video_out = out_dir / (video_path.stem + "_tracked.mp4")
    fourcc    = cv2.VideoWriter_fourcc(*"mp4v")
    writer    = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    # ── Background subtractor ──
    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )

    # ── Tracking loop ──
    records      = []
    trail        = []
    frame_idx    = 0
    running_dist = 0.0
    prev_pos     = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps
        pos       = detect_rat(frame, subtractor, cfg, pool_mask, pool, frame_idx)

        if pos and prev_pos:
            running_dist += euclidean(prev_pos, pos)
        if pos:
            prev_pos = pos

        records.append({
            "frame":        frame_idx,
            "timestamp_s":  round(timestamp, 4),
            "x":            pos[0] if pos else None,
            "y":            pos[1] if pos else None,
            "interpolated": False,
        })

        annotated = frame.copy()

        # Pool ellipse overlay
        if pool is not None:
            cx, cy, rx, ry = pool
            cv2.ellipse(annotated, (cx, cy), (rx, ry), 0, 0, 360, (255, 100, 0), 2)
            for pt in [(cx, cy), cfg["pool_west"], cfg["pool_north"],
                       cfg["pool_east"], cfg["pool_south"]]:
                cv2.circle(annotated, pt, 5, (255, 100, 0), -1)
                cv2.circle(annotated, pt, 6, (255, 255, 255), 1)

        # Trail
        if pos:
            trail.append(pos)
        if len(trail) > cfg["trail_len"]:
            trail.pop(0)
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            color = (0, int(255 * alpha), int(100 * (1 - alpha)))
            cv2.line(annotated, trail[i - 1], trail[i], color, 2)

        # Rat dot
        if pos:
            cv2.circle(annotated, pos, 8,  (0, 0, 255), -1)
            cv2.circle(annotated, pos, 10, (255, 255, 255), 1)

        # HUD
        status    = "DETECTED" if pos else "MISSING"
        hud_color = (0, 210, 0) if pos else (0, 0, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        cv2.rectangle(annotated, (5, 5), (300, 100), (0, 0, 0), -1)
        cv2.putText(annotated, f"Frame: {frame_idx:>4}   t = {timestamp:.2f}s",
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, f"Position: {pos_str}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, status,
                    (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, hud_color, 1)
        cv2.putText(annotated, f"Distance: {running_dist:.1f} px",
                    (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 50), 1)

        writer.write(annotated)
        frame_idx += 1

    cap.release()
    writer.release()

    detected = sum(1 for r in records if r["x"] is not None)
    print(f"\nProcessed {frame_idx} frames. Detected rat in {detected} frames.")
    print(f"Annotated video → {video_out}")

    # ── Interpolation ──
    records       = interpolate_missing(records)
    missing_after = sum(1 for r in records if r["x"] is None)
    if missing_after:
        print(f"Warning: {missing_after} frame(s) have no position "
              "(at start/end of video with no neighbours to interpolate from).")

    # ── CSV ──
    csv_path = out_dir / f"{video_path.stem}_coordinates.csv"
    with open(csv_path, "w", newline="") as f:
        writer_csv = csv.DictWriter(
            f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)
    print(f"Coordinates saved → {csv_path}")

    # ── Summary ──
    total_distance = 0.0
    valid_pairs    = 0
    prev           = None
    for rec in records:
        if rec["x"] is not None:
            curr = (rec["x"], rec["y"])
            if prev is not None:
                total_distance += euclidean(prev, curr)
                valid_pairs    += 1
            prev = curr

    summary_path = out_dir / f"{video_path.stem}_summary.txt"
    with open(summary_path, "w") as f:
        lines = [
            f"Video           : {video_path.name}",
            f"Resolution      : {frame_w}x{frame_h}",
            f"Total frames    : {frame_idx}",
            f"FPS             : {fps:.2f}",
            f"Duration (s)    : {frame_idx / fps:.2f}",
            f"",
            f"Detected frames : {detected}",
            f"Interpolated    : {sum(1 for r in records if r['interpolated'])}",
            f"Missing (no pos): {missing_after}",
            f"",
            f"Total distance swum : {total_distance:.2f} pixels",
            f"  (over {valid_pairs} consecutive frame pairs)",
            f"",
            f"Note: convert to real units using:",
            f"  scale (cm/px) = tank_real_diameter_cm / tank_diameter_in_pixels",
        ]
        f.write("\n".join(lines))

    print(f"Summary saved   → {summary_path}")
    print(f"\nTotal distance swum: {total_distance:.2f} pixels")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Track a rat in a water maze video.")
    parser.add_argument("--video", required=True,
                        help="Path to the input video file")
    args = parser.parse_args()
    main(args.video)