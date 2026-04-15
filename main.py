import cv2
import numpy as np
import csv
import math
import json
import argparse
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

STRINGS = {
    "en": {
        "calib_step":           "Step {step}/4 -- Click on the {cardinal} point of the pool edge",
        "calib_redo":           "Press  R  to redo all points   |   ESC to abort",
        "calib_confirm":        "All 4 points set -- press ENTER to confirm or R to redo",
        "calib_abort":          "Press  ESC  to abort without saving",
        "calib_post_confirm":   "ENTER  -->  Continue without platform     M  -->  Pick platform corners",
        "confirm_title":        "Saved pool coordinates found -- confirm or repick",
        "confirm_hint":         "ENTER  -->  Continue with these coordinates     ESC  -->  Repick",
        "platform_step":        "Platform Step {step}/4 -- Click the {corner} corner (clockwise)",
        "platform_redo":        "Press  R  to redo all points   |   ESC to skip platform",
        "platform_confirm":     "All 4 corners set -- press ENTER to confirm or R to redo",
        "platform_skip":        "ESC  -->  skip platform",
        "platform_confirm_title":"Saved platform coordinates found -- confirm or repick",
        "platform_confirm_hint":"ENTER  -->  Continue with these coordinates     ESC  -->  Repick",
        "status_detected":      "DETECTED",
        "status_missing":       "MISSING",
        "hud_frame":            "Frame: {frame}   t = {time:.2f}s",
        "hud_position":         "Position: {pos}",
        "hud_dist":             "Dist: {dist}",
        "hud_platform_exits":   "Platform exits: {n}",
        "leaderboard_title":    "QUADRANT LEADERBOARD",
        "cardinal_west":        "WEST",
        "cardinal_north":       "NORTH",
        "cardinal_east":        "EAST",
        "cardinal_south":       "SOUTH",
        "summary_video":        "Video           : {v}",
        "summary_res":          "Resolution      : {w}x{h}",
        "summary_frames":       "Total frames    : {n}",
        "summary_fps":          "FPS             : {fps:.2f}",
        "summary_duration":     "Duration (s)    : {d:.2f}",
        "summary_start":        "Start time (s)  : {v}",
        "summary_end":          "End time (s)    : {v}",
        "summary_detected":     "Detected frames : {n}",
        "summary_interp":       "Interpolated    : {n}",
        "summary_missing":      "Missing (no pos): {n}",
        "summary_radius":       "Pool radius     : {r} cm",
        "summary_scale_x":      "Scale X         : {s:.4f} cm/px  (horizontal)",
        "summary_scale_y":      "Scale Y         : {s:.4f} cm/px  (vertical)",
        "summary_dist_px":      "Total distance  : {d:.2f} px",
        "summary_dist_cm":      "Total distance  : {d:.2f} cm",
        "summary_pairs":        "  (over {n} consecutive frame pairs)",
        "summary_quad_hdr":     "-- Quadrant Analysis (sorted by time spent) --",
        "summary_col_q":        "Quadrant",
        "summary_col_t":        "Time (s)",
        "summary_col_tp":       "Time (%)",
        "summary_col_d":        "Dist (cm)",
        "summary_col_dp":       "Dist (%)",
        "summary_total":        "TOTAL",
        "summary_pool_hdr":     "-- Pool Calibration Points --",
        "summary_pool_w":       "Pool West       : {v}",
        "summary_pool_n":       "Pool North      : {v}",
        "summary_pool_e":       "Pool East       : {v}",
        "summary_pool_s":       "Pool South      : {v}",
        "summary_platform_hdr": "-- Platform Calibration Points --",
        "summary_platform_nw":  "Platform NW     : {v}",
        "summary_platform_ne":  "Platform NE     : {v}",
        "summary_platform_se":  "Platform SE     : {v}",
        "summary_platform_sw":  "Platform SW     : {v}",
        "summary_platform_exits":"Platform exits  : {n}",
        "summary_rerun":        "-- Re-run Command --",
    },
    "fr": {
        "calib_step":           "Etape {step}/4 -- Cliquez sur le point {cardinal} du bord du bassin",
        "calib_redo":           "Appuyez sur  R  pour recommencer   |   ESC pour abandonner",
        "calib_confirm":        "4 points definis -- ENTREE pour confirmer ou R pour recommencer",
        "calib_abort":          "ESC  pour abandonner sans sauvegarder",
        "calib_post_confirm":   "ENTREE  -->  Continuer sans plateforme     M  -->  Choisir les coins de la plateforme",
        "confirm_title":        "Coordonnees du bassin trouvees -- confirmer ou reprendre",
        "confirm_hint":         "ENTREE  -->  Continuer avec ces coordonnees     ESC  -->  Reprendre",
        "platform_step":        "Plateforme etape {step}/4 -- Cliquez le coin {corner} (sens horaire)",
        "platform_redo":        "Appuyez sur  R  pour recommencer   |   ESC pour ignorer la plateforme",
        "platform_confirm":     "4 coins definis -- ENTREE pour confirmer ou R pour recommencer",
        "platform_skip":        "ESC  -->  ignorer la plateforme",
        "platform_confirm_title":"Coordonnees de plateforme trouvees -- confirmer ou reprendre",
        "platform_confirm_hint":"ENTREE  -->  Continuer avec ces coordonnees     ESC  -->  Reprendre",
        "status_detected":      "DETECTE",
        "status_missing":       "MANQUANT",
        "hud_frame":            "Image: {frame}   t = {time:.2f}s",
        "hud_position":         "Position: {pos}",
        "hud_dist":             "Dist: {dist}",
        "hud_platform_exits":   "Sorties plateforme: {n}",
        "leaderboard_title":    "CLASSEMENT QUADRANTS",
        "cardinal_west":        "OUEST",
        "cardinal_north":       "NORD",
        "cardinal_east":        "EST",
        "cardinal_south":       "SUD",
        "summary_video":        "Video           : {v}",
        "summary_res":          "Resolution      : {w}x{h}",
        "summary_frames":       "Images totales  : {n}",
        "summary_fps":          "FPS             : {fps:.2f}",
        "summary_duration":     "Duree (s)       : {d:.2f}",
        "summary_start":        "Debut (s)       : {v}",
        "summary_end":          "Fin (s)         : {v}",
        "summary_detected":     "Images detectees: {n}",
        "summary_interp":       "Interpolees     : {n}",
        "summary_missing":      "Manquantes      : {n}",
        "summary_radius":       "Rayon bassin    : {r} cm",
        "summary_scale_x":      "Echelle X       : {s:.4f} cm/px  (horizontal)",
        "summary_scale_y":      "Echelle Y       : {s:.4f} cm/px  (vertical)",
        "summary_dist_px":      "Distance totale : {d:.2f} px",
        "summary_dist_cm":      "Distance totale : {d:.2f} cm",
        "summary_pairs":        "  (sur {n} paires d'images consecutives)",
        "summary_quad_hdr":     "-- Analyse par quadrant (triee par temps passe) --",
        "summary_col_q":        "Quadrant",
        "summary_col_t":        "Temps (s)",
        "summary_col_tp":       "Temps (%)",
        "summary_col_d":        "Dist (cm)",
        "summary_col_dp":       "Dist (%)",
        "summary_total":        "TOTAL",
        "summary_pool_hdr":     "-- Points de calibration du bassin --",
        "summary_pool_w":       "Bassin Ouest    : {v}",
        "summary_pool_n":       "Bassin Nord     : {v}",
        "summary_pool_e":       "Bassin Est      : {v}",
        "summary_pool_s":       "Bassin Sud      : {v}",
        "summary_platform_hdr": "-- Points de calibration de la plateforme --",
        "summary_platform_nw":  "Plateforme NO   : {v}",
        "summary_platform_ne":  "Plateforme NE   : {v}",
        "summary_platform_se":  "Plateforme SE   : {v}",
        "summary_platform_sw":  "Plateforme SO   : {v}",
        "summary_platform_exits":"Sorties plateau : {n}",
        "summary_rerun":        "-- Commande de relance --",
    },
    "tr": {
        "calib_step":           "Adim {step}/4 -- Havuz kenarindaki {cardinal} noktasina tiklayin",
        "calib_redo":           "R  tum noktalari sifirlar   |   ESC iptal eder",
        "calib_confirm":        "4 nokta belirlendi -- ENTER ile onayla veya R ile yeniden secim yap",
        "calib_abort":          "ESC -->  kaydetmeden cik",
        "calib_post_confirm":   "ENTER  -->  Platform olmadan devam et     M  -->  Platform koselerini sec",
        "confirm_title":        "Kayitli havuz koordinatlari bulundu -- onayla veya yeniden sec",
        "confirm_hint":         "ENTER  -->  Bu koordinatlarla devam et     ESC  -->  Yeniden sec",
        "platform_step":        "Platform Adim {step}/4 -- {corner} kosesine tiklayin (saat yonunde)",
        "platform_redo":        "R  tum noktalari sifirlar   |   ESC platformu atla",
        "platform_confirm":     "4 kose belirlendi -- ENTER ile onayla veya R ile yeniden yap",
        "platform_skip":        "ESC  -->  platformu atla",
        "platform_confirm_title":"Kayitli platform koordinatlari bulundu -- onayla veya yeniden sec",
        "platform_confirm_hint":"ENTER  -->  Bu koordinatlarla devam et     ESC  -->  Yeniden sec",
        "status_detected":      "ALGILANDI",
        "status_missing":       "KAYIP",
        "hud_frame":            "Kare: {frame}   t = {time:.2f}s",
        "hud_position":         "Konum: {pos}",
        "hud_dist":             "Dist: {dist}",
        "hud_platform_exits":   "Platform cikisi: {n}",
        "leaderboard_title":    "CEYREK SIRALAMASI",
        "cardinal_west":        "BATI",
        "cardinal_north":       "KUZEY",
        "cardinal_east":        "DOGU",
        "cardinal_south":       "GUNEY",
        "summary_video":        "Video           : {v}",
        "summary_res":          "Cozunurluk      : {w}x{h}",
        "summary_frames":       "Toplam kare     : {n}",
        "summary_fps":          "FPS             : {fps:.2f}",
        "summary_duration":     "Sure (s)        : {d:.2f}",
        "summary_start":        "Baslangic (s)   : {v}",
        "summary_end":          "Bitis (s)       : {v}",
        "summary_detected":     "Algilanan kare  : {n}",
        "summary_interp":       "Enterpolasyon   : {n}",
        "summary_missing":      "Eksik (konum yok): {n}",
        "summary_radius":       "Havuz yaricapi  : {r} cm",
        "summary_scale_x":      "Olcek X         : {s:.4f} cm/px  (yatay)",
        "summary_scale_y":      "Olcek Y         : {s:.4f} cm/px  (dikey)",
        "summary_dist_px":      "Toplam mesafe   : {d:.2f} px",
        "summary_dist_cm":      "Toplam mesafe   : {d:.2f} cm",
        "summary_pairs":        "  ({n} ardisik kare cifti uzerinden)",
        "summary_quad_hdr":     "-- Ceyrek Analizi (harcanan zamana gore siralanmis) --",
        "summary_col_q":        "Ceyrek",
        "summary_col_t":        "Sure (s)",
        "summary_col_tp":       "Sure (%)",
        "summary_col_d":        "Dist (cm)",
        "summary_col_dp":       "Dist (%)",
        "summary_total":        "TOPLAM",
        "summary_pool_hdr":     "-- Havuz Kalibrasyon Noktalari --",
        "summary_pool_w":       "Havuz Bati      : {v}",
        "summary_pool_n":       "Havuz Kuzey     : {v}",
        "summary_pool_e":       "Havuz Dogu      : {v}",
        "summary_pool_s":       "Havuz Guney     : {v}",
        "summary_platform_hdr": "-- Platform Kalibrasyon Noktalari --",
        "summary_platform_nw":  "Platform KB     : {v}",
        "summary_platform_ne":  "Platform KD     : {v}",
        "summary_platform_se":  "Platform GD     : {v}",
        "summary_platform_sw":  "Platform GB     : {v}",
        "summary_platform_exits":"Platform cikisi : {n}",
        "summary_rerun":        "-- Yeniden calistirma Komutu --",
    },
}

