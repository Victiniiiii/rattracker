import cv2
import numpy as np
import csv
import math
import json
import argparse
import shutil
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

# ─────────────────────────────────────────────
# DEFAULT CONFIG
# ─────────────────────────────────────────────
DEFAULTS = {
    "mog2_history":       120,
    "mog2_threshold":     20,        # ↓ was 40 - more sensitive to low-contrast rats
    "mog2_detect_shadow": False,
    "morph_open_k":       3,
    "morph_close_k":      15,
    "min_contour_area":   300,
    "max_contour_area":   12000,
    "trail_len":          40,
    "debug_frames":       0,
    "pool_radius_cm":     60,
    "pool_nw":            None,
    "pool_ne":            None,
    "pool_sw":            None,
    "pool_se":            None,
    # ── CLAHE ──────────────────────────────────
    "clahe_clip_limit":   2.0,       # contrast amplification ceiling per tile
    "clahe_tile_size":    8,         # grid tile size (NxN); smaller = more local
    # ── Nearest-neighbour gating ───────────────
    "max_jump_px":        80,        # reject detections farther than this from last pos
    "gate_warmup_frames": 10,        # frames before gating activates (lets MOG2 settle)
}

CONFIG_FILE = Path(__file__).parent / "config.json"
OUTPUT_DIR  = Path(__file__).parent / "output"

QUADRANT_NAMES  = ["NE", "NW", "SW", "SE"]
QUADRANT_COLORS = {
    "NE": (0,   200, 255),
    "NW": (0,   255, 100),
    "SW": (255, 180,   0),
    "SE": (180,   0, 255),
}

### Font setup

def fix_opencv_qt_fonts():
    cv2_dir = Path(cv2.__file__).resolve().parent
    qt_fonts_dir = cv2_dir / "qt" / "fonts"

    qt_fonts_dir.mkdir(parents=True, exist_ok=True)

    bundled_font = Path(__file__).resolve().parent / "assets" / "edosz.ttf"

    if not bundled_font.exists():
        raise FileNotFoundError(f"Missing font: {bundled_font}")

    target_font = qt_fonts_dir / bundled_font.name

    if not target_font.exists():
        shutil.copy2(bundled_font, target_font)

def put_ttf_text(img, text, pos, color, size=22):
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    font_path = Path(__file__).resolve().parent / "assets" / "edosz.ttf"
    font = ImageFont.truetype(str(font_path), size)

    draw.text(pos, text, font=font, fill=(color[2], color[1], color[0]))

    return cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)


fix_opencv_qt_fonts()

# ─────────────────────────────────────────────
# CONFIG I/O
# ─────────────────────────────────────────────

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            # Merge with DEFAULTS so new keys always have a value
            cfg = {**DEFAULTS, **saved}
            for key in ("pool_nw", "pool_ne", "pool_sw", "pool_se"):
                if cfg[key] is not None:
                    cfg[key] = tuple(cfg[key])
            print(f"Config loaded from {CONFIG_FILE}")
            return cfg
        except Exception as e:
            print(f"Warning: could not read config.json ({e}). Using defaults.")
    return dict(DEFAULTS)


def save_config(cfg: dict):
    serialisable = {}
    for k, v in cfg.items():
        serialisable[k] = list(v) if isinstance(v, tuple) else v
    with open(CONFIG_FILE, "w") as f:
        json.dump(serialisable, f, indent=2)
    print(f"Config saved to {CONFIG_FILE}")


def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_nw", "pool_ne", "pool_sw", "pool_se"))


# ─────────────────────────────────────────────
# POOL CALIBRATION  (rectangle - 4 corners)
# ─────────────────────────────────────────────

CALIB_STEPS = [
    ("NW", "Click the TOP-LEFT     (NW) corner of the pool"),
    ("NE", "Click the TOP-RIGHT    (NE) corner of the pool"),
    ("SW", "Click the BOTTOM-LEFT  (SW) corner of the pool"),
    ("SE", "Click the BOTTOM-RIGHT (SE) corner of the pool"),
]

