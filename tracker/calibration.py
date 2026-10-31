import cv2
import json
import math
import sys
import numpy as np

from .constants import CALIB_STEPS, CALIB_COLORS, PLATFORM_STEPS, PLATFORM_COLORS
from .geometry  import pool_ellipse_from_nsew, scale_platform_corners
from .drawing   import sc, sc_f, draw_transparent_banner
from .cli       import parse_point


def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_west", "pool_north", "pool_east", "pool_south"))

def platform_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("platform_nw", "platform_ne", "platform_se", "platform_sw"))

def needs_platform(args) -> bool:
    return any([args.platformcross, args.paraplatform is not None,
                args.proximity, args.latency])


def run_calibration(frame: np.ndarray, require_platform: bool = False, para_scale: int = 4) -> dict | None:
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
            cv2.putText(img, cardinal,
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
                para_preview = scale_platform_corners(corners_ordered, math.sqrt(para_scale))
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
        cv2.putText(img, cardinal,
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
