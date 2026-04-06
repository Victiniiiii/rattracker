import cv2
import numpy as np
import csv
import math
import json
import argparse
import time
from pathlib import Path

# DEFAULT CONFIG

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
    "pool_radius_cm":     60,
    "pool_west":          None,
    "pool_north":         None,
    "pool_east":          None,
    "pool_south":         None,
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


# CONFIG I/O

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            cfg = {**DEFAULTS, **saved}
            for key in ("pool_west", "pool_north", "pool_east", "pool_south"):
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
               for k in ("pool_west", "pool_north", "pool_east", "pool_south"))


# POOL CALIBRATION

CALIB_STEPS = [
    ("WEST",  "Click on the WEST point of the pool edge"),
    ("NORTH", "Click on the NORTH point of the pool edge"),
    ("EAST",  "Click on the EAST point of the pool edge"),
    ("SOUTH", "Click on the SOUTH point of the pool edge"),
]

CALIB_COLORS = {
    "WEST":  (255, 140, 0),
    "NORTH": (50, 205, 50),
    "EAST":  (30, 144, 255),
    "SOUTH": (238, 58, 140),
}


def draw_transparent_banner(img, x0, y0, x1, y1, alpha=0.72):
    overlay = img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (10, 10, 10), -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (80, 80, 80), 1)