CALIB_COLORS = {
    "NW": ( 50, 205,  50),
    "NE": (  0, 200, 255),
    "SW": (255, 140,   0),
    "SE": (180,   0, 255),
}


def run_calibration(frame: np.ndarray) -> dict | None:
    state = {
        "step":   0,
        "points": {},
        "frame":  frame.copy(),
    }

    window = "Pool Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    def draw(base):
        img = base.copy()
        cv2.rectangle(img, (0, 0), (frame.shape[1], 70), (0, 0, 0), -1)

        step = state["step"]
        if step < len(CALIB_STEPS):
            corner, instruction = CALIB_STEPS[step]
            color = CALIB_COLORS[corner]
            img = put_ttf_text(img, f"Step {step + 1}/4 - {instruction}", (12, 8), color, 20)
            img = put_ttf_text(img, "Press  R  to redo all points   -   ESC to abort", (12, 44), (180, 180, 180), 15)
        else:
            img = put_ttf_text(img, "All 4 corners set - press ENTER to confirm or R to redo", (12, 12), (100, 255, 180), 19)
            img = put_ttf_text(img, "Press  ESC  to abort without saving", (12, 44), (180, 180, 180), 15)

        for corner, pt in state["points"].items():
            col = CALIB_COLORS[corner]
            cv2.circle(img, pt, 7, col, -1)
            cv2.circle(img, pt, 9, (255, 255, 255), 1)
            img = put_ttf_text(img, corner, (pt[0] + 11, pt[1] + 5), col, 15)

        if len(state["points"]) == 4:
            p = state["points"]
            pts = np.array([p["NW"], p["NE"], p["SE"], p["SW"]], dtype=np.int32)
            cv2.polylines(img, [pts], isClosed=True, color=(100, 255, 180), thickness=2)
            cx, cy = pool_centre_from_corners(p["NW"], p["NE"], p["SW"], p["SE"])
            cv2.circle(img, (cx, cy), 5, (100, 255, 180), -1)
            cv2.line(img, (p["NW"][0], cy), (p["NE"][0], cy), (100, 255, 180), 1)
            cv2.line(img, (cx, p["NW"][1]), (cx, p["SW"][1]), (100, 255, 180), 1)

        return img

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        step = state["step"]
        if step >= len(CALIB_STEPS):
            return
        corner, _ = CALIB_STEPS[step]
        state["points"][corner] = (x, y)
        state["step"] += 1
        print(f"  {corner}: ({x}, {y})")
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    print("\n── Pool Calibration (Rectangle) ──────────────────")
    print("Click the 4 corners of the rectangular pool.")
    print("Order: NW - NE - SW - SE")
    print("R = redo all   |   ENTER = confirm   |   ESC = abort")
    print("──────────────────────────────────────────────────\n")

    result = None
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            print("Calibration aborted.")
            break
        elif key in (ord('r'), ord('R')):
            state["step"]   = 0
            state["points"] = {}
            cv2.imshow(window, draw(state["frame"]))
            print("Points cleared - starting over.")
        elif key in (13, 10):
            if state["step"] == 4:
                p = state["points"]
                result = {
                    "pool_nw": p["NW"],
                    "pool_ne": p["NE"],
                    "pool_sw": p["SW"],
                    "pool_se": p["SE"],
                }
                print("Calibration confirmed.")
                break
            else:
                print(f"Please click {4 - state['step']} more corner(s) before confirming.")
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    return result


# ─────────────────────────────────────────────
# GEOMETRY HELPERS
# ─────────────────────────────────────────────

def pool_centre_from_corners(nw, ne, sw, se):
    cx = int(round((nw[0] + ne[0] + sw[0] + se[0]) / 4))
    cy = int(round((nw[1] + ne[1] + sw[1] + se[1]) / 4))
    return cx, cy


def pool_rect_bounds(nw, ne, sw, se):
    x_min = min(nw[0], ne[0], sw[0], se[0])
    x_max = max(nw[0], ne[0], sw[0], se[0])
    y_min = min(nw[1], ne[1], sw[1], se[1])
    y_max = max(nw[1], ne[1], sw[1], se[1])
    cx = int(round((x_min + x_max) / 2))
    cy = int(round((y_min + y_max) / 2))
    rx = int(round((x_max - x_min) / 2))
    ry = int(round((y_max - y_min) / 2))
    return cx, cy, rx, ry, x_min, x_max, y_min, y_max


