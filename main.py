import cv2
import numpy as np
import csv
import math
import json
import argparse
import sys
import time
from datetime import datetime
from pathlib import Path

QUADRANT_NAMES  = ["NE", "NW", "SW", "SE"]
QUADRANT_COLORS = {
    "NE": (0,   200, 255),
    "NW": (0,   255, 100),
    "SW": (255, 180,   0),
    "SE": (180,   0, 255),
}

CALIB_STEPS = [
    ("WEST",  "west"),
    ("NORTH", "north"),
    ("EAST",  "east"),
    ("SOUTH", "south"),
]

CALIB_COLORS = {
    "WEST":  (255, 140, 0),
    "NORTH": (50, 205, 50),
    "EAST":  (30, 144, 255),
    "SOUTH": (238, 58, 140),
}

PLATFORM_STEPS = [
    ("NW", "platform_nw"),
    ("NE", "platform_ne"),
    ("SE", "platform_se"),
    ("SW", "platform_sw"),
]

PLATFORM_COLORS = {
    "NW": (255, 100, 200),
    "NE": (100, 200, 255),
    "SE": (200, 255, 100),
    "SW": (255, 200, 100),
}

NAMED_COLORS = {
    "red":     (0,   0,   255),
    "green":   (0,   255, 0),
    "blue":    (255, 0,   0),
    "yellow":  (0,   255, 255),
    "cyan":    (255, 255, 0),
    "magenta": (255, 0,   255),
    "white":   (255, 255, 255),
    "black":   (0,   0,   0),
    "orange":  (0,   165, 255),
    "purple":  (128, 0,   128),
    "pink":    (147, 20,  255),
    "lime":    (0,   255, 128),
    "teal":    (128, 128, 0),
    "navy":    (128, 0,   0),
    "maroon":  (0,   0,   128),
    "coral":   (80,  127, 255),
    "salmon":  (114, 128, 250),
    "gold":    (0,   215, 255),
    "silver":  (192, 192, 192),
    "indigo":  (130, 0,   75),
}

def parse_tracemap_color(value):
    if value is None:
        return (0, 255, 255)
    v = value.strip().lower()
    if v in NAMED_COLORS:
        return NAMED_COLORS[v]
    parts = v.split(",")
    if len(parts) == 3:
        try:
            r, g, b = int(parts[0]), int(parts[1]), int(parts[2])
            return (b, g, r)
        except ValueError:
            pass
    raise argparse.ArgumentTypeError(
        f"Invalid tracemapcolor '{value}'. Use R,G,B or a name: {', '.join(NAMED_COLORS)}"
    )

def scale_platform_corners(corners, scale):
    cx = sum(p[0] for p in corners) / 4
    cy = sum(p[1] for p in corners) / 4
    return [(cx + (p[0] - cx) * scale, cy + (p[1] - cy) * scale) for p in corners]

def platform_center(corners):
    return (sum(p[0] for p in corners) / 4, sum(p[1] for p in corners) / 4)

def tracemap(records, first_frame, output_dir, video_path, ts, color=(0, 255, 255)):
    canvas = first_frame.copy()
    output_path = output_dir / f"{video_path.stem}_{ts}_tracemap.jpg"
    prev_point = None
    for r in records:
        x = r.get("x")
        y = r.get("y")
        if x is None or y is None:
            prev_point = None
            continue
        point = (int(x), int(y))
        if prev_point is not None:
            cv2.line(canvas, prev_point, point, color, 2, lineType=cv2.LINE_AA)
        prev_point = point
    cv2.imwrite(str(output_path), canvas)

def heatmap(records, first_frame, output_dir, video_path, ts, sigma=20):
    h, w = first_frame.shape[:2]
    heat = np.zeros((h, w), dtype=np.float32)
    prev_time = None
    for r in records:
        x = r.get("x")
        y = r.get("y")
        t = r.get("timestamp_s")
        if x is None or y is None or t is None:
            prev_time = None
            continue
        x = int(x)
        y = int(y)
        if prev_time is not None:
            dt = t - prev_time
            if dt < 0 or dt > 1:
                dt = 0
            if 0 <= x < w and 0 <= y < h:
                heat[y, x] += dt
        prev_time = t
    heat = cv2.GaussianBlur(heat, (0, 0), sigmaX=sigma, sigmaY=sigma)
    heat_norm = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX)
    heat_uint8 = heat_norm.astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)
    overlay = cv2.addWeighted(first_frame, 0.6, heat_color, 0.4, 0)
    output_path = output_dir / f"{video_path.stem}_{ts}_heatmap.jpg"
    cv2.imwrite(str(output_path), overlay)

def emit_progress(frame_idx, processable_frames, loop_start, app_mode):
    if processable_frames <= 0:
        return
    pct     = frame_idx / processable_frames
    elapsed = time.time() - loop_start
    eta     = int(elapsed / pct - elapsed) if pct > 0 else 0
    if app_mode:
        print(json.dumps({
            "progress": round(pct * 100, 2),
            "frame":    frame_idx,
            "total":    processable_frames,
            "eta":      eta,
        }), flush=True)
    else:
        bar_width = 30
        filled    = int(bar_width * pct)
        bar       = "#" * filled + "-" * (bar_width - filled)
        line      = f"\r[{bar}] {pct*100:5.1f}%  Frame {frame_idx}/{processable_frames}  ETA: {eta}s   "
        print(line, end="", flush=True)

def appmode_calib(require_platform: bool, existing_pool: dict = None) -> dict | None:
    msg = {
        "needs_calib":      True,
        "require_platform": require_platform,
    }

    if existing_pool:
        msg["existing_pool"] = {
            "pool_west":  list(existing_pool["pool_west"]),
            "pool_north": list(existing_pool["pool_north"]),
            "pool_east":  list(existing_pool["pool_east"]),
            "pool_south": list(existing_pool["pool_south"]),
        }
        
    print(json.dumps(msg), flush=True)
    line = sys.stdin.readline()
    if not line:
        return None
    data = json.loads(line.strip())
    if data.get("aborted"):
        return None
    point_keys = ("pool_west", "pool_north", "pool_east", "pool_south",
                  "platform_nw", "platform_ne", "platform_se", "platform_sw")
    for key in point_keys:
        if key in data and isinstance(data[key], str):
            data[key] = parse_point(data[key])
    return data

def appmode_confirm(cfg: dict, confirm_type: str) -> bool:
    if confirm_type == "pool":
        points = {
            "pool_west":  list(cfg["pool_west"]),
            "pool_north": list(cfg["pool_north"]),
            "pool_east":  list(cfg["pool_east"]),
            "pool_south": list(cfg["pool_south"]),
        }
    else:
        points = {
            "platform_nw": list(cfg["platform_nw"]),
            "platform_ne": list(cfg["platform_ne"]),
            "platform_se": list(cfg["platform_se"]),
            "platform_sw": list(cfg["platform_sw"]),
        }

    msg = {
        "needs_confirm": True,
        "confirm_type":  confirm_type,
        "points":        points,
    }
    print(json.dumps(msg), flush=True)
    line = sys.stdin.readline()
    if not line:
        return False
    data = json.loads(line.strip())
    return bool(data.get("confirmed"))

def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_west", "pool_north", "pool_east", "pool_south"))

def platform_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("platform_nw", "platform_ne", "platform_se", "platform_sw"))

def needs_platform(args) -> bool:
    return any([args.platformcross, args.paraplatform is not None,
                args.proximity, args.latency])