def run_calibration(frame: np.ndarray, pool_radius_cm=None) -> dict | None:
    state = {"step": 0, "points": {}, "frame": frame.copy()}
    window = "Pool Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    def draw(base):
        img = base.copy()
        draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
        step = state["step"]
        if step < len(CALIB_STEPS):
            cardinal, instruction = CALIB_STEPS[step]
            color = CALIB_COLORS[cardinal]
            cv2.putText(img, f"Step {step + 1}/4 -- {instruction}", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1)
            cv2.putText(img, "Press  R  to redo all points   |   ESC to abort", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        else:
            cv2.putText(img, "All 4 points set -- press ENTER to confirm or R to redo", (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
            cv2.putText(img, "Press  ESC  to abort without saving", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)

        for cardinal, pt in state["points"].items():
            col = CALIB_COLORS[cardinal]
            cv2.circle(img, pt, 7, col, -1)
            cv2.circle(img, pt, 9, (255, 255, 255), 1)
            cv2.putText(img, cardinal, (pt[0] + 11, pt[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)

        if len(state["points"]) == 4:
            p = state["points"]
            result = pool_ellipse_from_nsew(p["WEST"], p["NORTH"], p["EAST"], p["SOUTH"])
            if result is not None:
                cx, cy, rx, ry, angle = result
                cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, (100, 255, 180), 2)
                cv2.circle(img, (cx, cy), 5, (100, 255, 180), -1)
                cv2.line(img, p["NORTH"], p["SOUTH"], (100, 255, 180), 1)
                cv2.line(img, p["WEST"],  p["EAST"],  (100, 255, 180), 1)

        return img

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN: return
        step = state["step"]
        if step >= len(CALIB_STEPS): return
        cardinal, _ = CALIB_STEPS[step]
        state["points"][cardinal] = (x, y)
        state["step"] += 1
        print(f"  {cardinal}: ({x}, {y})")
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    print("\n-- Pool Calibration ------------------------------------------")
    print("Click the 4 cardinal edge points of the pool.")
    print("Order: WEST -> NORTH -> EAST -> SOUTH")
    print("R = redo all   |   ENTER = confirm   |   ESC = abort")
    print("--------------------------------------------------------------\n")

    result = None
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            print("Calibration aborted.")
            break
        elif key in (ord('r'), ord('R')):
            state["step"] = 0
            state["points"] = {}
            cv2.imshow(window, draw(state["frame"]))
            print("Points cleared -- starting over.")
        elif key in (13, 10):
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
                print(f"Please click {4 - state['step']} more point(s) before confirming.")
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    return result

# GEOMETRY HELPERS

def pool_ellipse_from_nsew(west, north, east, south):
    cx = (west[0] + east[0] + north[0] + south[0]) / 4
    cy = (west[1] + east[1] + north[1] + south[1]) / 4

    r1x = east[0] - cx
    r1y = east[1] - cy
    r2x = north[0] - cx
    r2y = north[1] - cy

    M = np.array([
        [r1x*r1x + r2x*r2x, r1x*r1y + r2x*r2y],
        [r1x*r1y + r2x*r2y, r1y*r1y + r2y*r2y],
    ], dtype=np.float64)

    eigenvalues, eigenvectors = np.linalg.eigh(M)
    rx = int(round(math.sqrt(eigenvalues[1])))
    ry = int(round(math.sqrt(eigenvalues[0])))
    angle = math.degrees(math.atan2(eigenvectors[1, 1], eigenvectors[0, 1]))

    return int(round(cx)), int(round(cy)), rx, ry, angle


def make_ellipse_mask(shape, cx, cy, rx, ry, angle):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
    return mask


def point_in_ellipse(x, y, cx, cy, rx, ry, angle) -> bool:
    px = x - cx
    py = y - cy

    theta = -math.radians(angle)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)

    xr = px * cos_t - py * sin_t
    yr = px * sin_t + py * cos_t

    return (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0


def euclidean_px(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def euclidean_cm(p1, p2, scale_x, scale_y) -> float:
    dx_real = (p2[0] - p1[0]) * scale_x
    dy_real = (p2[1] - p1[1]) * scale_y
    return math.sqrt(dx_real**2 + dy_real**2)


def cross2d(ax, ay, bx, by) -> float:
    return ax * by - ay * bx


def get_quadrant(x, y, west, north, east, south) -> str:
    center = line_intersection(west, east, north, south)
    if center is None:
        return "UNKNOWN"

    cx, cy = center

    we_dx = east[0] - west[0]
    we_dy = east[1] - west[1]

    ns_dx = south[0] - north[0]
    ns_dy = south[1] - north[1]

    px = x - cx
    py = y - cy

    side_ns = cross2d(ns_dx, ns_dy, px, py)
    side_we = cross2d(we_dx, we_dy, px, py)

    east_side  = side_ns < 0
    south_side = side_we > 0

    if east_side and not south_side:
        return "NE"
    elif not east_side and not south_side:
        return "NW"
    elif not east_side and south_side:
        return "SW"
    else:
        return "SE"

def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4

    denom = (x1 - x2)*(y3 - y4) - (y1 - y2)*(x3 - x4)
    if abs(denom) < 1e-9:
        return None

    px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
    py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom

    return px, py

def line_segment_intersection_t(p1, p2, q1, q2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    qx = q2[0] - q1[0]
    qy = q2[1] - q1[1]

    denom = cross2d(dx, dy, qx, qy)

    if abs(denom) < 1e-9:
        return None
    
    wx = q1[0] - p1[0]
    wy = q1[1] - p1[1]

    t = cross2d(wx, wy, qx, qy) / denom    
    return t

def segment_quadrant_splits(p1, p2, west, north, east, south):
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dx = x2 - x1
    dy = y2 - y1

    t_vals = [0.0, 1.0]

    t_ns = line_segment_intersection_t(p1, p2, north, south)
    if t_ns is not None and 0.0 < t_ns < 1.0:
        t_vals.append(t_ns)

    t_we = line_segment_intersection_t(p1, p2, west, east)
    if t_we is not None and 0.0 < t_we < 1.0:
        t_vals.append(t_we)

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
        q  = get_quadrant(xm, ym, west, north, east, south)
        splits.append(((xa, ya), (xb, yb), q))

    return splits

def parse_time_input(inp: str) -> float:
    inp = inp.strip()
    if not inp:
        return None
    if ':' in inp:
        parts = inp.split(':')
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + int(seconds)
    return float(inp)

def get_video_params(default_radius=60):
    start_inp = input("Video start time (Press Enter for regular start, or type 00:05 / 5): ")
    end_inp   = input("Video ending time (Press Enter for regular end, or type 01:02 / 62): ")
    radius_inp = input(f"Pool radius in cm (Press Enter for {default_radius}): ")

    start_sec = parse_time_input(start_inp)
    end_sec   = parse_time_input(end_inp)
    pool_radius_cm = float(radius_inp) if radius_inp.strip() else default_radius

    print(f"Using parameters -> Start: {start_sec or 'default'} s, End: {end_sec or 'default'} s, Pool radius: {pool_radius_cm} cm\n")
    return start_sec, end_sec, pool_radius_cm

# QUADRANT STATS ACCUMULATOR

def empty_quadrant_stats():
    return {q: {"time_s": 0.0, "dist_cm": 0.0} for q in QUADRANT_NAMES}


def accumulate_segment(stats, p1, p2, west, north, east, south, frame_dt, scale_x, scale_y):
    total_dist_px = euclidean_px(p1, p2)
    splits = segment_quadrant_splits(p1, p2, west, north, east, south)

    for idx, (sa, sb, q) in enumerate(splits):
        sub_dist_px = euclidean_px(sa, sb)
        if total_dist_px > 0:
            frac = sub_dist_px / total_dist_px
        else:
            frac = 1.0 if idx == 0 else 0.0

        stats[q]["time_s"]  += frac * frame_dt
        stats[q]["dist_cm"] += euclidean_cm(sa, sb, scale_x, scale_y)


def accumulate_static(stats, pos, west, north, east, south, frame_dt):
    q = get_quadrant(pos[0], pos[1], west, north, east, south)
    stats[q]["time_s"] += frame_dt


# ON-SCREEN LEADERBOARD RENDERER

def draw_leaderboard(img, stats, total_time_s, total_dist_cm):
    sorted_q = ["NW", "NE", "SW", "SE"]

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
    cv2.putText(img, "QUADRANT LEADERBOARD", (x0 + pad, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1)

    for rank, q in enumerate(sorted_q):
        t_s   = stats[q]["time_s"]
        d_cm  = stats[q]["dist_cm"]
        t_pct = (t_s   / total_time_s   * 100) if total_time_s   > 0 else 0.0
        d_pct = (d_cm  / total_dist_cm  * 100) if total_dist_cm  > 0 else 0.0
        color = QUADRANT_COLORS[q]

        row_y = y0 + header_h + rank * row_h + row_h - 4

        cv2.putText(img, f"#{rank+1} {q}", (x0 + pad, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1)
        cv2.putText(img, f"T:{t_s:5.1f}s {t_pct:4.1f}%", (x0 + pad + 52, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1)
        cv2.putText(img, f"D:{d_cm:6.1f}cm {d_pct:4.1f}%", (x0 + pad + 166, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 200, 50), 1)


# RAT DETECTION

def detect_rat(frame, subtractor, cfg, pool_mask=None, pool=None, frame_idx=0, prev_pos=None):
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    fg_mask = subtractor.apply(frame)

    if pool_mask is not None:
        fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=pool_mask)

    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg["morph_open_k"],  cfg["morph_open_k"]))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg["morph_close_k"], cfg["morph_close_k"]))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  k_open)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k_close)

    if cfg["debug_frames"] > 0 and frame_idx < cfg["debug_frames"]:
        cv2.imwrite(f"debug_frame_{frame_idx:03d}.png", fg_mask)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    candidates = []
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
        candidates.append((bx, by, area))

    if not candidates:
        return None

    if prev_pos is not None:
        candidates.sort(key=lambda c: euclidean_px(prev_pos, (c[0], c[1])))
    else:
        candidates.sort(key=lambda c: c[2], reverse=True)

    bx, by, _ = candidates[0]
    return (bx, by)


# INTERPOLATION

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


# CONFIG CONFIRMATION

def confirm_pool_from_config(frame, cfg):
    p = {
        "WEST":  cfg["pool_west"],
        "NORTH": cfg["pool_north"],
        "EAST":  cfg["pool_east"],
        "SOUTH": cfg["pool_south"],
    }

    result = pool_ellipse_from_nsew(p["WEST"], p["NORTH"], p["EAST"], p["SOUTH"])
    if result is None:
        return False
    cx, cy, rx, ry, angle = result

    img = frame.copy()

    cv2.ellipse(img, (cx, cy), (rx, ry), angle, 0, 360, (100, 255, 180), 2)
    cv2.circle(img, (cx, cy), 5, (100, 255, 180), -1)
    cv2.circle(img, (cx, cy), 7, (255, 255, 255), 1)

    cv2.line(img, p["NORTH"], p["SOUTH"], (100, 255, 180), 1)
    cv2.line(img, p["WEST"],  p["EAST"],  (100, 255, 180), 1)

    for cardinal, pt in p.items():
        col = CALIB_COLORS[cardinal]
        cv2.circle(img, pt, 7, col, -1)
        cv2.circle(img, pt, 9, (255, 255, 255), 1)
        cv2.putText(img, cardinal, (pt[0] + 11, pt[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)

    draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
    cv2.putText(img, "Saved pool coordinates found -- confirm or repick?", (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
    cv2.putText(img, "ENTER  -->  Continue with these coordinates     ESC  -->  Repick", (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)

    window = "Pool Confirmation"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))
    cv2.imshow(window, img)

    print("\n-- Saved Pool Coordinates ------------------------------------")
    for cardinal, pt in p.items():
        print(f"  {cardinal}: {pt}")
    print(f"  Centre: ({cx}, {cy})  rx={rx}px  ry={ry}px  angle={angle:.2f}")
    print("ENTER = use these   |   ESC = repick")
    print("--------------------------------------------------------------\n")

    confirmed = False
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 10):
            confirmed = True
            break
        elif key == 27:
            confirmed = False
            break

    cv2.destroyWindow(window)
    return confirmed

def main(video_path: str):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    start_sec, end_sec, pool_radius_cm = get_video_params()
    DEFAULTS["pool_radius_cm"] = pool_radius_cm

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
        print("\nNo pool coordinates found -- opening calibration window...")
        result = run_calibration(first_frame, pool_radius_cm)
        if result is None:
            raise RuntimeError("Pool calibration is required. Please re-run and complete calibration.")
        cfg.update(result)
        save_config(cfg)
    else:
        use_saved = confirm_pool_from_config(first_frame, cfg)
        if not use_saved:
            print("\nRepicking pool coordinates...")
            result = run_calibration(first_frame, pool_radius_cm)
            if result is None:
                raise RuntimeError("Pool calibration is required. Please re-run and complete calibration.")
            cfg.update(result)
            save_config(cfg)
        else:
            print("Using saved pool coordinates.")

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)

    west  = cfg["pool_west"]
    north = cfg["pool_north"]
    east  = cfg["pool_east"]
    south = cfg["pool_south"]

    r_cm = cfg["pool_radius_cm"]

    ellipse = pool_ellipse_from_nsew(west, north, east, south)
    if ellipse is None:
        raise RuntimeError("Could not compute pool ellipse from calibration points.")
    cx, cy, rx, ry, angle = ellipse

    raw_rx_px = math.hypot(east[0] - west[0],   east[1] - west[1])   / 2
    raw_ry_px = math.hypot(south[0] - north[0],  south[1] - north[1]) / 2

    scale_x = r_cm / raw_rx_px
    scale_y = r_cm / raw_ry_px

    pool = (cx, cy, rx, ry, angle)
    pool_mask = make_ellipse_mask((frame_h, frame_w), *pool)

    print(f"Pool radius: {r_cm} cm")
    print(f"Pool ellipse -> centre=({cx},{cy}), rx={rx}px, ry={ry}px, angle={angle:.2f}deg")
    print(f"Scale factors -> x: {scale_x:.4f} cm/px  |  y: {scale_y:.4f} cm/px")

    OUTPUT_DIR.mkdir(exist_ok=True)
    video_out = OUTPUT_DIR / (video_path.stem + "_tracked.mp4")
    fourcc    = cv2.VideoWriter_fourcc(*"mp4v")
    writer    = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )

    records         = []
    trail           = []
    frame_idx       = 0
    running_dist_px = 0.0
    running_dist_cm = 0.0
    prev_pos        = None

    q_stats = empty_quadrant_stats()
    loop_start = time.time()

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        gray      = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        timestamp = frame_idx / fps
        pos       = detect_rat(gray, subtractor, cfg, pool_mask, pool, frame_idx, prev_pos)

        if pos and prev_pos:
            d_px = euclidean_px(prev_pos, pos)
            running_dist_px += d_px
            running_dist_cm += euclidean_cm(prev_pos, pos, scale_x, scale_y)
            accumulate_segment(q_stats, prev_pos, pos, west, north, east, south,
                               frame_dt, scale_x, scale_y)
        elif pos and prev_pos is None:
            accumulate_static(q_stats, pos, west, north, east, south, frame_dt)
        elif pos and prev_pos == pos:
            accumulate_static(q_stats, pos, west, north, east, south, frame_dt)

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

        cv2.ellipse(annotated, (cx, cy), (rx, ry), angle, 0, 360, (255, 100, 0), thickness=2)
        cv2.line(annotated, north, south, (255, 100, 0), 1)
        cv2.line(annotated, west,  east,  (255, 100, 0), 1)
        for pt in [west, north, east, south, (cx, cy)]:
            cv2.circle(annotated, pt, 5, (255, 100, 0), -1)
            cv2.circle(annotated, pt, 6, (255, 255, 255), 1)

        def quadrant_label_pos(qa, qb):
            mx = (qa[0] + qb[0]) // 2
            my = (qa[1] + qb[1]) // 2
            mx = int(mx * 0.6 + cx * 0.4)
            my = int(my * 0.6 + cy * 0.4)
            return (mx, my)

        q_label_positions = {
            "NE": quadrant_label_pos(north, east),
            "NW": quadrant_label_pos(north, west),
            "SW": quadrant_label_pos(south, west),
            "SE": quadrant_label_pos(south, east),
        }

        for q, lp in q_label_positions.items():
            cv2.putText(annotated, q, lp,
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, QUADRANT_COLORS[q], 1)

        if pos:
            trail.append(pos)
        if len(trail) > cfg["trail_len"]:
            trail.pop(0)
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            color = (0, int(255 * alpha), int(100 * (1 - alpha)))
            cv2.line(annotated, trail[i - 1], trail[i], color, 2)

        if pos:
            cv2.circle(annotated, pos, 8,  (0, 0, 255), -1)
            cv2.circle(annotated, pos, 10, (255, 255, 255), 1)

        status    = "DETECTED" if pos else "MISSING"
        hud_color = (0, 210, 0) if pos else (0, 0, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        hud_dist  = f"{running_dist_px:.1f} px  |  {running_dist_cm:.1f} cm"
        draw_transparent_banner(annotated, 5, 5, 340, 100)
        cv2.putText(annotated, f"Frame: {frame_idx:>4}   t = {timestamp:.2f}s", (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, f"Position: {pos_str}", (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, status, (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, hud_color, 1)
        cv2.putText(annotated, f"Dist: {hud_dist}", (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 50), 1)

        total_q_time = sum(v["time_s"]  for v in q_stats.values())
        total_q_dist = sum(v["dist_cm"] for v in q_stats.values())
        draw_leaderboard(annotated, q_stats, total_q_time, total_q_dist)

        writer.write(annotated)
        frame_idx += 1

        if total_frames > 0:
            pct     = frame_idx / total_frames
            elapsed = time.time() - loop_start
            eta     = (elapsed / pct - elapsed) if pct > 0 else 0
            bar_w   = 30
            filled  = int(bar_w * pct)
            bar     = "#" * filled + "-" * (bar_w - filled)
            eta_str = f"{int(eta // 60):02d}:{int(eta % 60):02d}"
            print(f"\r  [{bar}] {pct*100:5.1f}%  |  frame {frame_idx}/{total_frames}"
                  f"  |  ETA {eta_str}  ", end="", flush=True)

    cap.release()
    writer.release()

    total_elapsed = time.time() - loop_start
    print(f"\r  Processing complete -- {frame_idx} frames in "
          f"{int(total_elapsed // 60):02d}:{int(total_elapsed % 60):02d}  "
          + " " * 20)

    detected = sum(1 for r in records if r["x"] is not None)
    print(f"\nProcessed {frame_idx} frames. Detected rat in {detected} frames.")
    print(f"Annotated video -> {video_out}")

    records       = interpolate_missing(records)
    missing_after = sum(1 for r in records if r["x"] is None)
    if missing_after:
        print(f"Warning: {missing_after} frame(s) have no position.")

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
                accumulate_segment(q_stats_final, prev, curr,
                                   west, north, east, south,
                                   frame_dt, scale_x, scale_y)
                valid_pairs += 1
            else:
                accumulate_static(q_stats_final, curr, west, north, east, south, frame_dt)
            prev = curr

    total_q_time = sum(v["time_s"]  for v in q_stats_final.values())
    total_q_dist = sum(v["dist_cm"] for v in q_stats_final.values())

    csv_path = OUTPUT_DIR / f"{video_path.stem}_coordinates.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)
    print(f"Coordinates saved -> {csv_path}")

    sorted_q = sorted(QUADRANT_NAMES, key=lambda q: q_stats_final[q]["time_s"], reverse=True)

    summary_path = OUTPUT_DIR / f"{video_path.stem}_summary.txt"
    with open(summary_path, "w", encoding="utf-8") as f:
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
            f"Pool radius     : {cfg['pool_radius_cm']} cm",
            f"Scale X         : {scale_x:.4f} cm/px  (horizontal)",
            f"Scale Y         : {scale_y:.4f} cm/px  (vertical)",
            f"",
            f"Total distance  : {total_dist_px:.2f} px",
            f"Total distance  : {total_dist_cm:.2f} cm",
            f"  (over {valid_pairs} consecutive frame pairs)",
            f"",
            f"-- Quadrant Analysis (sorted by time spent) --",
            f"{'Quadrant':<10} {'Time (s)':>10} {'Time (%)':>10} {'Dist (cm)':>12} {'Dist (%)':>10}",
            f"{'-'*56}",
        ]
        for q in sorted_q:
            t_s   = q_stats_final[q]["time_s"]
            d_cm  = q_stats_final[q]["dist_cm"]
            t_pct = (t_s  / total_q_time * 100) if total_q_time > 0 else 0.0
            d_pct = (d_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
            lines.append(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%")
        lines += [f"{'-'*56}", f"{'TOTAL':<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%",]
        f.write("\n".join(lines))

    print(f"Summary saved   -> {summary_path}")
    print(f"\n-- Results -----------------------------------------------")
    print(f"Total distance  : {total_dist_px:.2f} px")
    print(f"Total distance  : {total_dist_cm:.2f} cm")
    print(f"\n-- Quadrant Analysis (sorted by time spent) --------------")
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
    print(f"----------------------------------------------------------")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track a rat in a water maze video.")
    parser.add_argument("--video", required=True, help="Path to the input video file")
    args = parser.parse_args()
    main(args.video)