def S(lang, key, **kwargs):
    base = STRINGS.get(lang, STRINGS["en"])
    s = base.get(key, STRINGS["en"].get(key, key))
    return s.format(**kwargs) if kwargs else s

def tracemap(records, first_frame, output_dir, video_path, ts, color=(255, 255, 0)):
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
            cv2.line(
                canvas,
                prev_point,
                point,
                color,  # Aqua
                2,
                lineType=cv2.LINE_AA
            )

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

## Progress

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

## Calibration

def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_west", "pool_north", "pool_east", "pool_south"))

def platform_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("platform_nw", "platform_ne", "platform_se", "platform_sw"))

def run_calibration(frame: np.ndarray, lang: str) -> dict | None:
    state = {"step": 0, "points": {}, "frame": frame.copy()}
    window = "Pool Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    calib_cardinal_labels = {
        "WEST":  S(lang, "cardinal_west"),
        "NORTH": S(lang, "cardinal_north"),
        "EAST":  S(lang, "cardinal_east"),
        "SOUTH": S(lang, "cardinal_south"),
    }

    def draw(base):
        img = base.copy()
        draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
        step = state["step"]
        if step < len(CALIB_STEPS):
            cardinal, _ = CALIB_STEPS[step]
            color = CALIB_COLORS[cardinal]
            label = calib_cardinal_labels[cardinal]
            cv2.putText(img, S(lang, "calib_step", step=step+1, cardinal=label),
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1)
            cv2.putText(img, S(lang, "calib_redo"),
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        else:
            cv2.putText(img, S(lang, "calib_confirm"),
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
            cv2.putText(img, S(lang, "calib_post_confirm"),
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (180, 180, 180), 1)
        for cardinal, pt in state["points"].items():
            col = CALIB_COLORS[cardinal]
            cv2.circle(img, pt, 7, col, -1)
            cv2.circle(img, pt, 9, (255, 255, 255), 1)
            cv2.putText(img, calib_cardinal_labels[cardinal],
                        (pt[0] + 11, pt[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)
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
        cv2.imshow(window, draw(state["frame"]))

    cv2.setMouseCallback(window, on_click)
    cv2.imshow(window, draw(state["frame"]))

    result = None
    pick_platform = False
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
                    "pool_west":  p["WEST"],
                    "pool_north": p["NORTH"],
                    "pool_east":  p["EAST"],
                    "pool_south": p["SOUTH"],
                }
                break
        elif key in (ord('m'), ord('M')):
            p = state["points"]
            if len(p) == 4:
                result = {
                    "pool_west":  p["WEST"],
                    "pool_north": p["NORTH"],
                    "pool_east":  p["EAST"],
                    "pool_south": p["SOUTH"],
                }
                pick_platform = True
                break
        cv2.imshow(window, draw(state["frame"]))

    cv2.destroyWindow(window)
    if result is None:
        return None
    return result, pick_platform

def run_platform_calibration(frame: np.ndarray, lang: str) -> dict | None:
    state = {"step": 0, "points": {}, "frame": frame.copy()}
    window = "Platform Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))

    corner_labels = {s[0]: s[0] for s in PLATFORM_STEPS}

    def draw(base):
        img = base.copy()
        draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
        step = state["step"]
        if step < len(PLATFORM_STEPS):
            corner, _ = PLATFORM_STEPS[step]
            color = PLATFORM_COLORS[corner]
            cv2.putText(img, S(lang, "platform_step", step=step+1, corner=corner),
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, color, 1)
            cv2.putText(img, S(lang, "platform_redo"),
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        else:
            cv2.putText(img, S(lang, "platform_confirm"),
                        (12, 28), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
            cv2.putText(img, S(lang, "platform_skip"),
                        (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (180, 180, 180), 1)
        pts_ordered = [state["points"].get(s[0]) for s in PLATFORM_STEPS if s[0] in state["points"]]
        if len(pts_ordered) >= 2:
            for i in range(len(pts_ordered) - 1):
                cv2.line(img, pts_ordered[i], pts_ordered[i+1], (200, 200, 50), 1)
        if len(state["points"]) == 4:
            corners_ordered = [state["points"][s[0]] for s in PLATFORM_STEPS]
            pts_np = np.array(corners_ordered, dtype=np.int32)
            cv2.polylines(img, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
        for corner, pt in state["points"].items():
            col = PLATFORM_COLORS[corner]
            cv2.circle(img, pt, 7, col, -1)
            cv2.circle(img, pt, 9, (255, 255, 255), 1)
            cv2.putText(img, corner, (pt[0] + 11, pt[1] + 5),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)
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

def confirm_pool_from_args(frame, cfg, lang):
    p = {
        "WEST":  cfg["pool_west"],
        "NORTH": cfg["pool_north"],
        "EAST":  cfg["pool_east"],
        "SOUTH": cfg["pool_south"],
    }
    calib_cardinal_labels = {
        "WEST":  S(lang, "cardinal_west"),
        "NORTH": S(lang, "cardinal_north"),
        "EAST":  S(lang, "cardinal_east"),
        "SOUTH": S(lang, "cardinal_south"),
    }
    result = pool_ellipse_from_nsew(p["WEST"], p["NORTH"], p["EAST"], p["SOUTH"])
    if result is None:
        return False, False
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
        cv2.putText(img, calib_cardinal_labels[cardinal],
                    (pt[0] + 11, pt[1] + 5), cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)
    draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
    cv2.putText(img, S(lang, "confirm_title"),
                (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
    cv2.putText(img, S(lang, "confirm_hint"),
                (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)
    window = "Pool Confirmation"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1], 1280), min(frame.shape[0], 720))
    cv2.imshow(window, img)
    confirmed = False
    pick_platform = False
    while True:
        key = cv2.waitKey(20) & 0xFF
        if key in (13, 10):
            confirmed = True
            break
        elif key == 27:
            confirmed = False
            break
        elif key in (ord('m'), ord('M')):
            confirmed = True
            pick_platform = True
            break
    cv2.destroyWindow(window)
    return confirmed, pick_platform

def confirm_platform_from_args(frame, cfg, lang):
    corners = [cfg["platform_nw"], cfg["platform_ne"], cfg["platform_se"], cfg["platform_sw"]]
    img = frame.copy()
    pts_np = np.array(corners, dtype=np.int32)
    cv2.polylines(img, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
    for i, (corner_name, _) in enumerate(PLATFORM_STEPS):
        pt = corners[i]
        col = PLATFORM_COLORS[corner_name]
        cv2.circle(img, pt, 7, col, -1)
        cv2.circle(img, pt, 9, (255, 255, 255), 1)
        cv2.putText(img, corner_name, (pt[0] + 11, pt[1] + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.52, col, 1)
    draw_transparent_banner(img, 0, 0, frame.shape[1], 70)
    cv2.putText(img, S(lang, "platform_confirm_title"),
                (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.65, (100, 255, 180), 1)
    cv2.putText(img, S(lang, "platform_confirm_hint"),
                (12, 54), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (180, 180, 180), 1)
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
    nw, ne, se, sw = platform_corners
    corners = [nw, ne, se, sw]
    n = len(corners)
    inside = False
    px, py = x, y
    j = n - 1
    for i in range(n):
        xi, yi = corners[i]
        xj, yj = corners[j]
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

## Calculations

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

def draw_transparent_banner(img, x0, y0, x1, y1, alpha=0.72):
    overlay = img.copy()
    cv2.rectangle(overlay, (x0, y0), (x1, y1), (10, 10, 10), -1)
    cv2.addWeighted(overlay, alpha, img, 1 - alpha, 0, img)
    cv2.rectangle(img, (x0, y0), (x1, y1), (80, 80, 80), 1)

def draw_leaderboard(img, stats, total_time_s, total_dist_cm, lang):
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
    cv2.putText(img, S(lang, "leaderboard_title"),
                (x0 + pad, y0 + 16), cv2.FONT_HERSHEY_SIMPLEX, 0.44, (200, 200, 200), 1)
    for rank, q in enumerate(sorted_q):
        t_s   = stats[q]["time_s"]
        d_cm  = stats[q]["dist_cm"]
        t_pct = (t_s  / total_time_s  * 100) if total_time_s  > 0 else 0.0
        d_pct = (d_cm / total_dist_cm * 100) if total_dist_cm > 0 else 0.0
        color = QUADRANT_COLORS[q]
        row_y = y0 + header_h + rank * row_h + row_h - 4
        cv2.putText(img, f"#{rank+1} {q}", (x0 + pad, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.44, color, 1)
        cv2.putText(img, f"T:{t_s:5.1f}s {t_pct:4.1f}%", (x0 + pad + 52, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (220, 220, 220), 1)
        cv2.putText(img, f"D:{d_cm:6.1f}cm {d_pct:4.1f}%", (x0 + pad + 166, row_y), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (255, 200, 50), 1)

## Rat Detection

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

def parse_point(s):
    parts = s.split(",")
    return (int(parts[0]), int(parts[1]))

def fmt_pt(pt):
    return f"{pt[0]},{pt[1]}"

def build_rerun_command(video_path, args, cfg):
    parts = ["python main.py"]
    if args.language != "en":
        parts.append(f"--language {args.language}")
    if args.start is not None:
        parts.append(f"--start {args.start}")
    if args.end is not None:
        parts.append(f"--end {args.end}")
    if args.pool_radius_cm != 60:
        parts.append(f"--pool_radius_cm {args.pool_radius_cm}")
    if args.mog2_history != 120:
        parts.append(f"--mog2_history {args.mog2_history}")
    if args.mog2_threshold != 40:
        parts.append(f"--mog2_threshold {args.mog2_threshold}")
    if args.mog2_detect_shadow:
        parts.append("--mog2_detect_shadow")
    if args.morph_open_k != 3:
        parts.append(f"--morph_open_k {args.morph_open_k}")
    if args.morph_close_k != 15:
        parts.append(f"--morph_close_k {args.morph_close_k}")
    if args.min_contour_area != 300:
        parts.append(f"--min_contour_area {args.min_contour_area}")
    if args.max_contour_area != 12000:
        parts.append(f"--max_contour_area {args.max_contour_area}")
    if args.trail_len != 40:
        parts.append(f"--trail_len {args.trail_len}")
    if args.debug_frames != 0:
        parts.append(f"--debug_frames {args.debug_frames}")
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

def main():
    parser = argparse.ArgumentParser(description="Track a rat in a water maze video.")
    parser.add_argument("--video",               required=True,  type=str)
    parser.add_argument("--language",            default="en",   type=str,    choices=["en", "fr", "tr"])
    parser.add_argument("--start",               default=None,   type=float)
    parser.add_argument("--end",                 default=None,   type=float)
    parser.add_argument("--pool_radius_cm",      default=60,     type=float)
    parser.add_argument("--mog2_history",        default=120,    type=int)
    parser.add_argument("--mog2_threshold",      default=40,     type=float)
    parser.add_argument("--mog2_detect_shadow",  default=False,  action="store_true")
    parser.add_argument("--morph_open_k",        default=3,      type=int)
    parser.add_argument("--morph_close_k",       default=15,     type=int)
    parser.add_argument("--min_contour_area",    default=300,    type=float)
    parser.add_argument("--max_contour_area",    default=12000,  type=float)
    parser.add_argument("--trail_len",           default=40,     type=int)
    parser.add_argument("--debug_frames",        default=0,      type=int)
    parser.add_argument("--pool_west",           default=None,   type=str)
    parser.add_argument("--pool_north",          default=None,   type=str)
    parser.add_argument("--pool_east",           default=None,   type=str)
    parser.add_argument("--pool_south",          default=None,   type=str)
    parser.add_argument("--platform_nw",         default=None,   type=str)
    parser.add_argument("--platform_ne",         default=None,   type=str)
    parser.add_argument("--platform_se",         default=None,   type=str)
    parser.add_argument("--platform_sw",         default=None,   type=str)
    parser.add_argument("--appmode",             default=False,  action="store_true")
    args = parser.parse_args()

    lang = args.language

    cfg = {
        "pool_radius_cm":     args.pool_radius_cm,
        "mog2_history":       args.mog2_history,
        "mog2_threshold":     args.mog2_threshold,
        "mog2_detect_shadow": args.mog2_detect_shadow,
        "morph_open_k":       args.morph_open_k,
        "morph_close_k":      args.morph_close_k,
        "min_contour_area":   args.min_contour_area,
        "max_contour_area":   args.max_contour_area,
        "trail_len":          args.trail_len,
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

    start_frame = int(args.start * fps) if args.start is not None else 0
    end_frame   = int(args.end   * fps) if args.end   is not None else total_frames

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    ret, first_frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read first frame from video.")

    pick_platform = False

    if pool_coords_valid(cfg):
        confirmed, pick_platform = confirm_pool_from_args(first_frame, cfg, lang)
        if not confirmed:
            result = run_calibration(first_frame, lang)
            if result is None:
                raise RuntimeError("Pool calibration aborted.")
            pool_result, pick_platform = result
            cfg.update(pool_result)
        elif pick_platform:
            cfg["platform_nw"] = None
            cfg["platform_ne"] = None
            cfg["platform_se"] = None
            cfg["platform_sw"] = None
    else:
        result = run_calibration(first_frame, lang)
        if result is None:
            raise RuntimeError("Pool calibration aborted.")
        pool_result, pick_platform = result
        cfg.update(pool_result)

    if pick_platform:
        plat_result = run_platform_calibration(first_frame, lang)
        if plat_result is not None:
            cfg.update(plat_result)
    elif platform_coords_valid(cfg):
        confirmed = confirm_platform_from_args(first_frame, cfg, lang)
        if not confirmed:
            plat_result = run_platform_calibration(first_frame, lang)
            if plat_result is not None:
                cfg.update(plat_result)
            else:
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

    has_platform = platform_coords_valid(cfg)
    platform_corners = None
    if has_platform:
        platform_corners = [cfg["platform_nw"], cfg["platform_ne"],
                            cfg["platform_se"], cfg["platform_sw"]]

    ts           = datetime.now().strftime("%y-%m-%d_%H-%M-%S")
    output_dir   = video_path.parent
    video_out    = output_dir / f"{video_path.stem}_{ts}.mp4"
    csv_path     = output_dir / f"{video_path.stem}_{ts}_coordinates.csv"
    summary_path = output_dir / f"{video_path.stem}_{ts}_summary.txt"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )

    records              = []
    trail                = []
    frame_idx            = 0
    running_dist_px      = 0.0
    running_dist_cm      = 0.0
    prev_pos             = None
    q_stats              = empty_quadrant_stats()
    platform_exits       = 0
    prev_inside_platform = False
    loop_start           = time.time()

    processable_frames = end_frame - start_frame

    calib_labels = {
        "WEST":  S(lang, "cardinal_west"),
        "NORTH": S(lang, "cardinal_north"),
        "EAST":  S(lang, "cardinal_east"),
        "SOUTH": S(lang, "cardinal_south"),
    }

    while True:
        current_pos = int(cap.get(cv2.CAP_PROP_POS_FRAMES))
        if current_pos >= end_frame:
            break

        ret, frame = cap.read()
        if not ret:
            break

        timestamp = (start_frame + frame_idx) / fps
        pos       = detect_rat(frame, subtractor, cfg, pool_mask, pool, frame_idx, prev_pos)

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

        if has_platform and pos:
            curr_inside = point_in_platform(pos, platform_corners)
            if prev_pos is not None:
                if prev_inside_platform and not curr_inside:
                    platform_exits += 1
                elif not prev_inside_platform and not curr_inside:
                    if segment_crosses_platform_twice(prev_pos, pos, platform_corners):
                        platform_exits += 1
            prev_inside_platform = curr_inside

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
        cv2.ellipse(annotated, (cx, cy), (rx, ry), angle, 0, 360, (255, 100, 0), thickness=2)
        cv2.line(annotated, north, south, (255, 100, 0), 1)
        cv2.line(annotated, west,  east,  (255, 100, 0), 1)
        for pt in [west, north, east, south, (cx, cy)]:
            cv2.circle(annotated, pt, 5, (255, 100, 0), -1)
            cv2.circle(annotated, pt, 6, (255, 255, 255), 1)

        if has_platform:
            pts_np = np.array(platform_corners, dtype=np.int32)
            cv2.polylines(annotated, [pts_np], isClosed=True, color=(200, 200, 50), thickness=2)
            for i, (corner_name, _) in enumerate(PLATFORM_STEPS):
                pt = platform_corners[i]
                col = PLATFORM_COLORS[corner_name]
                cv2.circle(annotated, pt, 4, col, -1)

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
            cv2.putText(annotated, q, lp, cv2.FONT_HERSHEY_SIMPLEX, 0.5, QUADRANT_COLORS[q], 1)

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

        status    = S(lang, "status_detected") if pos else S(lang, "status_missing")
        hud_color = (0, 210, 0) if pos else (0, 0, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        hud_dist  = f"{running_dist_px:.1f} px  |  {running_dist_cm:.1f} cm"

        hud_h = 120 if has_platform else 100
        draw_transparent_banner(annotated, 5, 5, 340, hud_h)
        cv2.putText(annotated, S(lang, "hud_frame", frame=frame_idx, time=timestamp),
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, S(lang, "hud_position", pos=pos_str),
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, status,
                    (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, hud_color, 1)
        cv2.putText(annotated, S(lang, "hud_dist", dist=hud_dist),
                    (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 50), 1)
        if has_platform:
            cv2.putText(annotated, S(lang, "hud_platform_exits", n=platform_exits),
                        (10, 118), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (200, 200, 50), 1)

        total_q_time = sum(v["time_s"]  for v in q_stats.values())
        total_q_dist = sum(v["dist_cm"] for v in q_stats.values())
        draw_leaderboard(annotated, q_stats, total_q_time, total_q_dist, lang)

        writer.write(annotated)
        frame_idx += 1

        emit_progress(frame_idx, processable_frames, loop_start, cfg["app_mode"])

    if not cfg["app_mode"]:
        print()

    cap.release()
    writer.release()

    detected      = sum(1 for r in records if r["x"] is not None)
    records       = interpolate_missing(records)
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
                                   west, north, east, south,
                                   frame_dt, scale_x, scale_y)
                valid_pairs += 1
            else:
                accumulate_static(q_stats_final, curr, west, north, east, south, frame_dt)
            prev = curr

    total_q_time = sum(v["time_s"]  for v in q_stats_final.values())
    total_q_dist = sum(v["dist_cm"] for v in q_stats_final.values())

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)

    sorted_q     = sorted(QUADRANT_NAMES, key=lambda q: q_stats_final[q]["time_s"], reverse=True)
    col_q  = S(lang, "summary_col_q")
    col_t  = S(lang, "summary_col_t")
    col_tp = S(lang, "summary_col_tp")
    col_d  = S(lang, "summary_col_d")
    col_dp = S(lang, "summary_col_dp")

    rerun_cmd = build_rerun_command(video_path, args, cfg)

    lines = [
        S(lang, "summary_video",    v=video_path.name),
        S(lang, "summary_res",      w=frame_w, h=frame_h),
        S(lang, "summary_frames",   n=frame_idx),
        S(lang, "summary_fps",      fps=fps),
        S(lang, "summary_duration", d=frame_idx / fps),
        S(lang, "summary_start",    v=args.start if args.start is not None else 0),
        S(lang, "summary_end",      v=args.end   if args.end   is not None else round(frame_idx / fps, 2)),
        "",
        S(lang, "summary_pool_hdr"),
        S(lang, "summary_pool_w",   v=cfg["pool_west"]),
        S(lang, "summary_pool_n",   v=cfg["pool_north"]),
        S(lang, "summary_pool_e",   v=cfg["pool_east"]),
        S(lang, "summary_pool_s",   v=cfg["pool_south"]),
        "",
    ]

    if has_platform:
        lines += [
            S(lang, "summary_platform_hdr"),
            S(lang, "summary_platform_nw", v=cfg["platform_nw"]),
            S(lang, "summary_platform_ne", v=cfg["platform_ne"]),
            S(lang, "summary_platform_se", v=cfg["platform_se"]),
            S(lang, "summary_platform_sw", v=cfg["platform_sw"]),
            S(lang, "summary_platform_exits", n=platform_exits),
            "",
        ]

    lines += [
        S(lang, "summary_detected", n=detected),
        S(lang, "summary_interp",   n=sum(1 for r in records if r['interpolated'])),
        S(lang, "summary_missing",  n=missing_after),
        "",
        S(lang, "summary_radius",   r=cfg['pool_radius_cm']),
        S(lang, "summary_scale_x",  s=scale_x),
        S(lang, "summary_scale_y",  s=scale_y),
        "",
        S(lang, "summary_dist_px",  d=total_dist_px),
        S(lang, "summary_dist_cm",  d=total_dist_cm),
        S(lang, "summary_pairs",    n=valid_pairs),
        "",
        S(lang, "summary_quad_hdr"),
        f"{col_q:<10} {col_t:>10} {col_tp:>10} {col_d:>12} {col_dp:>10}",
        f"{'-'*56}",
    ]
    for q in sorted_q:
        t_s   = q_stats_final[q]["time_s"]
        d_cm  = q_stats_final[q]["dist_cm"]
        t_pct = (t_s  / total_q_time * 100) if total_q_time > 0 else 0.0
        d_pct = (d_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
        lines.append(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%")
    total_label = S(lang, "summary_total")
    lines += [
        f"{'-'*56}",
        f"{total_label:<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%",
        "",
        S(lang, "summary_rerun"),
        rerun_cmd,
    ]

    with open(summary_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    tracemap(records, first_frame, output_dir, video_path, ts)
    heatmap(records, first_frame, output_dir, video_path, ts)

    if not cfg["app_mode"]:
        print("\n" + "\n".join(lines))

    if cfg["app_mode"]:
        print(json.dumps({
            "done":           True,
            "video_out":      str(video_out),
            "csv_out":        str(csv_path),
            "summary_out":    str(summary_path),
            "total_dist_cm":  round(total_dist_cm, 2),
            "total_frames":   frame_idx,
            "detected":       detected,
            "platform_exits": platform_exits,
        }), flush=True)

if __name__ == "__main__":
    main()