def make_rect_mask(shape, x_min, x_max, y_min, y_max):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.rectangle(mask, (x_min, y_min), (x_max, y_max), 255, -1)
    return mask


def point_in_rect(x, y, x_min, x_max, y_min, y_max) -> bool:
    return x_min <= x <= x_max and y_min <= y <= y_max


def euclidean_px(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def euclidean_cm(p1, p2, scale_x: float, scale_y: float) -> float:
    dx = (p2[0] - p1[0]) * scale_x
    dy = (p2[1] - p1[1]) * scale_y
    return math.sqrt(dx ** 2 + dy ** 2)


def get_quadrant(x, y, cx, cy) -> str:
    if x >= cx and y < cy:
        return "NE"
    elif x < cx and y < cy:
        return "NW"
    elif x < cx and y >= cy:
        return "SW"
    else:
        return "SE"


def segment_quadrant_splits(p1, p2, cx, cy):
    x1, y1 = p1
    x2, y2 = p2
    dx = x2 - x1
    dy = y2 - y1

    t_vals = [0.0, 1.0]

    if dx != 0:
        t = (cx - x1) / dx
        if 0.0 < t < 1.0:
            t_vals.append(t)

    if dy != 0:
        t = (cy - y1) / dy
        if 0.0 < t < 1.0:
            t_vals.append(t)

    t_vals = sorted(set(t_vals))

    splits = []
    for i in range(len(t_vals) - 1):
        t_a = t_vals[i]
        t_b = t_vals[i + 1]
        xa = x1 + t_a * dx
        ya = y1 + t_a * dy
        xb = x1 + t_b * dx
        yb = y1 + t_b * dy
        xm = (xa + xb) / 2
        ym = (ya + yb) / 2
        q  = get_quadrant(xm, ym, cx, cy)
        splits.append(((xa, ya), (xb, yb), q))

    return splits


# ─────────────────────────────────────────────
# QUADRANT STATS ACCUMULATOR
# ─────────────────────────────────────────────

def empty_quadrant_stats():
    return {q: {"time_s": 0.0, "dist_cm": 0.0} for q in QUADRANT_NAMES}


def accumulate_segment(stats, p1, p2, cx, cy, frame_dt, scale_x, scale_y):
    total_dist_px = euclidean_px(p1, p2)
    splits = segment_quadrant_splits(p1, p2, cx, cy)

    for (sa, sb, q) in splits:
        sub_dist_px = euclidean_px(sa, sb)
        if total_dist_px > 0:
            frac = sub_dist_px / total_dist_px
        else:
            frac = 1.0 if splits.index((sa, sb, q)) == 0 else 0.0

        stats[q]["time_s"]  += frac * frame_dt
        stats[q]["dist_cm"] += euclidean_cm(sa, sb, scale_x, scale_y)


def accumulate_static(stats, pos, cx, cy, frame_dt):
    q = get_quadrant(pos[0], pos[1], cx, cy)
    stats[q]["time_s"] += frame_dt


# ─────────────────────────────────────────────
# ON-SCREEN LEADERBOARD RENDERER
# ─────────────────────────────────────────────

def draw_leaderboard(img, stats, total_time_s, total_dist_cm):
    sorted_q = sorted(QUADRANT_NAMES,
                      key=lambda q: stats[q]["time_s"], reverse=True)

    panel_w  = 310
    row_h    = 22
    pad      = 8
    n_rows   = len(QUADRANT_NAMES)
    header_h = 24
    panel_h  = header_h + n_rows * row_h + pad

    x0 = img.shape[1] - panel_w - 8
    y0 = 8
    x1 = x0 + panel_w
    y1 = y0 + panel_h

    overlay = img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (10, 10, 10), -1)
    cv2.addWeighted(overlay, 0.72, img, 0.28, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (80, 80, 80), 1)

    cv2.putText(img, "QUADRANT LEADERBOARD",
                (x0 + pad, y0 + 16),
                cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1, cv2.LINE_AA)

    for rank, q in enumerate(sorted_q):
        t_s   = stats[q]["time_s"]
        d_cm  = stats[q]["dist_cm"]
        t_pct = (t_s  / total_time_s  * 100) if total_time_s  > 0 else 0.0
        d_pct = (d_cm / total_dist_cm * 100) if total_dist_cm > 0 else 0.0
        color = QUADRANT_COLORS[q]

        row_y = y0 + header_h + rank * row_h + row_h - 4

        cv2.putText(img, f"#{rank+1} {q}",
                    (x0 + pad, row_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1, cv2.LINE_AA)
        cv2.putText(img, f"T:{t_s:5.1f}s {t_pct:4.1f}%",
                    (x0 + pad + 52, row_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(img, f"D:{d_cm:6.1f}cm {d_pct:4.1f}%",
                    (x0 + pad + 166, row_y),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 200, 50), 1, cv2.LINE_AA)


# ─────────────────────────────────────────────
# PREPROCESSING
# ─────────────────────────────────────────────

def make_clahe(cfg: dict) -> cv2.CLAHE:
    """Create a CLAHE object from config parameters."""
    tile = cfg["clahe_tile_size"]
    return cv2.createCLAHE(
        clipLimit    = cfg["clahe_clip_limit"],
        tileGridSize = (tile, tile),
    )


def preprocess_frame(gray: np.ndarray, clahe: cv2.CLAHE) -> np.ndarray:
    """
    Apply preprocessing to a grayscale frame before feeding MOG2.

    Pipeline:
      1. Gaussian blur  - suppresses compression noise / sensor grain
      2. CLAHE          - locally boosts contrast so rat stands out from water
    """
    blurred = cv2.GaussianBlur(gray, (5, 5), 0)
    enhanced = clahe.apply(blurred)
    return enhanced


# ─────────────────────────────────────────────
# NEAREST-NEIGHBOUR GATING
# ─────────────────────────────────────────────

def gate_detection(candidate, prev_pos, frame_idx: int, cfg: dict):
    """
    Accept or reject a raw detection based on proximity to the last
    known position.

    Rules:
    - During warmup (frame_idx < gate_warmup_frames): always accept.
      MOG2 hasn't built a stable background model yet so candidates
      are unreliable - gating them would discard real first detections.
    - If no previous position exists: accept (establishes first lock).
    - If distance from prev_pos > max_jump_px: reject (return None).
      A rat can only move so far between frames; big jumps are noise.
    - Otherwise: accept.

    Returns the candidate unchanged if accepted, None if rejected.
    """
    if candidate is None:
        return None

    if frame_idx < cfg["gate_warmup_frames"]:
        return candidate

    if prev_pos is None:
        return candidate

    dist = euclidean_px(prev_pos, candidate)
    if dist > cfg["max_jump_px"]:
        return None

    return candidate


# ─────────────────────────────────────────────
# RAT DETECTION
# ─────────────────────────────────────────────

def detect_rat(frame, subtractor, clahe, cfg, pool_mask=None, pool_bounds=None, frame_idx=0):
    """
    Detect rat centroid in a single frame.

    Changes vs original:
    - Accepts a pre-built CLAHE object and applies preprocessing before MOG2.
    - Candidate scoring: blobs are ranked by area * proximity_bonus so that
      a large blob far from centre doesn't beat a smaller blob that is closer
      to the last known position (proximity_bonus is not used here - that
      logic lives in the gating layer above - but area-only is kept as before
      since gating handles the jump problem separately).
    """
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    # ── Preprocessing ──────────────────────────────────────────────────────
    enhanced = preprocess_frame(frame, clahe)

    # ── Background subtraction ─────────────────────────────────────────────
    fg_mask = subtractor.apply(enhanced)

    if pool_mask is not None:
        fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=pool_mask)

    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (cfg["morph_open_k"],  cfg["morph_open_k"]))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                        (cfg["morph_close_k"], cfg["morph_close_k"]))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  k_open)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k_close)

    if cfg["debug_frames"] > 0 and frame_idx < cfg["debug_frames"]:
        cv2.imwrite(f"debug_frame_{frame_idx:03d}_fg.png",       fg_mask)
        cv2.imwrite(f"debug_frame_{frame_idx:03d}_enhanced.png", enhanced)

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
        if pool_bounds is not None:
            x_min, x_max, y_min, y_max = pool_bounds
            if not point_in_rect(bx, by, x_min, x_max, y_min, y_max):
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

    cfg = load_config()

    cap          = cv2.VideoCapture(str(video_path))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 4.0
    frame_h      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_dt     = 1.0 / fps

    print(f"Video : {video_path.name} | {frame_w}x{frame_h} | "
          f"FPS: {fps:.2f} | Frames: {total_frames}")

    ret, first_frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read first frame from video.")

    if not pool_coords_valid(cfg):
        print("\nNo pool coordinates found - opening calibration window...")
        result = run_calibration(first_frame)
        if result is None:
            raise RuntimeError("Pool calibration is required. Please re-run and complete calibration.")
        cfg.update(result)
        save_config(cfg)
    else:
        print("Pool coordinates loaded from config - skipping calibration.")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    # ── Pool rectangle + scale factors ──
    cx, cy, rx, ry, x_min, x_max, y_min, y_max = pool_rect_bounds(
        cfg["pool_nw"], cfg["pool_ne"], cfg["pool_sw"], cfg["pool_se"]
    )
    pool_bounds = (x_min, x_max, y_min, y_max)
    pool_mask   = make_rect_mask((frame_h, frame_w), x_min, x_max, y_min, y_max)
    r_cm        = cfg["pool_radius_cm"]
    scale_x     = r_cm / rx
    scale_y     = r_cm / ry

    print(f"Pool radius (ref): {r_cm} cm")
    print(f"Pool rectangle  - centre=({cx},{cy}), half_w={rx}px, half_h={ry}px")
    print(f"Bounds          - x:[{x_min},{x_max}]  y:[{y_min},{y_max}]")
    print(f"Scale factors   - x: {scale_x:.4f} cm/px  |  y: {scale_y:.4f} cm/px")
    print(f"CLAHE           - clip={cfg['clahe_clip_limit']}  tile={cfg['clahe_tile_size']}x{cfg['clahe_tile_size']}")
    print(f"Gating          - max_jump={cfg['max_jump_px']}px  warmup={cfg['gate_warmup_frames']} frames")

    OUTPUT_DIR.mkdir(exist_ok=True)
    video_out = OUTPUT_DIR / (video_path.stem + "_tracked.mp4")
    fourcc    = cv2.VideoWriter_fourcc(*"mp4v")
    writer    = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )

    # ── CLAHE instance (shared across frames) ──
    clahe = make_clahe(cfg)

    # ── Tracking state ──
    records         = []
    trail           = []
    frame_idx       = 0
    running_dist_px = 0.0
    running_dist_cm = 0.0
    prev_pos        = None
    gated_count     = 0   # how many frames were rejected by gating (for summary)

    q_stats = empty_quadrant_stats()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamp = frame_idx / fps

        # ── Raw detection ──────────────────────────────────────────────────
        raw_pos = detect_rat(gray, subtractor, clahe, cfg,
                             pool_mask, pool_bounds, frame_idx)

        # ── Nearest-neighbour gating ───────────────────────────────────────
        pos = gate_detection(raw_pos, prev_pos, frame_idx, cfg)
        if raw_pos is not None and pos is None:
            gated_count += 1

        if pos and prev_pos:
            d_px = euclidean_px(prev_pos, pos)
            running_dist_px += d_px
            running_dist_cm += euclidean_cm(prev_pos, pos, scale_x, scale_y)
            accumulate_segment(q_stats, prev_pos, pos, cx, cy,
                               frame_dt, scale_x, scale_y)
        elif pos and prev_pos is None:
            accumulate_static(q_stats, pos, cx, cy, frame_dt)
        elif pos and prev_pos == pos:
            accumulate_static(q_stats, pos, cx, cy, frame_dt)

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

        # ── Pool rectangle + quadrant dividers ──
        cv2.rectangle(annotated, (x_min, y_min), (x_max, y_max), (255, 100, 0), 2)
        cv2.line(annotated, (cx, y_min), (cx, y_max), (255, 100, 0), 1)
        cv2.line(annotated, (x_min, cy), (x_max, cy), (255, 100, 0), 1)
        for pt in [cfg["pool_nw"], cfg["pool_ne"], cfg["pool_sw"], cfg["pool_se"], (cx, cy)]:
            cv2.circle(annotated, pt, 5, (255, 100, 0), -1)
            cv2.circle(annotated, pt, 6, (255, 255, 255), 1)

        q_label_positions = {
            "NE": (cx + rx // 2, cy - ry // 2),
            "NW": (cx - rx // 2, cy - ry // 2),
            "SW": (cx - rx // 2, cy + ry // 2),
            "SE": (cx + rx // 2, cy + ry // 2),
        }
        for q, lp in q_label_positions.items():
            cv2.putText(annotated, q, lp,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, QUADRANT_COLORS[q], 1, cv2.LINE_AA)

        # Trail
        if pos:
            trail.append(pos)
        if len(trail) > cfg["trail_len"]:
            trail.pop(0)
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            color = (0, int(255 * alpha), int(100 * (1 - alpha)))
            cv2.line(annotated, trail[i - 1], trail[i], color, 2)

        # Rat dot - green ring if gated (rejected raw pos), normal otherwise
        if pos:
            cv2.circle(annotated, pos, 8,  (0, 0, 255), -1)
            cv2.circle(annotated, pos, 10, (255, 255, 255), 1)
        if raw_pos and pos is None:
            # Show where the gated-out candidate was (dim orange)
            cv2.circle(annotated, raw_pos, 8,  (0, 140, 255), 1)

        # ── HUD (top-left) ──
        status    = "DETECTED" if pos else ("GATED" if raw_pos else "MISSING")
        hud_color = (0, 210, 0) if pos else ((0, 140, 255) if raw_pos else (0, 0, 210))
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        hud_dist  = f"{running_dist_px:.1f} px  |  {running_dist_cm:.1f} cm"
        cv2.rectangle(annotated, (5, 5), (340, 100), (0, 0, 0), -1)
        cv2.putText(annotated, f"Frame: {frame_idx:>4}   t = {timestamp:.2f}s",
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(annotated, f"Position: {pos_str}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(annotated, status,
                    (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, hud_color, 1, cv2.LINE_AA)
        cv2.putText(annotated, f"Dist: {hud_dist}",
                    (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 50), 1, cv2.LINE_AA)

        # ── Leaderboard (top-right) ──
        total_q_time = sum(v["time_s"]  for v in q_stats.values())
        total_q_dist = sum(v["dist_cm"] for v in q_stats.values())
        draw_leaderboard(annotated, q_stats, total_q_time, total_q_dist)

        writer.write(annotated)
        frame_idx += 1

    cap.release()
    writer.release()

    detected = sum(1 for r in records if r["x"] is not None)
    print(f"\nProcessed {frame_idx} frames.")
    print(f"Detected (post-gate): {detected} frames")
    print(f"Gated out (jumps):    {gated_count} frames")
    print(f"Annotated video - {video_out}")

    # ── Interpolation ──
    records       = interpolate_missing(records)
    missing_after = sum(1 for r in records if r["x"] is None)
    if missing_after:
        print(f"Warning: {missing_after} frame(s) have no position after interpolation.")

    # ── Recalculate final distances + quadrant stats from interpolated records ──
    total_dist_px = 0.0
    total_dist_cm = 0.0
    valid_pairs   = 0
    prev          = None

    q_stats_final = empty_quadrant_stats()

    for rec in records:
        if rec["x"] is not None:
            curr = (rec["x"], rec["y"])
            if prev is not None:
                total_dist_px += euclidean_px(prev, curr)
                total_dist_cm += euclidean_cm(prev, curr, scale_x, scale_y)
                accumulate_segment(q_stats_final, prev, curr, cx, cy,
                                   frame_dt, scale_x, scale_y)
                valid_pairs += 1
            else:
                accumulate_static(q_stats_final, curr, cx, cy, frame_dt)
            prev = curr

    total_q_time = sum(v["time_s"]  for v in q_stats_final.values())
    total_q_dist = sum(v["dist_cm"] for v in q_stats_final.values())

    # ── CSV ──
    csv_path = OUTPUT_DIR / f"{video_path.stem}_coordinates.csv"
    with open(csv_path, "w", newline="") as f:
        writer_csv = csv.DictWriter(
            f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)
    print(f"Coordinates saved - {csv_path}")

    # ── Summary ──
    sorted_q = sorted(QUADRANT_NAMES,
                      key=lambda q: q_stats_final[q]["time_s"], reverse=True)

    summary_path = OUTPUT_DIR / f"{video_path.stem}_summary.txt"
    with open(summary_path, "w") as f:
        lines = [
            f"Video           : {video_path.name}",
            f"Resolution      : {frame_w}x{frame_h}",
            f"Total frames    : {frame_idx}",
            f"FPS             : {fps:.2f}",
            f"Duration (s)    : {frame_idx / fps:.2f}",
            f"",
            f"Detected frames : {detected}",
            f"Gated out       : {gated_count}",
            f"Interpolated    : {sum(1 for r in records if r['interpolated'])}",
            f"Missing (no pos): {missing_after}",
            f"",
            f"Pool radius (ref): {cfg['pool_radius_cm']} cm",
            f"Scale X         : {scale_x:.4f} cm/px  (horizontal)",
            f"Scale Y         : {scale_y:.4f} cm/px  (vertical)",
            f"CLAHE clip      : {cfg['clahe_clip_limit']}",
            f"CLAHE tile      : {cfg['clahe_tile_size']}x{cfg['clahe_tile_size']}",
            f"Max jump (gate) : {cfg['max_jump_px']} px",
            f"",
            f"Total distance  : {total_dist_px:.2f} px",
            f"Total distance  : {total_dist_cm:.2f} cm",
            f"  (over {valid_pairs} consecutive frame pairs)",
            f"",
            f"── Quadrant Analysis (sorted by time spent) ─────────────────",
            f"{'Quadrant':<10} {'Time (s)':>10} {'Time (%)':>10} {'Dist (cm)':>12} {'Dist (%)':>10}",
            f"{'-'*56}",
        ]
        for q in sorted_q:
            t_s   = q_stats_final[q]["time_s"]
            d_cm  = q_stats_final[q]["dist_cm"]
            t_pct = (t_s  / total_q_time * 100) if total_q_time > 0 else 0.0
            d_pct = (d_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
            lines.append(
                f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%"
            )
        lines += [
            f"{'-'*56}",
            f"{'TOTAL':<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%",
        ]
        f.write("\n".join(lines))

    print(f"Summary saved   - {summary_path}")

    print(f"\n── Results ───────────────────────────────────────")
    print(f"Total distance  : {total_dist_px:.2f} px")
    print(f"Total distance  : {total_dist_cm:.2f} cm")
    print(f"\n── Quadrant Analysis (sorted by time spent) ─────")
    print(f"{'Quadrant':<10} {'Time (s)':>10} {'Time (%)':>10} {'Dist (cm)':>12} {'Dist (%)':>10}")
    print(f"{'-'*56}")
    for q in sorted_q:
        t_s   = q_stats_final[q]["time_s"]
        d_cm  = q_stats_final[q]["dist_cm"]
        t_pct = (t_s  / total_q_time * 100) if total_q_time > 0 else 0.0
        d_pct = (d_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
        print(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%")
    print(f"{'-'*56}")
    print(f"{'TOTAL':<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%")
    print(f"──────────────────────────────────────────────────")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Track a rat in a rectangular pool video.")
    parser.add_argument("--video", required=True,
                        help="Path to the input video file")
    args = parser.parse_args()
    main(args.video)