def run_calibration(frame: np.ndarray, require_platform: bool = False) -> dict | None:
    state = {
        "step": 0,
        "pool_points": {},
        "platform_points": {},
        "phase": "pool",
        "frame": frame.copy(),
    }
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    calib_cardinal_labels = {
        "WEST":  'WEST',
        "NORTH": 'NORTH',
        "EAST":  'EAST',
        "SOUTH": 'SOUTH',
    }

    def draw(base):
        img = base.copy()
        banner_h = sc(img, 70)
        draw_transparent_banner(img, 0, 0, frame.shape[1], banner_h)
        tx, ty1, ty2 = sc(img, 14), sc(img, 30), sc(img, 56)
        fs1, fs2 = sc_f(img, 0.65), sc_f(img, 0.50)
        if state["phase"] == "pool":
            step = state["step"]
            if step < len(CALIB_STEPS):
                cardinal, _ = CALIB_STEPS[step]
                color = CALIB_COLORS[cardinal]
                label = calib_cardinal_labels[cardinal]
                cv2.putText(img, f"Step {step}/4 -- Click on the {cardinal} point of the pool edge",
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
                cv2.putText(img, 'Press  R  to redo all points   |   ESC to abort',
                            (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
            else:
                if not require_platform:
                    cv2.putText(img, 'All 4 points set -- press ENTER to confirm or R to redo',
                                (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
                    cv2.putText(img, 'ENTER  -->  Confirm all 8 points',
                                (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        elif state["phase"] == "platform":
            step = state["step"]
            if step < len(PLATFORM_STEPS):
                corner, _ = PLATFORM_STEPS[step]
                color = PLATFORM_COLORS[corner]
                cv2.putText(img, f"Pool done! Now click the {corner} platform corner (clockwise)",
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
                cv2.putText(img, 'Press  R  to redo all points   |   ESC to abort',
                            (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
            else:
                cv2.putText(img, 'All 8 points set -- press ENTER to confirm or R to redo all',
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
                cv2.putText(img, 'ENTER  -->  Confirm all 8 points',
                            (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        dot_r, dot_ro = sc(img, 7), sc(img, 9)
        lbl_off = sc(img, 12)
        lbl_fs  = sc_f(img, 0.52)
        for cardinal, pt in state["pool_points"].items():
            col = CALIB_COLORS[cardinal]
            cv2.circle(img, pt, dot_r, col, -1)
            cv2.circle(img, pt, dot_ro, (255, 255, 255), 1)
            cv2.putText(img, calib_cardinal_labels[cardinal],
                        (pt[0] + lbl_off, pt[1] + sc(img, 5)), cv2.FONT_HERSHEY_DUPLEX, lbl_fs, col, 1, cv2.LINE_AA)
        if len(state["pool_points"]) == 4:
            p = state["pool_points"]
            result = pool_ellipse_from_nsew(p["WEST"], p["NORTH"], p["EAST"], p["SOUTH"])
            if result is not None:
                ecx, ecy, erx, ery, eangle = result
                cv2.ellipse(img, (ecx, ecy), (erx, ery), eangle, 0, 360, (100, 255, 180), 2)
                cv2.circle(img, (ecx, ecy), sc(img, 5), (100, 255, 180), -1)
                cv2.line(img, p["NORTH"], p["SOUTH"], (100, 255, 180), 1)
                cv2.line(img, p["WEST"],  p["EAST"],  (100, 255, 180), 1)
        for corner, pt in state["platform_points"].items():
            col = PLATFORM_COLORS[corner]
            cv2.circle(img, pt, dot_r, col, -1)
            cv2.circle(img, pt, dot_ro, (255, 255, 255), 1)
            cv2.putText(img, corner, (pt[0] + lbl_off, pt[1] + sc(img, 5)),
                        cv2.FONT_HERSHEY_DUPLEX, lbl_fs, col, 1, cv2.LINE_AA)
        pts_ordered = [state["platform_points"].get(s[0]) for s in PLATFORM_STEPS if s[0] in state["platform_points"]]
        if len(pts_ordered) >= 2:
            for i in range(len(pts_ordered) - 1):
                cv2.line(img, pts_ordered[i], pts_ordered[i+1], (200, 200, 50), 1)
        if len(state["platform_points"]) == 4:
            corners_ordered = [state["platform_points"][s[0]] for s in PLATFORM_STEPS]
            pts_np = np.array(corners_ordered, dtype=np.int32)
            cv2.polylines(img, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
            if require_platform:
                para_preview = scale_platform_corners(corners_ordered, math.sqrt(4))
                para_pts_np = np.array([(int(p[0]), int(p[1])) for p in para_preview], dtype=np.int32)
                cv2.polylines(img, [para_pts_np], isClosed=True, color=(0, 180, 255), thickness=1)
        return img

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN:
            return
        if state["phase"] == "pool":
            step = state["step"]
            if step >= len(CALIB_STEPS):
                return
            cardinal, _ = CALIB_STEPS[step]
            state["pool_points"][cardinal] = (x, y)
            state["step"] += 1
            if state["step"] == len(CALIB_STEPS) and require_platform:
                state["phase"] = "platform"
                state["step"] = 0
        elif state["phase"] == "platform":
            step = state["step"]
            if step >= len(PLATFORM_STEPS):
                return
            corner, _ = PLATFORM_STEPS[step]
            state["platform_points"][corner] = (x, y)
            state["step"] += 1
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    result = None
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            break
        elif key in (ord('r'), ord('R')):
            state["step"] = 0
            state["phase"] = "pool"
            state["pool_points"] = {}
            state["platform_points"] = {}
            cv2.imshow(window, draw(state["frame"]))
        elif key in (13, 10):
            p = state["pool_points"]
            if len(p) == 4:
                if require_platform:
                    plat = state["platform_points"]
                    if len(plat) == 4:
                        result = {
                            "pool_west":   p["WEST"],
                            "pool_north":  p["NORTH"],
                            "pool_east":   p["EAST"],
                            "pool_south":  p["SOUTH"],
                            "platform_nw": plat["NW"],
                            "platform_ne": plat["NE"],
                            "platform_se": plat["SE"],
                            "platform_sw": plat["SW"],
                        }
                        break
                else:
                    result = {
                        "pool_west":  p["WEST"],
                        "pool_north": p["NORTH"],
                        "pool_east":  p["EAST"],
                        "pool_south": p["SOUTH"],
                    }
                    break
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    return result

def run_platform_calibration(frame: np.ndarray) -> dict | None:
    state = {"step": 0, "points": {}, "frame": frame.copy()}
    window = "Platform Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    def draw(base):
        img = base.copy()
        banner_h = sc(img, 70)
        draw_transparent_banner(img, 0, 0, frame.shape[1], banner_h)
        tx, ty1, ty2 = sc(img, 14), sc(img, 30), sc(img, 56)
        fs1, fs2 = sc_f(img, 0.65), sc_f(img, 0.50)
        step = state["step"]
        if step < len(PLATFORM_STEPS):
            corner, _ = PLATFORM_STEPS[step]
            color = PLATFORM_COLORS[corner]
            cv2.putText(img, f"Platform Step {step}/4 -- Click the {corner} corner (clockwise)",
                        (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
            cv2.putText(img, 'Press  R  to redo all points   |   ESC to skip platform',
                        (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        else:
            cv2.putText(img, 'All 4 corners set -- press ENTER to confirm or R to redo',
                        (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
            cv2.putText(img, 'ESC  -->  skip platform',
                        (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        pts_ordered = [state["points"].get(s[0]) for s in PLATFORM_STEPS if s[0] in state["points"]]
        if len(pts_ordered) >= 2:
            for i in range(len(pts_ordered) - 1):
                cv2.line(img, pts_ordered[i], pts_ordered[i+1], (200, 200, 50), 1)
        if len(state["points"]) == 4:
            corners_ordered = [state["points"][s[0]] for s in PLATFORM_STEPS]
            pts_np = np.array(corners_ordered, dtype=np.int32)
            cv2.polylines(img, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
        dot_r, dot_ro = sc(img, 7), sc(img, 9)
        lbl_off = sc(img, 12)
        lbl_fs  = sc_f(img, 0.52)
        for corner, pt in state["points"].items():
            col = PLATFORM_COLORS[corner]
            cv2.circle(img, pt, dot_r, col, -1)
            cv2.circle(img, pt, dot_ro, (255, 255, 255), 1)
            cv2.putText(img, corner, (pt[0] + lbl_off, pt[1] + sc(img, 5)),
                        cv2.FONT_HERSHEY_DUPLEX, lbl_fs, col, 1, cv2.LINE_AA)
        return img

    def on_click(event, x, y, flags, param):
        if event != cv2.EVENT_LBUTTONDOWN: return
        step = state["step"]
        if step >= len(PLATFORM_STEPS): return
        corner, _ = PLATFORM_STEPS[step]
        state["points"][corner] = (x, y)
        state["step"] += 1
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    result = None
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key == 27:
            break
        elif key in (ord('r'), ord('R')):
            state["step"] = 0
            state["points"] = {}
            cv2.imshow(window, draw(state["frame"]))
        elif key in (13, 10):
            p = state["points"]
            if len(p) == 4:
                result = {
                    "platform_nw": p["NW"],
                    "platform_ne": p["NE"],
                    "platform_se": p["SE"],
                    "platform_sw": p["SW"],
                }
                break
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    return result

def confirm_pool_from_args(frame, cfg):
    p = {
        "WEST":  cfg["pool_west"],
        "NORTH": cfg["pool_north"],
        "EAST":  cfg["pool_east"],
        "SOUTH": cfg["pool_south"],
    }
    calib_cardinal_labels = {
        "WEST":  'WEST',
        "NORTH": 'NORTH',
        "EAST":  'EAST',
        "SOUTH": 'SOUTH',
    }
    result = pool_ellipse_from_nsew(p["WEST"], p["NORTH"], p["EAST"], p["SOUTH"])
    if result is None:
        return False
    ecx, ecy, erx, ery, eangle = result
    img = frame.copy()
    cv2.ellipse(img, (ecx, ecy), (erx, ery), eangle, 0, 360, (100, 255, 180), 2)
    cv2.circle(img, (ecx, ecy), 5, (100, 255, 180), -1)
    cv2.circle(img, (ecx, ecy), 7, (255, 255, 255), 1)
    cv2.line(img, p["NORTH"], p["SOUTH"], (100, 255, 180), 1)
    cv2.line(img, p["WEST"],  p["EAST"],  (100, 255, 180), 1)
    for cardinal, pt in p.items():
        col = CALIB_COLORS[cardinal]
        cv2.circle(img, pt, sc(img, 7), col, -1)
        cv2.circle(img, pt, sc(img, 9), (255, 255, 255), 1)
        cv2.putText(img, calib_cardinal_labels[cardinal],
                    (pt[0] + sc(img, 12), pt[1] + sc(img, 5)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.52), col, 1, cv2.LINE_AA)
    draw_transparent_banner(img, 0, 0, frame.shape[1], sc(img, 70))
    cv2.putText(img, 'Saved pool coordinates found -- confirm or repick',
                (sc(img, 14), sc(img, 28)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.65), (100, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(img, 'ENTER  -->  Continue with these coordinates     ESC  -->  Repick',
                (sc(img, 14), sc(img, 56)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.52), (180, 180, 180), 1, cv2.LINE_AA)
    window = "Pool Confirmation"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))
    cv2.imshow(window, img)
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

def confirm_platform_from_args(frame, cfg):
    corners = [cfg["platform_nw"], cfg["platform_ne"], cfg["platform_se"], cfg["platform_sw"]]
    img = frame.copy()
    pts_np = np.array(corners, dtype=np.int32)
    cv2.polylines(img, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
    for i, (corner_name, _) in enumerate(PLATFORM_STEPS):
        pt = corners[i]
        col = PLATFORM_COLORS[corner_name]
        cv2.circle(img, pt, sc(img, 7), col, -1)
        cv2.circle(img, pt, sc(img, 9), (255, 255, 255), 1)
        cv2.putText(img, corner_name, (pt[0] + sc(img, 12), pt[1] + sc(img, 5)),
                    cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.52), col, 1, cv2.LINE_AA)
    draw_transparent_banner(img, 0, 0, frame.shape[1], sc(img, 70))
    cv2.putText(img, 'Saved platform coordinates found -- confirm or repick',
                (sc(img, 14), sc(img, 28)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.65), (100, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(img, 'ENTER  -->  Continue with these coordinates     ESC  -->  Repick',
                (sc(img, 14), sc(img, 56)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.52), (180, 180, 180), 1, cv2.LINE_AA)
    window = "Platform Confirmation"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))
    cv2.imshow(window, img)
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

## Pool Calculations

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
    u = cross2d(wx, wy, dx, dy) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None

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

## Platform geometry

def get_platform_edges(platform_corners):
    nw, ne, se, sw = platform_corners
    return [(nw, ne), (ne, se), (se, sw), (sw, nw)]

def point_in_platform(pt, platform_corners) -> bool:
    x, y = pt
    corners = list(platform_corners)
    n = len(corners)
    inside = False
    px, py = x, y
    j = n - 1
    for i in range(n):
        xi, yi = corners[i][0], corners[i][1]
        xj, yj = corners[j][0], corners[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def segment_crosses_platform_twice(p1, p2, platform_corners) -> bool:
    edges = get_platform_edges(platform_corners)
    crossings = []
    for edge_a, edge_b in edges:
        t = line_segment_intersection_t(p1, p2, edge_a, edge_b)
        if t is not None:
            crossings.append(t)
    unique_crossings = []
    for t in sorted(crossings):
        if not unique_crossings or abs(t - unique_crossings[-1]) > 1e-6:
            unique_crossings.append(t)
    return len(unique_crossings) >= 2

def segment_enters_platform(p1, p2, platform_corners, prev_inside: bool) -> bool:
    curr_inside = point_in_platform(p2, platform_corners)
    if not prev_inside and curr_inside:
        return True
    if not prev_inside and not curr_inside:
        return segment_crosses_platform_twice(p1, p2, platform_corners)
    return False

## Calculations

def empty_quadrant_stats():
    return {q: {"time_s": 0.0, "dist_cm": 0.0} for q in QUADRANT_NAMES}

def empty_quadrant_exits():
    return {q: 0 for q in QUADRANT_NAMES}

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

def count_quadrant_exits(prev_pos, curr_pos, west, north, east, south, exits_dict):
    prev_q = get_quadrant(prev_pos[0], prev_pos[1], west, north, east, south)
    splits = segment_quadrant_splits(prev_pos, curr_pos, west, north, east, south)
    current_q = prev_q
    for (_, _, q) in splits:
        if q != current_q and current_q in exits_dict:
            exits_dict[current_q] += 1
        current_q = q

def res_scale(img):
    return min(img.shape[1], img.shape[0]) / 720.0

def sc(img, px):
    return max(1, int(round(px * res_scale(img))))

def sc_f(img, val):
    return val * res_scale(img)

def draw_transparent_banner(img, x0, y0, x1, y1, alpha=0.65):
    overlay = img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (8, 8, 8), -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (60, 60, 60), 1)

def draw_leaderboard(img, stats, total_time_s, total_dist_cm, quad_exits=None):
    sorted_q   = ["NW", "NE", "SW", "SE"]
    show_exits = quad_exits is not None
    s          = res_scale(img)
    panel_w    = int((380 if show_exits else 320) * s)
    row_h      = int(26 * s)
    pad        = int(10 * s)
    header_h   = int(28 * s)
    panel_h    = header_h + len(QUADRANT_NAMES) * row_h + pad
    x0 = img.shape[1] - panel_w - sc(img, 10)
    y0 = sc(img, 10)
    x1 = x0 + panel_w
    y1 = y0 + panel_h
    overlay = img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (8, 8, 8), -1)
    cv2.addWeighted(overlay, 0.65, img, 0.35, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (70, 70, 70), 1)
    title_fs = sc_f(img, 0.48)
    cv2.putText(img, 'QUADRANT LEADERBOARD',
                (x0 + pad, y0 + int(18 * s)), cv2.FONT_HERSHEY_DUPLEX, title_fs, (210, 210, 210), 1, cv2.LINE_AA)
    row_fs   = sc_f(img, 0.42)
    col2_off = int(58 * s)
    col3_off = int(178 * s)
    col4_off = int(308 * s)
    for rank, q in enumerate(sorted_q):
        t_s   = stats[q]["time_s"]
        d_cm  = stats[q]["dist_cm"]
        t_pct = (t_s  / total_time_s  * 100) if total_time_s  > 0 else 0.0
        d_pct = (d_cm / total_dist_cm * 100) if total_dist_cm > 0 else 0.0
        color = QUADRANT_COLORS[q]
        row_y = y0 + header_h + rank * row_h + row_h - int(5 * s)
        cv2.putText(img, f"#{rank+1} {q}", (x0 + pad, row_y), cv2.FONT_HERSHEY_DUPLEX, row_fs, color, 1, cv2.LINE_AA)
        cv2.putText(img, f"T:{t_s:5.1f}s {t_pct:4.1f}%", (x0 + pad + col2_off, row_y), cv2.FONT_HERSHEY_DUPLEX, row_fs, (220, 220, 220), 1, cv2.LINE_AA)
        cv2.putText(img, f"D:{d_cm:6.1f}cm {d_pct:4.1f}%", (x0 + pad + col3_off, row_y), cv2.FONT_HERSHEY_DUPLEX, row_fs, (255, 200, 50), 1, cv2.LINE_AA)
        if show_exits:
            cv2.putText(img, f"X:{quad_exits.get(q, 0)}", (x0 + pad + col4_off, row_y), cv2.FONT_HERSHEY_DUPLEX, row_fs, (100, 200, 255), 1, cv2.LINE_AA)

## Rat Detection

def _extract_candidates(frame, subtractor, cfg, pool_mask, pool, frame_idx):
    """Run MOG2 + morphology + contour filtering. Returns list of (bx, by, area, cnt)
    for all contours that pass area and pool filters, without any position-based selection."""
    if len(frame.shape) == 3:
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    fg_mask = subtractor.apply(frame, learningRate=cfg.get("mog2_learning_rate", -1.0))
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
        candidates.append((bx, by, area, cnt))
    return candidates

def detect_rat(frame, subtractor, cfg, pool_mask=None, pool=None, frame_idx=0, prev_pos=None):
    """Detect rat position. Returns ((bx, by), contour, raw_candidates).
    raw_candidates is the full unfiltered list, saved by the caller for missed-frame recovery."""
    candidates = _extract_candidates(frame, subtractor, cfg, pool_mask, pool, frame_idx)
    if not candidates:
        return None, None, []
    if prev_pos is not None:
        candidates.sort(key=lambda c: euclidean_px(prev_pos, (c[0], c[1])))
    else:
        candidates.sort(key=lambda c: c[2], reverse=True)
    bx, by, area, winning_cnt = candidates[0]

    # Partial-blob smoother: if the winning blob is suspiciously small AND its
    # centroid is close to prev_pos, the rat is likely being partially absorbed
    # into the background (ghost absorption). Blend the centroid toward prev_pos
    # rather than jumping to the partial blob's center.
    # If the blob is small but FAR from prev_pos, trust it — the rat has moved
    # or is partially visible after a dive, and we should follow it.
    median_blob_area   = cfg.get("median_blob_area")
    rat_body_radius_px = cfg.get("rat_body_radius_px")
    if (prev_pos is not None
            and median_blob_area is not None
            and rat_body_radius_px is not None
            and area < median_blob_area * 0.50):
        dist_to_prev = euclidean_px(prev_pos, (bx, by))
        if dist_to_prev <= rat_body_radius_px * 2.0:
            # Partial detection near last position — blend centroid toward prev_pos.
            # Weight by how small the blob is: smaller blob = more pull toward prev_pos.
            smallness = 1.0 - (area / (median_blob_area * 0.50))  # 0..1
            alpha = smallness * 0.6  # max 60% pull toward prev_pos
            bx = int(round(bx * (1 - alpha) + prev_pos[0] * alpha))
            by = int(round(by * (1 - alpha) + prev_pos[1] * alpha))

    return (bx, by), winning_cnt, candidates

def detect_rat_appearance(frame, cfg, pool_mask, pool, prev_pos=None):
    """Appearance-based fallback detector. Thresholds the raw frame by brightness
    to find the rat as the brightest large blob in the pool, regardless of motion.
    Returns list of (bx, by, area, cnt) same format as _extract_candidates."""
    appearance_threshold = cfg.get("appearance_threshold")
    if appearance_threshold is None:
        return []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame.copy()
    _, binary = cv2.threshold(gray, appearance_threshold, 255, cv2.THRESH_BINARY)
    if pool_mask is not None:
        binary = cv2.bitwise_and(binary, binary, mask=pool_mask)
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                  (cfg["morph_close_k"], cfg["morph_close_k"]))
    binary = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k_close)
    contours, _ = cv2.findContours(binary, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
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
        candidates.append((bx, by, area, cnt))
    if not candidates:
        return []
    if prev_pos is not None:
        candidates.sort(key=lambda c: euclidean_px(prev_pos, (c[0], c[1])))
    else:
        candidates.sort(key=lambda c: c[2], reverse=True)
    return candidates


def interpolate_missing(records: list, max_gap: int = 0) -> list:
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
                gap = right - left
                if max_gap == 0 or gap - 1 <= max_gap:
                    x0, y0 = result[left]["x"],  result[left]["y"]
                    x1, y1 = result[right]["x"], result[right]["y"]
                    for j in range(left + 1, right):
                        t = (j - left) / gap
                        result[j]["x"]            = round(x0 + t * (x1 - x0), 2)
                        result[j]["y"]            = round(y0 + t * (y1 - y0), 2)
                        result[j]["interpolated"] = True
            i = right
        else:
            i += 1
    return result

def retroactive_jump_correction(records, missed_candidates, jump_threshold_px):
    """After re-locking on the rat following a miss streak, walk backwards through
    the missed frames using the re-lock position as an anchor, picking the candidate
    closest to the current backward position at each step.

    This recovers real detection data for missed frames rather than relying on
    linear interpolation across the entire gap. Whatever true gap remains in the
    middle (genuinely zero candidates) is left as None for interpolate_missing.

    missed_candidates: dict of {record_index: [(bx, by, area, cnt), ...]}
                       populated during the main loop for every frame where pos was None.
    jump_threshold_px: maximum px step considered continuous during backward walk.
                       If no candidate is within this distance, the backward walk stops.
    """
    n = len(records)
    i = 0
    while i < n:
        # Find the start of a None streak
        if records[i]["x"] is not None:
            i += 1
            continue
        streak_start = i
        while i < n and records[i]["x"] is None:
            i += 1
        streak_end = i  # first non-None after the gap (exclusive), or n if never re-locked

        if streak_end >= n:
            break  # never re-locked, leave for interpolate_missing

        # We have a gap: [streak_start, streak_end)
        # Anchor the backward walk from the re-lock position
        anchor = (records[streak_end]["x"], records[streak_end]["y"])

        for j in range(streak_end - 1, streak_start - 1, -1):
            candidates = missed_candidates.get(j, [])
            if not candidates:
                continue  # genuinely no detection this frame, leave as None
            # Pick closest candidate to current backward anchor
            candidates_sorted = sorted(candidates, key=lambda c: euclidean_px(anchor, (c[0], c[1])))
            bx, by, _, _ = candidates_sorted[0]
            dist = euclidean_px(anchor, (bx, by))
            if dist > jump_threshold_px:
                break  # gap too large, stop backward walk; leave rest for interpolation
            records[j]["x"] = bx
            records[j]["y"] = by
            anchor = (bx, by)

def parse_point(s):
    parts = s.split(",")
    return (int(parts[0]), int(parts[1]))

def fmt_pt(pt):
    return f"{pt[0]},{pt[1]}"

def build_rerun_command(video_path, args, cfg):
    # When autoconfig was used, cfg carries the resolved values; always emit them
    # explicitly so reruns are fully deterministic without --autoconfig.
    resolved_mog2_threshold  = cfg.get("mog2_threshold",  args.mog2_threshold)
    resolved_morph_open_k    = cfg.get("morph_open_k",    args.morph_open_k)
    resolved_morph_close_k   = cfg.get("morph_close_k",   args.morph_close_k)
    resolved_mog2_history_s  = cfg.get("mog2_history_s",  args.mog2_history_s)

    parts = ["python main.py"]
    if args.start is not None:
        parts.append(f"--start {args.start}")
    if args.end is not None:
        parts.append(f"--end {args.end}")
    if args.pool_radius_cm != 60:
        parts.append(f"--pool_radius_cm {args.pool_radius_cm}")
    if resolved_mog2_history_s != 4.0:
        parts.append(f"--mog2_history_s {resolved_mog2_history_s}")
    if resolved_mog2_threshold != 32:
        parts.append(f"--mog2_threshold {resolved_mog2_threshold}")
    if args.mog2_detect_shadow:
        parts.append("--mog2_detect_shadow")
    if args.mog2_learning_rate != -1.0:
        parts.append(f"--mog2_learning_rate {args.mog2_learning_rate}")
    if args.max_interp_gap != 0:
        parts.append(f"--max_interp_gap {args.max_interp_gap}")
    if args.heatmap_sigma != 0:
        parts.append(f"--heatmap_sigma {args.heatmap_sigma}")
    if resolved_morph_open_k != 3:
        parts.append(f"--morph_open_k {resolved_morph_open_k}")
    if resolved_morph_close_k != 15:
        parts.append(f"--morph_close_k {resolved_morph_close_k}")
    if args.min_contour_area != 300:
        parts.append(f"--min_contour_area {args.min_contour_area}")
    if args.max_contour_area != 12000:
        parts.append(f"--max_contour_area {args.max_contour_area}")
    if args.trail_s != 2.0:
        parts.append(f"--trail_s {args.trail_s}")
    if args.debug_frames != 0:
        parts.append(f"--debug_frames {args.debug_frames}")
    if args.quadrantcross:
        parts.append("--quadrantcross")
    if args.platformcross:
        parts.append("--platformcross")
    if args.paraplatform is not None:
        parts.append(f"--paraplatform {args.paraplatform}")
    if args.proximity:
        parts.append("--proximity")
    if args.latency:
        parts.append("--latency")
    if args.tracemapcolor is not None:
        parts.append(f"--tracemapcolor {args.tracemapcolor}")
    if args.ratcolor is not None:
        parts.append(f"--ratcolor {args.ratcolor}")
    if args.colorall:
        parts.append("--colorall")
    parts.append(f"--pool_west {fmt_pt(cfg['pool_west'])}")
    parts.append(f"--pool_north {fmt_pt(cfg['pool_north'])}")
    parts.append(f"--pool_east {fmt_pt(cfg['pool_east'])}")
    parts.append(f"--pool_south {fmt_pt(cfg['pool_south'])}")
    if platform_coords_valid(cfg):
        parts.append(f"--platform_nw {fmt_pt(cfg['platform_nw'])}")
        parts.append(f"--platform_ne {fmt_pt(cfg['platform_ne'])}")
        parts.append(f"--platform_se {fmt_pt(cfg['platform_se'])}")
        parts.append(f"--platform_sw {fmt_pt(cfg['platform_sw'])}")
    if args.appmode:
        parts.append("--appmode")
    parts.append(f"--video {args.video}")
    return " ".join(parts)

def run_autoconfig(cap, fps, total_frames, start_frame, end_frame, cfg, pool_mask, pool):
    """Analyse the video to suggest optimal mog2_threshold, morph_open_k,
    morph_close_k, and mog2_history_s.  Returns a dict of recommended values."""

    print("[autoconfig] Starting analysis...", flush=True)

    cx, cy, rx, ry, angle = pool
    mean_pool_r_px = (rx + ry) / 2

    # -------------------------------------------------------------------------
    # Step 1 — find a reliable rat detection to measure rat vs background contrast
    # Strategy: try the midpoint of the session first, then scan forward from
    # there, wrapping to the start if needed.
    # We use a temporary subtractor with default settings just for this probe.
    # -------------------------------------------------------------------------
    PROBE_THRESHOLD  = 32        # default threshold for the bootstrap detection
    PROBE_WARMUP_S   = 3.0       # seconds of warmup before probing
    probe_warmup_f   = max(1, int(PROBE_WARMUP_S * fps))

    probe_cfg = dict(cfg)
    probe_cfg["mog2_threshold"]    = PROBE_THRESHOLD
    probe_cfg["mog2_learning_rate"] = -1.0
    probe_cfg["debug_frames"]      = 0

    def _make_probe_subtractor(start_at):
        """Create and warm up a fresh MOG2 subtractor beginning at start_at."""
        sub = cv2.createBackgroundSubtractorMOG2(
            history       = probe_warmup_f,
            varThreshold  = PROBE_THRESHOLD,
            detectShadows = False,
        )
        warmup_begin = max(0, start_at - probe_warmup_f)
        cap.set(cv2.CAP_PROP_POS_FRAMES, warmup_begin)
        for _ in range(start_at - warmup_begin):
            ret, wf = cap.read()
            if not ret:
                break
            if len(wf.shape) == 3:
                wf = cv2.cvtColor(wf, cv2.COLOR_BGR2GRAY)
            sub.apply(wf, learningRate=-1.0)
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_at)
        return sub

    def _probe_for_rat(scan_start, scan_end):
        """Scan [scan_start, scan_end) frame by frame, return (frame_bgr, pos, contour)
        for the first successful detection, or None."""
        sub = _make_probe_subtractor(scan_start)
        cap.set(cv2.CAP_PROP_POS_FRAMES, scan_start)
        prev = None
        for fi in range(scan_start, scan_end):
            ret, frm = cap.read()
            if not ret:
                break
            pos, cnt, _ = detect_rat(frm, sub, probe_cfg, pool_mask, pool, fi, prev)
            if pos is not None:
                return frm, pos, cnt
            prev = pos
        return None

    session_mid  = start_frame + (end_frame - start_frame) // 2
    probe_result = _probe_for_rat(session_mid, end_frame)
    if probe_result is None:
        probe_result = _probe_for_rat(start_frame, session_mid)
    if probe_result is None:
        print("[autoconfig] WARNING: could not detect rat in any frame. "
              "Skipping threshold calibration, keeping default.", flush=True)
        rat_brightness  = None
        bg_brightness   = None
        contrast        = None
    else:
        # Collect brightness samples from multiple spread-out probe frames
        BRIGHTNESS_SAMPLES = 7
        sample_interval    = max(1, (end_frame - start_frame) // BRIGHTNESS_SAMPLES)
        rat_samples        = []
        bg_samples         = []

        # Seed one subtractor from start_frame for consistent bg estimates
        sub_multi = _make_probe_subtractor(start_frame)

        for si in range(BRIGHTNESS_SAMPLES):
            fi = start_frame + si * sample_interval
            if fi >= end_frame:
                break
            res = _probe_for_rat(fi, min(fi + max(1, sample_interval), end_frame))
            if res is None:
                continue
            s_frame, s_pos, s_cnt = res
            mask_rat = np.zeros(s_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_rat, [s_cnt], -1, 255, -1)
            gray_f = cv2.cvtColor(s_frame, cv2.COLOR_BGR2GRAY)
            rat_samples.append(cv2.mean(gray_f, mask=mask_rat)[0])

            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            for _ in range(min(probe_warmup_f, fi - start_frame if fi > start_frame else probe_warmup_f)):
                ret2, wf2 = cap.read()
                if not ret2:
                    break
                if len(wf2.shape) == 3:
                    wf2 = cv2.cvtColor(wf2, cv2.COLOR_BGR2GRAY)
                sub_multi.apply(wf2, learningRate=-1.0)
            bg_img = sub_multi.getBackgroundImage()
            if bg_img is not None:
                if len(bg_img.shape) == 3:
                    bg_img = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
                bg_samples.append(cv2.mean(bg_img, mask=pool_mask)[0])

        if rat_samples and bg_samples:
            rat_brightness = float(np.median(rat_samples))
            bg_brightness  = float(np.median(bg_samples))
        else:
            # Fallback to original single-frame probe
            probe_frame, probe_pos, probe_cnt = probe_result
            mask_rat = np.zeros(probe_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_rat, [probe_cnt], -1, 255, -1)
            gray_frame = cv2.cvtColor(probe_frame, cv2.COLOR_BGR2GRAY)
            rat_brightness = cv2.mean(gray_frame, mask=mask_rat)[0]
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            ret_fb, ff = cap.read()
            if ret_fb:
                ff_gray = cv2.cvtColor(ff, cv2.COLOR_BGR2GRAY) if len(ff.shape) == 3 else ff
                bg_brightness = cv2.mean(ff_gray, mask=pool_mask)[0]
            else:
                bg_brightness = 128.0

        contrast = abs(rat_brightness - bg_brightness)
        print(f"[autoconfig] rat_brightness={rat_brightness:.1f}  "
              f"bg_brightness={bg_brightness:.1f}  contrast={contrast:.1f}  "
              f"(from {len(rat_samples)} samples)", flush=True)

    # Compute appearance_threshold for the fallback detector:
    # midpoint between rat and background brightness.
    if rat_brightness is not None and bg_brightness is not None:
        appearance_threshold = int((rat_brightness + bg_brightness) / 2)
    else:
        appearance_threshold = 180  # safe default for bright rat / dark pool
    print(f"[autoconfig] appearance_threshold={appearance_threshold}", flush=True)

    # -------------------------------------------------------------------------
    # Measure temporal variance of the rat region to calibrate mog2_threshold.
    # MOG2 responds to per-pixel frame-to-frame change, not absolute brightness.
    # We collect N consecutive frames around a known rat detection and compute
    # the std-dev of each pixel inside the rat mask over time — that is exactly
    # the signal MOG2 models.  The median per-pixel std-dev inside the rat
    # region tells us how much the rat pixels actually vary, so we can set the
    # threshold just below that to reliably pick them up.
    # -------------------------------------------------------------------------
    TVAR_FRAMES  = 12   # consecutive frames to sample
    TVAR_SAMPLES = 4    # number of spread-out probe locations to average

    tvar_values = []

    if probe_result is not None:
        tvar_interval = max(1, (end_frame - start_frame) // (TVAR_SAMPLES + 1))
        for si in range(TVAR_SAMPLES):
            anchor = start_frame + (si + 1) * tvar_interval
            anchor = min(anchor, end_frame - TVAR_FRAMES - 1)
            res = _probe_for_rat(anchor, min(anchor + tvar_interval, end_frame))
            if res is None:
                continue
            t_frame, t_pos, t_cnt = res
            mask_rat = np.zeros(t_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_rat, [t_cnt], -1, 255, -1)
            pixel_coords = np.column_stack(np.where(mask_rat > 0))
            if len(pixel_coords) == 0:
                continue
            # Collect TVAR_FRAMES consecutive frames starting at anchor
            cap.set(cv2.CAP_PROP_POS_FRAMES, anchor)
            pixel_stack = []
            for _ in range(TVAR_FRAMES):
                ret2, frm2 = cap.read()
                if not ret2:
                    break
                gray2 = cv2.cvtColor(frm2, cv2.COLOR_BGR2GRAY) if len(frm2.shape) == 3 else frm2
                vals = gray2[pixel_coords[:, 0], pixel_coords[:, 1]].astype(np.float32)
                pixel_stack.append(vals)
            if len(pixel_stack) < 3:
                continue
            pixel_stack = np.array(pixel_stack)  # shape: (frames, pixels)
            per_pixel_std = np.std(pixel_stack, axis=0)
            tvar_values.append(float(np.median(per_pixel_std)))

    if tvar_values:
        median_tvar = float(np.median(tvar_values))
        # Set threshold to ~80% of median temporal variance so rat pixels reliably
        # exceed it, while static background pixels (near-zero variance) don't.
        suggested_threshold = max(8, int(round(median_tvar * 0.80)))
        print(f"[autoconfig] median_temporal_variance={median_tvar:.1f}  "
              f"suggested mog2_threshold={suggested_threshold}", flush=True)
    else:
        # Fallback: use contrast-based estimate if temporal variance failed
        if contrast is not None:
            CONTRAST_ANCHORS = [
                (0,   10), (20,  16), (35,  24),
                (55,  32), (80,  42), (120, 50),
            ]
            if contrast <= CONTRAST_ANCHORS[0][0]:
                suggested_threshold = CONTRAST_ANCHORS[0][1]
            elif contrast >= CONTRAST_ANCHORS[-1][0]:
                suggested_threshold = CONTRAST_ANCHORS[-1][1]
            else:
                for i in range(len(CONTRAST_ANCHORS) - 1):
                    c0, t0 = CONTRAST_ANCHORS[i]
                    c1, t1 = CONTRAST_ANCHORS[i + 1]
                    if c0 <= contrast <= c1:
                        frac = (contrast - c0) / (c1 - c0)
                        suggested_threshold = int(round(t0 + frac * (t1 - t0)))
                        break
        else:
            suggested_threshold = 32
        print(f"[autoconfig] temporal variance unavailable, "
              f"suggested mog2_threshold={suggested_threshold} (contrast fallback)", flush=True)

    # -------------------------------------------------------------------------
    # Step 2 — morph kernel sweep
    # Run ~120 frames spread across the session with the suggested threshold and
    # collect per-frame contour statistics to tune open_k and close_k.
    # -------------------------------------------------------------------------
    SWEEP_FRAMES   = 120
    sweep_interval = max(1, (end_frame - start_frame) // SWEEP_FRAMES)

    sweep_cfg = dict(cfg)
    sweep_cfg["mog2_threshold"]  = suggested_threshold
    sweep_cfg["morph_open_k"]    = cfg["morph_open_k"]   # current (resolution-scaled) defaults
    sweep_cfg["morph_close_k"]   = cfg["morph_close_k"]
    sweep_cfg["debug_frames"]    = 0

    sweep_sub = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = suggested_threshold,
        detectShadows = False,
    )
    # Warm it up properly from start
    warmup_begin = max(0, start_frame - cfg["mog2_history"])
    cap.set(cv2.CAP_PROP_POS_FRAMES, warmup_begin)
    for _ in range(start_frame - warmup_begin):
        ret, wf = cap.read()
        if not ret:
            break
        if len(wf.shape) == 3:
            wf = cv2.cvtColor(wf, cv2.COLOR_BGR2GRAY)
        sweep_sub.apply(wf, learningRate=-1.0)

    # Collect stats: noise contour count, fragmentation ratio, blob areas, displacements
    noise_counts      = []
    fragmentation     = []
    displacements     = []
    blob_areas        = []   # winning candidate area per frame (→ median_blob_area)
    prev_sweep_pos    = None

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    fi = start_frame
    while fi < end_frame:
        cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
        ret, frm = cap.read()
        if not ret:
            break

        gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY) if len(frm.shape) == 3 else frm
        fg   = sweep_sub.apply(gray, learningRate=-1.0)
        if pool_mask is not None:
            fg = cv2.bitwise_and(fg, fg, mask=pool_mask)

        k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                      (sweep_cfg["morph_open_k"],  sweep_cfg["morph_open_k"]))
        k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                      (sweep_cfg["morph_close_k"], sweep_cfg["morph_close_k"]))
        fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN,  k_open)
        fg = cv2.morphologyEx(fg, cv2.MORPH_CLOSE, k_close)

        contours, _ = cv2.findContours(fg, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        # Split contours into noise (too small) vs candidates (in area range)
        noise_cnt = 0
        valid_candidates = []
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area < sweep_cfg["min_contour_area"]:
                noise_cnt += 1
            elif area <= sweep_cfg["max_contour_area"]:
                M = cv2.moments(cnt)
                if M["m00"] > 0:
                    bx = int(M["m10"] / M["m00"])
                    by = int(M["m01"] / M["m00"])
                    if pool is None or point_in_ellipse(bx, by, *pool):
                        valid_candidates.append((bx, by, area))
        noise_counts.append(noise_cnt)

        # Collect split-candidate pairs for two-pass fragmentation evaluation.
        # We store (dist, combined_area) for frames with 2+ valid candidates;
        # evaluation happens after median_blob_area is known.
        if len(valid_candidates) >= 2:
            valid_candidates.sort(key=lambda c: c[2], reverse=True)
            top1 = valid_candidates[0]
            top2 = valid_candidates[1]
            dist_12       = euclidean_px((top1[0], top1[1]), (top2[0], top2[1]))
            combined_area = top1[2] + top2[2]
            fragmentation.append((dist_12, combined_area))
        else:
            fragmentation.append(None)

        # Collect winning blob area and displacement
        if valid_candidates:
            best = max(valid_candidates, key=lambda c: c[2])
            best_pos = (best[0], best[1])
            blob_areas.append(best[2])
            if prev_sweep_pos is not None:
                displacements.append(euclidean_px(prev_sweep_pos, best_pos))
            prev_sweep_pos = best_pos
        else:
            prev_sweep_pos = None

        fi += sweep_interval

    # -------------------------------------------------------------------------
    # Derive morph_open_k from noise floor
    # -------------------------------------------------------------------------
    avg_noise = sum(noise_counts) / len(noise_counts) if noise_counts else 0
    base_open_k = cfg["morph_open_k"]  # already resolution-scaled default
    if avg_noise > 10:
        open_k = base_open_k + 4
    elif avg_noise > 5:
        open_k = base_open_k + 2
    else:
        open_k = base_open_k
    open_k = max(3, open_k | 1)  # must be odd, at least 3

    # -------------------------------------------------------------------------
    # Derive median_blob_area and rat_body_radius_px from real detections
    # -------------------------------------------------------------------------
    if blob_areas:
        median_blob_area   = float(np.median(blob_areas))
        rat_body_radius_px = math.sqrt(median_blob_area / math.pi)
        partial_threshold  = median_blob_area * 0.50
        partial_rate       = sum(1 for a in blob_areas if a < partial_threshold) / len(blob_areas)
    else:
        median_blob_area   = cfg["min_contour_area"] * 3.0
        rat_body_radius_px = math.sqrt(median_blob_area / math.pi)
        partial_rate       = 0.0
    print(f"[autoconfig] median_blob_area={median_blob_area:.0f}  "
          f"rat_body_radius_px={rat_body_radius_px:.1f}  partial_rate={partial_rate:.2f}", flush=True)

    # -------------------------------------------------------------------------
    # Derive morph_close_k from split-rat fragmentation rate (two-pass)
    # A split rat produces two blobs whose combined area ≈ median_blob_area and
    # whose centroid distance is within [1×, 3×] rat_body_radius — not noise-close,
    # not two separate objects far apart.
    # -------------------------------------------------------------------------
    rat_diam_px = rat_body_radius_px * 2.0
    split_flags = []
    for entry in fragmentation:
        if entry is None:
            split_flags.append(False)
            continue
        dist_12, combined_area = entry
        area_match = 0.5 * median_blob_area <= combined_area <= 1.6 * median_blob_area
        dist_match = rat_diam_px * 0.8 <= dist_12 <= rat_diam_px * 3.5
        split_flags.append(area_match and dist_match)

    frag_rate = sum(split_flags) / len(split_flags) if split_flags else 0
    base_close_k = cfg["morph_close_k"]
    if frag_rate > 0.3:
        close_k = base_close_k + 12
    elif frag_rate > 0.15:
        close_k = base_close_k + 6
    else:
        close_k = base_close_k
    close_k = max(3, close_k | 1)

    print(f"[autoconfig] avg_noise={avg_noise:.1f}  frag_rate={frag_rate:.2f}", flush=True)
    print(f"[autoconfig] suggested morph_open_k={open_k}  morph_close_k={close_k}", flush=True)

    # -------------------------------------------------------------------------
    # Derive mog2_history_s from speed variance AND partial-detection rate
    # -------------------------------------------------------------------------
    if displacements:
        near_zero   = sum(1 for d in displacements if d < 5.0)
        zero_ratio  = near_zero / len(displacements)
        disp_std    = float(np.std(displacements))

        # Partial-detection rate is the most direct signal for ghost absorption:
        # if the rat is frequently only half-detected, shorten history aggressively.
        if partial_rate > 0.35 or zero_ratio > 0.3 or disp_std > mean_pool_r_px * 0.15:
            suggested_history_s = 1.5
        elif partial_rate > 0.20 or zero_ratio > 0.15:
            suggested_history_s = 2.5
        else:
            suggested_history_s = 4.0
        print(f"[autoconfig] zero_ratio={zero_ratio:.2f}  disp_std={disp_std:.1f}  "
              f"suggested mog2_history_s={suggested_history_s}", flush=True)
    else:
        suggested_history_s = 4.0
        print("[autoconfig] Not enough displacement data, keeping mog2_history_s=4.0", flush=True)

    return {
        "mog2_threshold":     suggested_threshold,
        "morph_open_k":       open_k,
        "morph_close_k":      close_k,
        "mog2_history_s":     suggested_history_s,
        "median_blob_area":   median_blob_area,
        "rat_body_radius_px": rat_body_radius_px,
        "appearance_threshold": appearance_threshold,
    }


def main():
    parser = argparse.ArgumentParser(description="Track a rat in a water maze video.")
    parser.add_argument("--video",               required=True,  type=str)
    parser.add_argument("--start",               default=None,   type=float)
    parser.add_argument("--end",                 default=None,   type=float)
    parser.add_argument("--pool_radius_cm",      default=60,     type=float)
    parser.add_argument("--mog2_history_s",      default=4.0,    type=float)
    parser.add_argument("--mog2_threshold",      default=32,     type=float)
    parser.add_argument("--mog2_detect_shadow",  default=False,  action="store_true")
    parser.add_argument("--mog2_learning_rate",  default=-1.0,   type=float)
    parser.add_argument("--morph_open_k",        default=3,      type=int)
    parser.add_argument("--morph_close_k",       default=15,     type=int)
    parser.add_argument("--min_contour_area",    default=300,    type=float)
    parser.add_argument("--max_contour_area",    default=12000,  type=float)
    parser.add_argument("--trail_s",             default=2.0,    type=float)
    parser.add_argument("--max_interp_gap",      default=0,      type=int)
    parser.add_argument("--heatmap_sigma",       default=0,      type=float)
    parser.add_argument("--debug_frames",        default=0,      type=int)
    parser.add_argument("--pool_west",           default=None,   type=str)
    parser.add_argument("--pool_north",          default=None,   type=str)
    parser.add_argument("--pool_east",           default=None,   type=str)
    parser.add_argument("--pool_south",          default=None,   type=str)
    parser.add_argument("--platform_nw",         default=None,   type=str)
    parser.add_argument("--platform_ne",         default=None,   type=str)
    parser.add_argument("--platform_se",         default=None,   type=str)
    parser.add_argument("--platform_sw",         default=None,   type=str)
    parser.add_argument("--quadrantcross",       default=False,  action="store_true")
    parser.add_argument("--platformcross",       default=False,  action="store_true")
    parser.add_argument("--paraplatform",        default=None,   type=int,    nargs="?", const=4)
    parser.add_argument("--proximity",           default=False,  action="store_true")
    parser.add_argument("--latency",             default=False,  action="store_true")
    parser.add_argument("--tracemapcolor",       default=None,   type=str)
    parser.add_argument("--appmode",             default=False,  action="store_true")
    parser.add_argument("--ratcolor",            default=None,   type=str)
    parser.add_argument("--colorall",            default=False,  action="store_true")
    parser.add_argument("--autoconfig",          default=False,  action="store_true", help="Auto-detect optimal mog2_threshold, morph kernels, and mog2_history_s from the video")
    args = parser.parse_args()

    tracemap_color   = parse_tracemap_color(args.tracemapcolor)
    if args.ratcolor:
        rat_color = parse_tracemap_color(args.ratcolor)
    elif args.colorall:
        rat_color = NAMED_COLORS["yellow"]
    else:
        rat_color = None
    secondary_color = tuple(max(0, int(c * 0.60)) for c in rat_color) if args.colorall and rat_color is not None else None
    require_platform = needs_platform(args)

    cfg = {
        "pool_radius_cm":     args.pool_radius_cm,
        "mog2_history":       0,
        "mog2_threshold":     args.mog2_threshold,
        "mog2_detect_shadow": args.mog2_detect_shadow,
        "mog2_learning_rate": args.mog2_learning_rate,
        "morph_open_k":       args.morph_open_k,
        "morph_close_k":      args.morph_close_k,
        "min_contour_area":   args.min_contour_area,
        "max_contour_area":   args.max_contour_area,
        "trail_len":          0,
        "debug_frames":       args.debug_frames,
        "pool_west":          parse_point(args.pool_west)   if args.pool_west   else None,
        "pool_north":         parse_point(args.pool_north)  if args.pool_north  else None,
        "pool_east":          parse_point(args.pool_east)   if args.pool_east   else None,
        "pool_south":         parse_point(args.pool_south)  if args.pool_south  else None,
        "platform_nw":        parse_point(args.platform_nw) if args.platform_nw else None,
        "platform_ne":        parse_point(args.platform_ne) if args.platform_ne else None,
        "platform_se":        parse_point(args.platform_se) if args.platform_se else None,
        "platform_sw":        parse_point(args.platform_sw) if args.platform_sw else None,
        "app_mode":           args.appmode,
    }

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap          = cv2.VideoCapture(str(video_path))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 4.0
    frame_h      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_dt     = 1.0 / fps

    _ref_w, _ref_h = 1280, 720
    _lin_scale  = min(frame_w, frame_h) / min(_ref_w, _ref_h)
    _area_scale = (frame_w * frame_h) / (_ref_w * _ref_h)

    cfg["mog2_history"] = max(1, int(round(args.mog2_history_s * fps)))
    cfg["trail_len"]    = max(1, int(round(args.trail_s * fps)))

    if args.morph_open_k == 3:
        cfg["morph_open_k"]  = max(3, int(round(args.morph_open_k  * _lin_scale)) | 1)
    if args.morph_close_k == 15:
        cfg["morph_close_k"] = max(3, int(round(args.morph_close_k * _lin_scale)) | 1)
    if args.min_contour_area == 300:
        cfg["min_contour_area"] = args.min_contour_area * _area_scale
    if args.max_contour_area == 12000:
        cfg["max_contour_area"] = args.max_contour_area * _area_scale

    start_frame = int(args.start * fps) if args.start is not None else 0
    end_frame   = int(args.end   * fps) if args.end   is not None else total_frames

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    if args.appmode:
        if pool_coords_valid(cfg):
            pool_confirmed = appmode_confirm(cfg, "pool")
            if not pool_confirmed:
                result = appmode_calib(require_platform)
                if result is None:
                    raise RuntimeError("Calibration aborted.")
                cfg.update(result)
            else:
                if require_platform:
                    if platform_coords_valid(cfg):
                        plat_confirmed = appmode_confirm(cfg, "platform")
                        if not plat_confirmed:
                            result = appmode_calib(require_platform=True, existing_pool=cfg)
                            if result is None:
                                raise RuntimeError("Platform calibration aborted.")
                            cfg.update(result)
                    else:
                        result = appmode_calib(require_platform=True, existing_pool=cfg)
                        if result is None:
                            raise RuntimeError("Platform calibration aborted.")
                        cfg.update(result)
                else:
                    cfg["platform_nw"] = None
                    cfg["platform_ne"] = None
                    cfg["platform_se"] = None
                    cfg["platform_sw"] = None
        else:
            result = appmode_calib(require_platform)
            if result is None:
                raise RuntimeError("Calibration aborted.")
            cfg.update(result)
            if not require_platform:
                cfg["platform_nw"] = None
                cfg["platform_ne"] = None
                cfg["platform_se"] = None
                cfg["platform_sw"] = None

        ret, first_frame = cap.read()
        if not ret:
            raise RuntimeError("Could not read first frame from video.")
    else:
        ret, first_frame = cap.read()
        if not ret:
            raise RuntimeError("Could not read first frame from video.")
        if pool_coords_valid(cfg):
            confirmed = confirm_pool_from_args(first_frame, cfg)
            if not confirmed:
                result = run_calibration(first_frame, require_platform=require_platform)
                if result is None:
                    raise RuntimeError("Pool calibration aborted.")
                cfg.update(result)
            else:
                if require_platform:
                    if platform_coords_valid(cfg):
                        plat_confirmed = confirm_platform_from_args(first_frame, cfg)
                        if not plat_confirmed:
                            plat_result = run_platform_calibration(first_frame)
                            if plat_result is None:
                                raise RuntimeError("Platform calibration aborted.")
                            cfg.update(plat_result)
                    else:
                        plat_result = run_platform_calibration(first_frame)
                        if plat_result is None:
                            raise RuntimeError("Platform calibration aborted.")
                        cfg.update(plat_result)
                else:
                    cfg["platform_nw"] = None
                    cfg["platform_ne"] = None
                    cfg["platform_se"] = None
                    cfg["platform_sw"] = None
        else:
            result = run_calibration(first_frame, require_platform=require_platform)
            if result is None:
                raise RuntimeError("Calibration aborted.")
            cfg.update(result)
            if not require_platform:
                cfg["platform_nw"] = None
                cfg["platform_ne"] = None
                cfg["platform_se"] = None
                cfg["platform_sw"] = None

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    west  = cfg["pool_west"]
    north = cfg["pool_north"]
    east  = cfg["pool_east"]
    south = cfg["pool_south"]
    r_cm  = cfg["pool_radius_cm"]

    ellipse = pool_ellipse_from_nsew(west, north, east, south)
    if ellipse is None:
        raise RuntimeError("Could not compute pool ellipse from calibration points.")
    cx, cy, rx, ry, angle = ellipse

    raw_rx_px = math.hypot(east[0] - west[0],  east[1] - west[1])  / 2
    raw_ry_px = math.hypot(south[0] - north[0], south[1] - north[1]) / 2
    scale_x = r_cm / raw_rx_px
    scale_y = r_cm / raw_ry_px

    pool      = (cx, cy, rx, ry, angle)
    pool_mask = make_ellipse_mask((frame_h, frame_w), *pool)

    # --autoconfig: probe the video to derive optimal detection parameters.
    # Must run after pool geometry is established (needs pool_mask and pool tuple)
    # but before the main subtractor is created so we can apply the results.
    if args.autoconfig:
        ac = run_autoconfig(cap, fps, total_frames, start_frame, end_frame,
                            cfg, pool_mask, pool)
        cfg["mog2_threshold"] = ac["mog2_threshold"]
        cfg["morph_open_k"]   = ac["morph_open_k"]
        cfg["morph_close_k"]  = ac["morph_close_k"]
        cfg["mog2_history"]   = max(1, int(round(ac["mog2_history_s"] * fps)))
        cfg["mog2_history_s"] = ac["mog2_history_s"]
        cfg["median_blob_area"]     = ac["median_blob_area"]
        cfg["rat_body_radius_px"]   = ac["rat_body_radius_px"]
        cfg["appearance_threshold"] = ac["appearance_threshold"]
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    has_platform = require_platform and platform_coords_valid(cfg)
    platform_corners = None
    if has_platform:
        platform_corners = [cfg["platform_nw"], cfg["platform_ne"],
                            cfg["platform_se"], cfg["platform_sw"]]

    para_scale       = None
    para_side_scale  = None
    para_corners     = None
    para_time_s      = 0.0
    para_dist_cm     = 0.0
    para_exits       = 0
    prev_inside_para = False

    if args.paraplatform is not None and has_platform:
        para_scale      = args.paraplatform
        para_side_scale = math.sqrt(para_scale)
        para_corners    = scale_platform_corners(platform_corners, para_side_scale)

    latency_time_s               = None
    latency_dist_cm              = None
    latency_done                 = False
    latency_dist_acc             = 0.0
    prev_inside_plat_for_latency = False

    para_latency_time_s               = None
    para_latency_dist_cm              = None
    para_latency_done                 = False
    para_latency_dist_acc             = 0.0
    prev_inside_para_for_latency      = False

    ts            = datetime.now().strftime("%y-%m-%d_%H-%M-%S")
    output_dir    = video_path.parent
    video_out     = output_dir / f"{video_path.stem}_{ts}.mp4"
    csv_path      = output_dir / f"{video_path.stem}_{ts}_coordinates.csv"
    summary_path  = output_dir / f"{video_path.stem}_{ts}_summary.txt"
    tracemap_path = output_dir / f"{video_path.stem}_{ts}_tracemap.jpg"
    heatmap_path  = output_dir / f"{video_path.stem}_{ts}_heatmap.jpg"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )

    warmup_frames = min(cfg["mog2_history"], start_frame if start_frame > 0 else end_frame)
    warmup_start  = max(0, start_frame - warmup_frames)
    cap.set(cv2.CAP_PROP_POS_FRAMES, warmup_start)
    for _ in range(start_frame - warmup_start):
        ret, wf = cap.read()
        if not ret:
            break
        if len(wf.shape) == 3:
            wf = cv2.cvtColor(wf, cv2.COLOR_BGR2GRAY)
        subtractor.apply(wf, learningRate=cfg["mog2_learning_rate"])
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    records              = []
    trail                = []
    frame_idx            = 0
    running_dist_px      = 0.0
    running_dist_cm      = 0.0
    prev_pos             = None
    q_stats              = empty_quadrant_stats()
    q_exits              = empty_quadrant_exits() if args.quadrantcross else None
    platform_exits       = 0
    prev_inside_platform = False
    loop_start           = time.time()
    missed_candidates    = {}  # frame record-index -> raw candidate list, for retroactive correction
    appearance_frames    = {}  # frame record-index -> raw frame, for appearance retroactive fill
    miss_streak          = 0
    APPEARANCE_TRIGGER   = 7  # consecutive MOG2 misses before appearance scan

    live_proximity_sum    = 0.0
    live_proximity_count  = 0

    processable_frames = end_frame - start_frame

    while True:
        current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        if current_pos >= end_frame:
            break

        ret, frame = cap.read()
        if not ret:
            break

        timestamp = (start_frame + frame_idx) / fps
        pos, rat_contour, raw_candidates = detect_rat(frame, subtractor, cfg, pool_mask, pool, frame_idx, prev_pos)

        if pos is None:
            missed_candidates[frame_idx] = raw_candidates
            miss_streak += 1
            appearance_frames[frame_idx] = frame.copy()
            # Once streak hits threshold, run appearance detector on all missed frames
            # so retroactive_jump_correction has candidates to walk back through.
            if miss_streak == APPEARANCE_TRIGGER:
                streak_start_idx = frame_idx - (miss_streak - 1)
                for fi in range(streak_start_idx, frame_idx + 1):
                    if fi in appearance_frames and not missed_candidates.get(fi):
                        app_candidates = detect_rat_appearance(
                            appearance_frames[fi], cfg, pool_mask, pool, prev_pos)
                        if app_candidates:
                            missed_candidates[fi] = app_candidates
        else:
            # On re-lock after a streak, run appearance on any remaining missed frames
            # that still have no candidates (MOG2 or appearance).
            if miss_streak >= APPEARANCE_TRIGGER:
                streak_start_idx = frame_idx - miss_streak
                for fi in range(streak_start_idx, frame_idx):
                    if fi in appearance_frames and not missed_candidates.get(fi):
                        app_candidates = detect_rat_appearance(
                            appearance_frames[fi], cfg, pool_mask, pool, prev_pos)
                        if app_candidates:
                            missed_candidates[fi] = app_candidates
            miss_streak = 0
            appearance_frames.clear()

        if pos and prev_pos:
            seg_dist_cm = euclidean_cm(prev_pos, pos, scale_x, scale_y)
            running_dist_px += euclidean_px(prev_pos, pos)
            running_dist_cm += seg_dist_cm
            accumulate_segment(q_stats, prev_pos, pos, west, north, east, south,
                               frame_dt, scale_x, scale_y)
            if args.quadrantcross:
                count_quadrant_exits(prev_pos, pos, west, north, east, south, q_exits)
        elif pos and prev_pos is None:
            accumulate_static(q_stats, pos, west, north, east, south, frame_dt)
        elif pos and prev_pos == pos:
            accumulate_static(q_stats, pos, west, north, east, south, frame_dt)

        if args.platformcross and has_platform and pos:
            curr_inside = point_in_platform(pos, platform_corners)
            if prev_pos is not None:
                if prev_inside_platform and not curr_inside:
                    platform_exits += 1
                elif not prev_inside_platform and not curr_inside:
                    if segment_crosses_platform_twice(prev_pos, pos, platform_corners):
                        platform_exits += 1
            prev_inside_platform = curr_inside

        if para_corners is not None and pos:
            curr_inside_para = point_in_platform(pos, para_corners)
            if prev_pos is not None:
                if curr_inside_para:
                    frac = 0.5 if not prev_inside_para else 1.0
                    para_time_s  += frac * frame_dt
                    para_dist_cm += euclidean_cm(prev_pos, pos, scale_x, scale_y) * frac
                if prev_inside_para and not curr_inside_para:
                    para_exits += 1
                elif not prev_inside_para and not curr_inside_para:
                    if segment_crosses_platform_twice(prev_pos, pos, para_corners):
                        para_exits += 1
            elif curr_inside_para:
                para_time_s += frame_dt
            prev_inside_para = curr_inside_para

        if args.latency and has_platform and not latency_done and pos:
            if prev_pos is not None:
                latency_dist_acc += euclidean_cm(prev_pos, pos, scale_x, scale_y)
                if segment_enters_platform(prev_pos, pos, platform_corners, prev_inside_plat_for_latency):
                    latency_time_s  = timestamp
                    latency_dist_cm = latency_dist_acc
                    latency_done    = True
            prev_inside_plat_for_latency = point_in_platform(pos, platform_corners)

        if args.latency and para_corners is not None and not para_latency_done and pos:
            if prev_pos is not None:
                para_latency_dist_acc += euclidean_cm(prev_pos, pos, scale_x, scale_y)
                if segment_enters_platform(prev_pos, pos, para_corners, prev_inside_para_for_latency):
                    para_latency_time_s  = timestamp
                    para_latency_dist_cm = para_latency_dist_acc
                    para_latency_done    = True
            prev_inside_para_for_latency = point_in_platform(pos, para_corners)

        if args.proximity and has_platform and pos:
            pcx, pcy = platform_center(platform_corners)
            live_proximity_sum   += euclidean_cm(pos, (pcx, pcy), scale_x, scale_y)
            live_proximity_count += 1

        if pos:
            prev_pos = pos

        records.append({
            "frame":        start_frame + frame_idx,
            "timestamp_s":  round(timestamp, 4),
            "x":            pos[0] if pos else None,
            "y":            pos[1] if pos else None,
            "interpolated": False,
        })

        annotated = frame.copy()
        if rat_color is not None:
            if rat_contour is not None:
                draw_color = secondary_color if args.colorall else rat_color
                cv2.drawContours(annotated, [rat_contour], -1, draw_color, -1)
            if args.colorall:
                for bx, by, area, cnt in raw_candidates:
                    if cnt is rat_contour:
                        continue
                    cv2.drawContours(annotated, [cnt], -1, secondary_color, -1)
        cv2.ellipse(annotated, (cx, cy), (rx, ry), angle, 0, 360, (255, 100, 0), thickness=2)
        cv2.line(annotated, north, south, (255, 100, 0), 1)
        cv2.line(annotated, west,  east,  (255, 100, 0), 1)
        for pt in [west, north, east, south, (cx, cy)]:
            cv2.circle(annotated, pt, sc(annotated, 5), (255, 100, 0), -1)
            cv2.circle(annotated, pt, sc(annotated, 7), (255, 255, 255), 1)

        if has_platform:
            pts_np = np.array(platform_corners, dtype=np.int32)
            cv2.polylines(annotated, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
            for i, (corner_name, _) in enumerate(PLATFORM_STEPS):
                pt = platform_corners[i]
                cv2.circle(annotated, pt, sc(annotated, 4), PLATFORM_COLORS[corner_name], -1)

        if para_corners is not None:
            para_pts_np = np.array([(int(p[0]), int(p[1])) for p in para_corners], dtype=np.int32)
            cv2.polylines(annotated, [para_pts_np], isClosed=True, color=(0, 180, 255), thickness=2)

        def quadrant_label_pos(qa, qb):
            mx = (qa[0] + qb[0]) // 2
            my = (qa[1] + qb[1]) // 2
            return (int(mx * 0.6 + cx * 0.4), int(my * 0.6 + cy * 0.4))

        for q, lp in {
            "NE": quadrant_label_pos(north, east),
            "NW": quadrant_label_pos(north, west),
            "SW": quadrant_label_pos(south, west),
            "SE": quadrant_label_pos(south, east),
        }.items():
            cv2.putText(annotated, q, lp, cv2.FONT_HERSHEY_DUPLEX, sc_f(annotated, 0.55), QUADRANT_COLORS[q], 1, cv2.LINE_AA)

        if pos:
            trail.append(pos)
            if len(trail) > cfg["trail_len"]:
                trail.pop(0)
        for i in range(1, len(trail)):
            alpha = i / len(trail)
            cv2.line(annotated, trail[i - 1], trail[i],
                     (0, int(255 * alpha), int(100 * (1 - alpha))), 2)
        if pos:
            cv2.circle(annotated, pos, sc(annotated, 8),  (0, 0, 255), -1)
            cv2.circle(annotated, pos, sc(annotated, 10), (255, 255, 255), 1)

        status    = 'DETECTED' if pos else 'INTERPOLATED'
        hud_color = (0, 210, 0) if pos else (0, 210, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        hud_dist  = f"{running_dist_px:.1f} px  |  {running_dist_cm:.1f} cm"

        hud_lines = [
            (f"Frame: {frame_idx}   t = {timestamp:.2f}s", (220, 220, 220)),
            (f"Position: {pos_str}",                        (220, 220, 220)),
            (status,                                                     hud_color),
            (f"Dist: {hud_dist}",                           (255, 200, 50)),
        ]
        if args.platformcross and has_platform:
            hud_lines.append((f"Platform exits: {platform_exits}", (200, 200, 50)))
        if para_corners is not None:
            hud_lines.append((f"ParaPlatform  T:{para_time_s:.1f}s D:{para_dist_cm:.1f}cm X:{para_exits}", (0, 180, 255)))
        if args.proximity and has_platform:
            live_prox = (live_proximity_sum / live_proximity_count) if live_proximity_count > 0 else 0.0
            hud_lines.append((f"Proximity: {live_prox:.1f}cm", (180, 130, 255)))
        if args.latency and has_platform:
            if latency_done:
                hud_lines.append((f"Latency: {latency_time_s:.2f}s / {latency_dist_cm:.2f}cm", (180, 255, 100)))
            else:
                hud_lines.append(('Latency: tracking...', (180, 180, 180)))
        if args.latency and para_corners is not None:
            if para_latency_done:
                hud_lines.append((f"Para Latency: {para_latency_time_s:.2f}s / {para_latency_dist_cm:.2f}cm", (100, 255, 180)))
            else:
                hud_lines.append(('Para Latency: tracking...', (140, 140, 140)))

        line_h  = sc(annotated, 26)
        hud_pad = sc(annotated, 10)
        hud_w   = sc(annotated, 420)
        hud_h   = hud_pad + len(hud_lines) * line_h + hud_pad // 2
        hud_x   = sc(annotated, 6)
        hud_y   = sc(annotated, 6)
        draw_transparent_banner(annotated, hud_x, hud_y, hud_x + hud_w, hud_y + hud_h)
        hud_fs = sc_f(annotated, 0.52)
        for li, (text, color) in enumerate(hud_lines):
            cv2.putText(annotated, text,
                        (hud_x + hud_pad, hud_y + hud_pad + (li + 1) * line_h - sc(annotated, 4)),
                        cv2.FONT_HERSHEY_DUPLEX, hud_fs, color, 1, cv2.LINE_AA)

        total_q_time = sum(v["time_s"]  for v in q_stats.values())
        total_q_dist = sum(v["dist_cm"] for v in q_stats.values())
        draw_leaderboard(annotated, q_stats, total_q_time, total_q_dist, quad_exits=q_exits)

        writer.write(annotated)
        frame_idx += 1
        emit_progress(frame_idx, processable_frames, loop_start, cfg["app_mode"])

    if not cfg["app_mode"]:
        print()

    cap.release()
    writer.release()

    detected      = sum(1 for r in records if r["x"] is not None)

    # Before interpolating, attempt to recover missed frames using saved candidate
    # lists walked backwards from the re-lock position. jump_threshold_px is set to
    # half the pool's mean pixel radius — a generous but physically plausible limit.
    jump_threshold_px = (rx + ry) / 2 * 0.5
    retroactive_jump_correction(records, missed_candidates, jump_threshold_px)

    records       = interpolate_missing(records, max_gap=args.max_interp_gap)
    missing_after = sum(1 for r in records if r["x"] is None)

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
                                   west, north, east, south, frame_dt, scale_x, scale_y)
                valid_pairs += 1
            else:
                accumulate_static(q_stats_final, curr, west, north, east, south, frame_dt)
            prev = curr

    total_q_time = sum(v["time_s"]  for v in q_stats_final.values())
    total_q_dist = sum(v["dist_cm"] for v in q_stats_final.values())

    proximity_avg_cm   = None
    proximity_n_frames = 0
    if args.proximity and has_platform:
        pcx, pcy = platform_center(platform_corners)
        dists = [
            euclidean_cm((rec["x"], rec["y"]), (pcx, pcy), scale_x, scale_y)
            for rec in records if rec["x"] is not None
        ]
        if dists:
            proximity_avg_cm   = sum(dists) / len(dists)
            proximity_n_frames = len(dists)

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)

    sorted_q = sorted(QUADRANT_NAMES, key=lambda q: q_stats_final[q]["time_s"], reverse=True)
    col_q  = 'Quadrant'
    col_t  = 'Time (s)'
    col_tp = 'Time (%)'
    col_d  = 'Dist (cm)'
    col_dp = 'Dist (%)'
    col_ex = 'Exits'

    rerun_cmd = build_rerun_command(video_path, args, cfg)

    detected      = sum(1 for r in records if r["x"] is not None and not r["interpolated"])
    missing_after = sum(1 for r in records if r["x"] is None)
    valid_pairs_n = valid_pairs

    lines = [
        f"Video           : {video_path.name}",
        f"Resolution      : {frame_w}x{frame_h}",
        f"Total frames    : {frame_idx}",
        f"FPS             : {fps:.2f}",
        f"Duration (s)    : {frame_idx / fps:.2f}",
        f"Start time (s)  : {args.start if args.start is not None else 0}",
        f"End time (s)    : {args.end if args.end is not None else round(frame_idx / fps, 2)}",
        "",
        '-- Pool Calibration Points --',
        f"Pool West       : {cfg['pool_west']}",
        f"Pool North      : {cfg['pool_north']}",
        f"Pool East       : {cfg['pool_east']}",
        f"Pool South      : {cfg['pool_south']}",
        "",
    ]

    if has_platform:
        lines += [
            '-- Platform Calibration Points --',
            f"Platform NW     : {cfg['platform_nw']}",
            f"Platform NE     : {cfg['platform_ne']}",
            f"Platform SE     : {cfg['platform_se']}",
            f"Platform SW     : {cfg['platform_sw']}",
        ]
        if args.platformcross:
            lines.append(f"Platform exits  : {platform_exits}")
        lines.append("")

    lines += [
        f"Detected frames : {detected}",
        f"Interpolated    : {sum(1 for r in records if r['interpolated'])}",
        f"Missing (no pos): {missing_after}",
        "",
        f"Pool radius     : {cfg['pool_radius_cm']} cm",
        f"Scale X         : {scale_x:.4f} cm/px  (horizontal)",
        f"Scale Y         : {scale_y:.4f} cm/px  (vertical)",
        "",
        f"Total distance  : {total_dist_px:.2f} px",
        f"Total distance  : {total_dist_cm:.2f} cm",
        f"  (over {valid_pairs_n} consecutive frame pairs)",
        "",
        '-- Quadrant Analysis (sorted by time spent) --',
    ]

    if args.quadrantcross:
        lines.append(f"{col_q:<10} {col_t:>10} {col_tp:>10} {col_d:>12} {col_dp:>10} {col_ex:>8}")
        lines.append(f"{'-'*66}")
    else:
        lines.append(f"{col_q:<10} {col_t:>10} {col_tp:>10} {col_d:>12} {col_dp:>10}")
        lines.append(f"{'-'*56}")

    for q in sorted_q:
        t_s   = q_stats_final[q]["time_s"]
        d_cm  = q_stats_final[q]["dist_cm"]
        t_pct = (t_s  / total_q_time * 100) if total_q_time > 0 else 0.0
        d_pct = (d_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
        if args.quadrantcross:
            lines.append(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}% {q_exits.get(q, 0):>8}")
        else:
            lines.append(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%")

    total_label = 'TOTAL'
    if args.quadrantcross:
        lines += [
            f"{'-'*66}",
            f"{total_label:<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}% {sum(q_exits.values()):>8}",
        ]
    else:
        lines += [
            f"{'-'*56}",
            f"{total_label:<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%",
        ]

    if args.quadrantcross:
        lines += ["", '-- Quadrant Exits --']
        for q in QUADRANT_NAMES:
            lines.append(f"{q} exits       : {q_exits.get(q, 0)}")

    if para_corners is not None:
        t_pct = (para_time_s / total_q_time * 100) if total_q_time > 0 else 0.0
        d_pct = (para_dist_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
        lines += [
            "",
            f"-- ParaPlatform Analysis (scale: {para_scale}x area / {para_side_scale:.2f}x side) --",
            f"ParaPlatform time  : {para_time_s:.2f} s  ({t_pct:.1f}% of total)",
            f"ParaPlatform dist  : {para_dist_cm:.2f} cm ({d_pct:.1f}% of total)",
            f"ParaPlatform exits : {para_exits}",
        ]

    if args.proximity and proximity_avg_cm is not None:
        lines += [
            "",
            '-- Proximity to Platform --',
            f"Avg dist to center : {proximity_avg_cm:.2f} cm  (over {proximity_n_frames} frames)",
        ]

    if args.latency and has_platform:
        lines += ["", '-- Latency to Platform --']
        if latency_done:
            lines += [
                f"Time to first entry: {latency_time_s:.2f} s",
                f"Dist to first entry: {latency_dist_cm:.2f} cm",
            ]
        else:
            lines.append('Rat never entered platform during session')

    if args.latency and para_corners is not None:
        lines += ["", '-- Latency to ParaPlatform --']
        if para_latency_done:
            lines += [
                f"Time to first para entry: {para_latency_time_s:.2f} s",
                f"Dist to first para entry: {para_latency_dist_cm:.2f} cm",
            ]
        else:
            lines.append('Rat never entered paraplatform during session')

    lines += ["", '-- Re-run Command --', rerun_cmd]

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    heatmap_sigma = args.heatmap_sigma if args.heatmap_sigma > 0 else max(5, int(round(min(frame_w, frame_h) / 40)))
    tracemap(records, first_frame, output_dir, video_path, ts, color=tracemap_color)
    heatmap(records, first_frame, output_dir, video_path, ts, sigma=heatmap_sigma)

    if not cfg["app_mode"]:
        print("\n" + "\n".join(lines))

    if cfg["app_mode"]:
        def fmt_pt_list(pt):
            if pt is None:
                return None
            return f"{pt[0]},{pt[1]}"

        out = {
            "done":             True,
            "video_out":        str(video_out),
            "csv_out":          str(csv_path),
            "summary_out":      str(summary_path),
            "tracemap_out":     str(tracemap_path),
            "heatmap_out":      str(heatmap_path),
            "pool_west":        fmt_pt_list(cfg.get("pool_west")),
            "pool_north":       fmt_pt_list(cfg.get("pool_north")),
            "pool_east":        fmt_pt_list(cfg.get("pool_east")),
            "pool_south":       fmt_pt_list(cfg.get("pool_south")),
            "platform_nw":      fmt_pt_list(cfg.get("platform_nw")),
            "platform_ne":      fmt_pt_list(cfg.get("platform_ne")),
            "platform_se":      fmt_pt_list(cfg.get("platform_se")),
            "platform_sw":      fmt_pt_list(cfg.get("platform_sw")),
            "total_dist_cm":    round(total_dist_cm, 2),
            "total_frames":     frame_idx,
            "detected":         detected,
            "platform_exits":   platform_exits if args.platformcross and has_platform else None,
            "para_time_s":      round(para_time_s, 3)  if para_corners is not None else None,
            "para_dist_cm":     round(para_dist_cm, 3) if para_corners is not None else None,
            "para_exits":       para_exits             if para_corners is not None else None,
            "proximity_avg_cm": round(proximity_avg_cm, 3) if proximity_avg_cm is not None else None,
            "latency_time_s":   round(latency_time_s, 3)   if latency_done else None,
            "latency_dist_cm":  round(latency_dist_cm, 3)  if latency_done else None,
            "para_latency_time_s":  round(para_latency_time_s, 3)  if para_latency_done else None,
            "para_latency_dist_cm": round(para_latency_dist_cm, 3) if para_latency_done else None,
            "ac_mog2_threshold":  cfg["mog2_threshold"]  if args.autoconfig else None,
            "ac_morph_open_k":    cfg["morph_open_k"]    if args.autoconfig else None,
            "ac_morph_close_k":   cfg["morph_close_k"]   if args.autoconfig else None,
            "ac_mog2_history_s":  cfg.get("mog2_history_s", args.mog2_history_s) if args.autoconfig else None,
        }
        if args.quadrantcross:
            out["quadrant_exits"] = q_exits
        print(json.dumps(out), flush=True)

if __name__ == "__main__":
    main()