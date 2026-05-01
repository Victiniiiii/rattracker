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

STRINGS = {
    "en": {
        "calib_step":               "Step {step}/4 -- Click on the {cardinal} point of the pool edge",
        "calib_redo":               "Press  R  to redo all points   |   ESC to abort",
        "calib_confirm":            "All 4 points set -- press ENTER to confirm or R to redo",
        "calib_abort":              "Press  ESC  to abort without saving",
        "calib_post_confirm":       "ENTER  -->  Confirm all 8 points",
        "calib_pool_done":          "Pool done! Now click the {corner} platform corner (clockwise)",
        "calib_all_done":           "All 8 points set -- press ENTER to confirm or R to redo all",
        "confirm_title":            "Saved pool coordinates found -- confirm or repick",
        "confirm_hint":             "ENTER  -->  Continue with these coordinates     ESC  -->  Repick",
        "platform_step":            "Platform Step {step}/4 -- Click the {corner} corner (clockwise)",
        "platform_redo":            "Press  R  to redo all points   |   ESC to skip platform",
        "platform_confirm":         "All 4 corners set -- press ENTER to confirm or R to redo",
        "platform_skip":            "ESC  -->  skip platform",
        "platform_confirm_title":   "Saved platform coordinates found -- confirm or repick",
        "platform_confirm_hint":    "ENTER  -->  Continue with these coordinates     ESC  -->  Repick",
        "status_detected":          "DETECTED",
        "status_missing":           "MISSING",
        "status_interpolated":      "INTERPOLATED",
        "hud_frame":                "Frame: {frame}   t = {time:.2f}s",
        "hud_position":             "Position: {pos}",
        "hud_dist":                 "Dist: {dist}",
        "hud_platform_exits":       "Platform exits: {n}",
        "hud_paraplatform":         "ParaPlatform  T:{t:.1f}s D:{d:.1f}cm X:{x}",
        "hud_latency_done":         "Latency: {t:.2f}s / {d:.2f}cm",
        "hud_latency_pending":      "Latency: tracking...",
        "hud_para_latency_done":    "Para Latency: {t:.2f}s / {d:.2f}cm",
        "hud_para_latency_pending": "Para Latency: tracking...",
        "hud_proximity":            "Proximity: {d:.1f}cm",
        "leaderboard_title":        "QUADRANT LEADERBOARD",
        "cardinal_west":            "WEST",
        "cardinal_north":           "NORTH",
        "cardinal_east":            "EAST",
        "cardinal_south":           "SOUTH",
        "summary_video":            "Video           : {v}",
        "summary_res":              "Resolution      : {w}x{h}",
        "summary_frames":           "Total frames    : {n}",
        "summary_fps":              "FPS             : {fps:.2f}",
        "summary_duration":         "Duration (s)    : {d:.2f}",
        "summary_start":            "Start time (s)  : {v}",
        "summary_end":              "End time (s)    : {v}",
        "summary_detected":         "Detected frames : {n}",
        "summary_interp":           "Interpolated    : {n}",
        "summary_missing":          "Missing (no pos): {n}",
        "summary_radius":           "Pool radius     : {r} cm",
        "summary_scale_x":          "Scale X         : {s:.4f} cm/px  (horizontal)",
        "summary_scale_y":          "Scale Y         : {s:.4f} cm/px  (vertical)",
        "summary_dist_px":          "Total distance  : {d:.2f} px",
        "summary_dist_cm":          "Total distance  : {d:.2f} cm",
        "summary_pairs":            "  (over {n} consecutive frame pairs)",
        "summary_quad_hdr":         "-- Quadrant Analysis (sorted by time spent) --",
        "summary_col_q":            "Quadrant",
        "summary_col_t":            "Time (s)",
        "summary_col_tp":           "Time (%)",
        "summary_col_d":            "Dist (cm)",
        "summary_col_dp":           "Dist (%)",
        "summary_col_exits":        "Exits",
        "summary_total":            "TOTAL",
        "summary_pool_hdr":         "-- Pool Calibration Points --",
        "summary_pool_w":           "Pool West       : {v}",
        "summary_pool_n":           "Pool North      : {v}",
        "summary_pool_e":           "Pool East       : {v}",
        "summary_pool_s":           "Pool South      : {v}",
        "summary_platform_hdr":     "-- Platform Calibration Points --",
        "summary_platform_nw":      "Platform NW     : {v}",
        "summary_platform_ne":      "Platform NE     : {v}",
        "summary_platform_se":      "Platform SE     : {v}",
        "summary_platform_sw":      "Platform SW     : {v}",
        "summary_platform_exits":   "Platform exits  : {n}",
        "summary_quad_exits_hdr":   "-- Quadrant Exits --",
        "summary_quad_exit":        "{q} exits       : {n}",
        "summary_paraplatform_hdr": "-- ParaPlatform Analysis (scale: {s}x area / {sl:.2f}x side) --",
        "summary_paraplatform_t":   "ParaPlatform time  : {t:.2f} s  ({p:.1f}% of total)",
        "summary_paraplatform_d":   "ParaPlatform dist  : {d:.2f} cm ({p:.1f}% of total)",
        "summary_paraplatform_x":   "ParaPlatform exits : {n}",
        "summary_proximity_hdr":    "-- Proximity to Platform --",
        "summary_proximity_avg":    "Avg dist to center : {d:.2f} cm  (over {n} frames)",
        "summary_latency_hdr":      "-- Latency to Platform --",
        "summary_latency_t":        "Time to first entry: {t:.2f} s",
        "summary_latency_d":        "Dist to first entry: {d:.2f} cm",
        "summary_latency_none":     "Rat never entered platform during session",
        "summary_para_latency_hdr": "-- Latency to ParaPlatform --",
        "summary_para_latency_t":   "Time to first para entry: {t:.2f} s",
        "summary_para_latency_d":   "Dist to first para entry: {d:.2f} cm",
        "summary_para_latency_none":"Rat never entered paraplatform during session",
        "summary_rerun":            "-- Re-run Command --",
    },
    "fr": {
        "calib_step":               "Etape {step}/4 -- Cliquez sur le point {cardinal} du bord du bassin",
        "calib_redo":               "Appuyez sur  R  pour recommencer   |   ESC pour abandonner",
        "calib_confirm":            "4 points definis -- ENTREE pour confirmer ou R pour recommencer",
        "calib_abort":              "ESC  pour abandonner sans sauvegarder",
        "calib_post_confirm":       "ENTREE  -->  Confirmer les 8 points",
        "calib_pool_done":          "Bassin OK! Cliquez le coin {corner} de la plateforme (sens horaire)",
        "calib_all_done":           "8 points definis -- ENTREE pour confirmer ou R pour tout recommencer",
        "confirm_title":            "Coordonnees du bassin trouvees -- confirmer ou reprendre",
        "confirm_hint":             "ENTREE  -->  Continuer avec ces coordonnees     ESC  -->  Reprendre",
        "platform_step":            "Plateforme etape {step}/4 -- Cliquez le coin {corner} (sens horaire)",
        "platform_redo":            "Appuyez sur  R  pour recommencer   |   ESC pour ignorer la plateforme",
        "platform_confirm":         "4 coins definis -- ENTREE pour confirmer ou R pour recommencer",
        "platform_skip":            "ESC  -->  ignorer la plateforme",
        "platform_confirm_title":   "Coordonnees de plateforme trouvees -- confirmer ou reprendre",
        "platform_confirm_hint":    "ENTREE  -->  Continuer avec ces coordonnees     ESC  -->  Reprendre",
        "status_detected":          "DETECTE",
        "status_missing":           "MANQUANT",
        "status_interpolated":      "INTERPOLE",
        "hud_frame":                "Image: {frame}   t = {time:.2f}s",
        "hud_position":             "Position: {pos}",
        "hud_dist":                 "Dist: {dist}",
        "hud_platform_exits":       "Sorties plateforme: {n}",
        "hud_paraplatform":         "ParaPlateforme T:{t:.1f}s D:{d:.1f}cm X:{x}",
        "hud_latency_done":         "Latence: {t:.2f}s / {d:.2f}cm",
        "hud_latency_pending":      "Latence: en cours...",
        "hud_para_latency_done":    "Para Latence: {t:.2f}s / {d:.2f}cm",
        "hud_para_latency_pending": "Para Latence: en cours...",
        "hud_proximity":            "Proximite: {d:.1f}cm",
        "leaderboard_title":        "CLASSEMENT QUADRANTS",
        "cardinal_west":            "OUEST",
        "cardinal_north":           "NORD",
        "cardinal_east":            "EST",
        "cardinal_south":           "SUD",
        "summary_video":            "Video           : {v}",
        "summary_res":              "Resolution      : {w}x{h}",
        "summary_frames":           "Images totales  : {n}",
        "summary_fps":              "FPS             : {fps:.2f}",
        "summary_duration":         "Duree (s)       : {d:.2f}",
        "summary_start":            "Debut (s)       : {v}",
        "summary_end":              "Fin (s)         : {v}",
        "summary_detected":         "Images detectees: {n}",
        "summary_interp":           "Interpolees     : {n}",
        "summary_missing":          "Manquantes      : {n}",
        "summary_radius":           "Rayon bassin    : {r} cm",
        "summary_scale_x":          "Echelle X       : {s:.4f} cm/px  (horizontal)",
        "summary_scale_y":          "Echelle Y       : {s:.4f} cm/px  (vertical)",
        "summary_dist_px":          "Distance totale : {d:.2f} px",
        "summary_dist_cm":          "Distance totale : {d:.2f} cm",
        "summary_pairs":            "  (sur {n} paires d'images consecutives)",
        "summary_quad_hdr":         "-- Analyse par quadrant (triee par temps passe) --",
        "summary_col_q":            "Quadrant",
        "summary_col_t":            "Temps (s)",
        "summary_col_tp":           "Temps (%)",
        "summary_col_d":            "Dist (cm)",
        "summary_col_dp":           "Dist (%)",
        "summary_col_exits":        "Sorties",
        "summary_total":            "TOTAL",
        "summary_pool_hdr":         "-- Points de calibration du bassin --",
        "summary_pool_w":           "Bassin Ouest    : {v}",
        "summary_pool_n":           "Bassin Nord     : {v}",
        "summary_pool_e":           "Bassin Est      : {v}",
        "summary_pool_s":           "Bassin Sud      : {v}",
        "summary_platform_hdr":     "-- Points de calibration de la plateforme --",
        "summary_platform_nw":      "Plateforme NO   : {v}",
        "summary_platform_ne":      "Plateforme NE   : {v}",
        "summary_platform_se":      "Plateforme SE   : {v}",
        "summary_platform_sw":      "Plateforme SO   : {v}",
        "summary_platform_exits":   "Sorties plateau : {n}",
        "summary_quad_exits_hdr":   "-- Sorties par quadrant --",
        "summary_quad_exit":        "Sorties {q}     : {n}",
        "summary_paraplatform_hdr": "-- Analyse ParaPlateforme (echelle: {s}x aire / {sl:.2f}x cote) --",
        "summary_paraplatform_t":   "Temps ParaPlat  : {t:.2f} s  ({p:.1f}% du total)",
        "summary_paraplatform_d":   "Dist ParaPlat   : {d:.2f} cm ({p:.1f}% du total)",
        "summary_paraplatform_x":   "Sorties ParaPlat: {n}",
        "summary_proximity_hdr":    "-- Proximite de la plateforme --",
        "summary_proximity_avg":    "Dist moy centre : {d:.2f} cm  (sur {n} images)",
        "summary_latency_hdr":      "-- Latence vers la plateforme --",
        "summary_latency_t":        "Temps 1ere entree: {t:.2f} s",
        "summary_latency_d":        "Dist 1ere entree : {d:.2f} cm",
        "summary_latency_none":     "Le rat n'est jamais entre sur la plateforme",
        "summary_para_latency_hdr": "-- Latence vers la ParaPlateforme --",
        "summary_para_latency_t":   "Temps 1ere entree para: {t:.2f} s",
        "summary_para_latency_d":   "Dist 1ere entree para : {d:.2f} cm",
        "summary_para_latency_none":"Le rat n'est jamais entre en paraplateforme",
        "summary_rerun":            "-- Commande de relance --",
    },
    "tr": {
        "calib_step":               "Adim {step}/4 -- Havuz kenarindaki {cardinal} noktasina tiklayin",
        "calib_redo":               "R  tum noktalari sifirlar   |   ESC iptal eder",
        "calib_confirm":            "4 nokta belirlendi -- ENTER ile onayla veya R ile yeniden secim yap",
        "calib_abort":              "ESC -->  kaydetmeden cik",
        "calib_post_confirm":       "ENTER  -->  8 noktanin hepsini onayla",
        "calib_pool_done":          "Havuz tamam! {corner} platform kosesine tiklayin (saat yonunde)",
        "calib_all_done":           "8 nokta belirlendi -- ENTER ile onayla veya R ile bastan yap",
        "confirm_title":            "Kayitli havuz koordinatlari bulundu -- onayla veya yeniden sec",
        "confirm_hint":             "ENTER  -->  Bu koordinatlarla devam et     ESC  -->  Yeniden sec",
        "platform_step":            "Platform Adim {step}/4 -- {corner} kosesine tiklayin (saat yonunde)",
        "platform_redo":            "R  tum noktalari sifirlar   |   ESC platformu atla",
        "platform_confirm":         "4 kose belirlendi -- ENTER ile onayla veya R ile yeniden yap",
        "platform_skip":            "ESC  -->  platformu atla",
        "platform_confirm_title":   "Kayitli platform koordinatlari bulundu -- onayla veya yeniden sec",
        "platform_confirm_hint":    "ENTER  -->  Bu koordinatlarla devam et     ESC  -->  Yeniden sec",
        "status_detected":          "ALGILANDI",
        "status_missing":           "KAYIP",
        "status_interpolated":      "ENTERPOLASYON",
        "hud_frame":                "Kare: {frame}   t = {time:.2f}s",
        "hud_position":             "Konum: {pos}",
        "hud_dist":                 "Dist: {dist}",
        "hud_platform_exits":       "Platform cikisi: {n}",
        "hud_paraplatform":         "ParaPlatform  T:{t:.1f}s D:{d:.1f}cm X:{x}",
        "hud_latency_done":         "Gecikme: {t:.2f}s / {d:.2f}cm",
        "hud_latency_pending":      "Gecikme: olculuyor...",
        "hud_para_latency_done":    "Para Gecikme: {t:.2f}s / {d:.2f}cm",
        "hud_para_latency_pending": "Para Gecikme: olculuyor...",
        "hud_proximity":            "Yakinlik: {d:.1f}cm",
        "leaderboard_title":        "CEYREK SIRALAMASI",
        "cardinal_west":            "BATI",
        "cardinal_north":           "KUZEY",
        "cardinal_east":            "DOGU",
        "cardinal_south":           "GUNEY",
        "summary_video":            "Video           : {v}",
        "summary_res":              "Cozunurluk      : {w}x{h}",
        "summary_frames":           "Toplam kare     : {n}",
        "summary_fps":              "FPS             : {fps:.2f}",
        "summary_duration":         "Sure (s)        : {d:.2f}",
        "summary_start":            "Baslangic (s)   : {v}",
        "summary_end":              "Bitis (s)       : {v}",
        "summary_detected":         "Algilanan kare  : {n}",
        "summary_interp":           "Enterpolasyon   : {n}",
        "summary_missing":          "Eksik (konum yok): {n}",
        "summary_radius":           "Havuz yaricapi  : {r} cm",
        "summary_scale_x":          "Olcek X         : {s:.4f} cm/px  (yatay)",
        "summary_scale_y":          "Olcek Y         : {s:.4f} cm/px  (dikey)",
        "summary_dist_px":          "Toplam mesafe   : {d:.2f} px",
        "summary_dist_cm":          "Toplam mesafe   : {d:.2f} cm",
        "summary_pairs":            "  ({n} ardisik kare cifti uzerinden)",
        "summary_quad_hdr":         "-- Ceyrek Analizi (harcanan zamana gore siralanmis) --",
        "summary_col_q":            "Ceyrek",
        "summary_col_t":            "Sure (s)",
        "summary_col_tp":           "Sure (%)",
        "summary_col_d":            "Dist (cm)",
        "summary_col_dp":           "Dist (%)",
        "summary_col_exits":        "Cikis",
        "summary_total":            "TOPLAM",
        "summary_pool_hdr":         "-- Havuz Kalibrasyon Noktalari --",
        "summary_pool_w":           "Havuz Bati      : {v}",
        "summary_pool_n":           "Havuz Kuzey     : {v}",
        "summary_pool_e":           "Havuz Dogu      : {v}",
        "summary_pool_s":           "Havuz Guney     : {v}",
        "summary_platform_hdr":     "-- Platform Kalibrasyon Noktalari --",
        "summary_platform_nw":      "Platform KB     : {v}",
        "summary_platform_ne":      "Platform KD     : {v}",
        "summary_platform_se":      "Platform GD     : {v}",
        "summary_platform_sw":      "Platform GB     : {v}",
        "summary_platform_exits":   "Platform cikisi : {n}",
        "summary_quad_exits_hdr":   "-- Ceyrek Cikislari --",
        "summary_quad_exit":        "{q} cikisi      : {n}",
        "summary_paraplatform_hdr": "-- ParaPlatform Analizi (olcek: {s}x alan / {sl:.2f}x kenar) --",
        "summary_paraplatform_t":   "ParaPlatform sure  : {t:.2f} s  (toplamın %{p:.1f})",
        "summary_paraplatform_d":   "ParaPlatform mesafe: {d:.2f} cm (toplamın %{p:.1f})",
        "summary_paraplatform_x":   "ParaPlatform cikis : {n}",
        "summary_proximity_hdr":    "-- Platform Yakinligi --",
        "summary_proximity_avg":    "Ort. merkez mesafesi: {d:.2f} cm  ({n} kare)",
        "summary_latency_hdr":      "-- Platform Gecikmesi --",
        "summary_latency_t":        "Ilk girise kadar sure: {t:.2f} s",
        "summary_latency_d":        "Ilk girise kadar mesafe: {d:.2f} cm",
        "summary_latency_none":     "Sickan hic platforma girmedi",
        "summary_para_latency_hdr": "-- ParaPlatform Gecikmesi --",
        "summary_para_latency_t":   "Para ilk girise kadar sure: {t:.2f} s",
        "summary_para_latency_d":   "Para ilk girise kadar mesafe: {d:.2f} cm",
        "summary_para_latency_none":"Sickan hic paraplatforma girmedi",
        "summary_rerun":            "-- Yeniden calistirma Komutu --",
    },
}

def S(lang, key, **kwargs):
    base = STRINGS.get(lang, STRINGS["en"])
    s = base.get(key, STRINGS["en"].get(key, key))
    return s.format(**kwargs) if kwargs else s

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

def run_calibration(frame: np.ndarray, lang: str, require_platform: bool = False) -> dict | None:
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
        "WEST":  S(lang, "cardinal_west"),
        "NORTH": S(lang, "cardinal_north"),
        "EAST":  S(lang, "cardinal_east"),
        "SOUTH": S(lang, "cardinal_south"),
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
                cv2.putText(img, S(lang, "calib_step", step=step+1, cardinal=label),
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
                cv2.putText(img, S(lang, "calib_redo"),
                            (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
            else:
                if not require_platform:
                    cv2.putText(img, S(lang, "calib_confirm"),
                                (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
                    cv2.putText(img, S(lang, "calib_post_confirm"),
                                (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        elif state["phase"] == "platform":
            step = state["step"]
            if step < len(PLATFORM_STEPS):
                corner, _ = PLATFORM_STEPS[step]
                color = PLATFORM_COLORS[corner]
                cv2.putText(img, S(lang, "calib_pool_done", corner=corner),
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
                cv2.putText(img, S(lang, "calib_redo"),
                            (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
            else:
                cv2.putText(img, S(lang, "calib_all_done"),
                            (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
                cv2.putText(img, S(lang, "calib_post_confirm"),
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

def run_platform_calibration(frame: np.ndarray, lang: str) -> dict | None:
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
            cv2.putText(img, S(lang, "platform_step", step=step+1, corner=corner),
                        (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, color, 1, cv2.LINE_AA)
            cv2.putText(img, S(lang, "platform_redo"),
                        (tx, ty2), cv2.FONT_HERSHEY_DUPLEX, fs2, (180, 180, 180), 1, cv2.LINE_AA)
        else:
            cv2.putText(img, S(lang, "platform_confirm"),
                        (tx, ty1), cv2.FONT_HERSHEY_DUPLEX, fs1, (100, 255, 180), 1, cv2.LINE_AA)
            cv2.putText(img, S(lang, "platform_skip"),
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
    cv2.putText(img, S(lang, "confirm_title"),
                (sc(img, 14), sc(img, 28)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.65), (100, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(img, S(lang, "confirm_hint"),
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

def confirm_platform_from_args(frame, cfg, lang):
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
    cv2.putText(img, S(lang, "platform_confirm_title"),
                (sc(img, 14), sc(img, 28)), cv2.FONT_HERSHEY_DUPLEX, sc_f(img, 0.65), (100, 255, 180), 1, cv2.LINE_AA)
    cv2.putText(img, S(lang, "platform_confirm_hint"),
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

def draw_leaderboard(img, stats, total_time_s, total_dist_cm, lang, quad_exits=None):
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
    cv2.putText(img, S(lang, "leaderboard_title"),
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

<<<<<<< HEAD
def detect_rat(frame, subtractor, cfg, pool_mask=None, pool=None, frame_idx=0, prev_pos=None, max_jump_px=None):
=======
def _extract_candidates(frame, subtractor, cfg, pool_mask, pool, frame_idx):
    """Run MOG2 + morphology + contour filtering. Returns list of (bx, by, area, cnt)
    for all contours that pass area and pool filters, without any position-based selection."""
>>>>>>> 3f148e3 (added --autoconfig, and improved previous Retroactive jump correction)
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
        # Prefer nearest candidate to last known position, but never hard-reject —
        # if the rat jumped far (fast swim, brief occlusion) we still pick the best
        # available rather than returning None and getting permanently stuck.
        candidates.sort(key=lambda c: euclidean_px(prev_pos, (c[0], c[1])))
        if max_jump_px is not None and euclidean_px(prev_pos, (candidates[0][0], candidates[0][1])) > max_jump_px:
            return None, None
    else:
        candidates.sort(key=lambda c: c[2], reverse=True)
    bx, by, _, winning_cnt = candidates[0]
    return (bx, by), winning_cnt, candidates

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
    if args.language != "en":
        parts.append(f"--language {args.language}")
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
        probe_frame, probe_pos, probe_cnt = probe_result

        # Sample rat brightness from the original BGR frame inside the contour
        mask_rat = np.zeros(probe_frame.shape[:2], dtype=np.uint8)
        cv2.drawContours(mask_rat, [probe_cnt], -1, 255, -1)
        gray_frame = cv2.cvtColor(probe_frame, cv2.COLOR_BGR2GRAY)
        rat_mean   = cv2.mean(gray_frame, mask=mask_rat)
        rat_brightness = rat_mean[0]

        # Sample background brightness from getBackgroundImage inside pool mask
        # We need a subtractor that has been warmed up; reuse the probe one but
        # re-warm from the probe frame position so getBackgroundImage() is valid.
        sub_bg = _make_probe_subtractor(session_mid)
        bg_img = sub_bg.getBackgroundImage()
        if bg_img is not None:
            if len(bg_img.shape) == 3:
                bg_img = cv2.cvtColor(bg_img, cv2.COLOR_BGR2GRAY)
            bg_mean    = cv2.mean(bg_img, mask=pool_mask)
            bg_brightness = bg_mean[0]
        else:
            # Fallback: sample the first frame inside the pool mask
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            ret, ff = cap.read()
            if ret:
                ff_gray = cv2.cvtColor(ff, cv2.COLOR_BGR2GRAY) if len(ff.shape) == 3 else ff
                bg_brightness = cv2.mean(ff_gray, mask=pool_mask)[0]
            else:
                bg_brightness = 128.0

        contrast = abs(rat_brightness - bg_brightness)
        print(f"[autoconfig] rat_brightness={rat_brightness:.1f}  "
              f"bg_brightness={bg_brightness:.1f}  contrast={contrast:.1f}", flush=True)

    # Map contrast → mog2_threshold
    # High contrast → detector can afford to be less sensitive (higher threshold)
    # Low contrast  → needs high sensitivity (lower threshold)
    if contrast is not None:
        if contrast >= 80:
            suggested_threshold = 44
        elif contrast >= 55:
            suggested_threshold = 36
        elif contrast >= 35:
            suggested_threshold = 28
        elif contrast >= 20:
            suggested_threshold = 20
        else:
            suggested_threshold = 14
    else:
        suggested_threshold = 32  # unchanged default

    print(f"[autoconfig] suggested mog2_threshold={suggested_threshold}", flush=True)

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

    # Collect stats: noise contour count, fragmentation ratio
    noise_counts      = []   # number of sub-threshold contours per frame (→ open_k)
    fragmentation     = []   # fraction of frames where top-2 candidates are suspiciously close (→ close_k)
    displacements     = []   # consecutive detected-position distances (→ history_s)
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

        # Fragmentation: top-2 candidates closer than 1 rat-body-width apart
        if len(valid_candidates) >= 2:
            valid_candidates.sort(key=lambda c: c[2], reverse=True)
            top1 = valid_candidates[0]
            top2 = valid_candidates[1]
            dist_12 = euclidean_px((top1[0], top1[1]), (top2[0], top2[1]))
            # Rat body ≈ sqrt(min_contour_area) as a rough diameter estimate
            rat_diam_est = math.sqrt(sweep_cfg["min_contour_area"])
            fragmentation.append(dist_12 < rat_diam_est * 2.5)
        else:
            fragmentation.append(False)

        # Displacement for history tuning
        if valid_candidates:
            best = max(valid_candidates, key=lambda c: c[2])
            best_pos = (best[0], best[1])
            if prev_sweep_pos is not None:
                displacements.append(euclidean_px(prev_sweep_pos, best_pos))
            prev_sweep_pos = best_pos
        else:
            prev_sweep_pos = None  # reset on miss so we don't measure huge jumps across gaps

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
    # Derive morph_close_k from fragmentation rate
    # -------------------------------------------------------------------------
    frag_rate = sum(fragmentation) / len(fragmentation) if fragmentation else 0
    base_close_k = cfg["morph_close_k"]  # already resolution-scaled default
    if frag_rate > 0.4:
        close_k = base_close_k + 8
    elif frag_rate > 0.2:
        close_k = base_close_k + 4
    else:
        close_k = base_close_k
    close_k = max(3, close_k | 1)

    print(f"[autoconfig] avg_noise={avg_noise:.1f}  frag_rate={frag_rate:.2f}", flush=True)
    print(f"[autoconfig] suggested morph_open_k={open_k}  morph_close_k={close_k}", flush=True)

    # -------------------------------------------------------------------------
    # Derive mog2_history_s from speed variance
    # A rat that frequently stops risks being absorbed into the background model
    # when history is too long — shorten it.  A rat that moves steadily can
    # tolerate a longer history for a cleaner background estimate.
    # -------------------------------------------------------------------------
    if displacements:
        near_zero   = sum(1 for d in displacements if d < 5.0)
        zero_ratio  = near_zero / len(displacements)
        disp_std    = float(np.std(displacements))

        if zero_ratio > 0.3 or disp_std > mean_pool_r_px * 0.15:
            # Rat stops often or moves very erratically → short history
            suggested_history_s = 2.0
        elif zero_ratio > 0.15:
            suggested_history_s = 3.0
        else:
            suggested_history_s = 4.0  # default is fine
        print(f"[autoconfig] zero_ratio={zero_ratio:.2f}  disp_std={disp_std:.1f}  "
              f"suggested mog2_history_s={suggested_history_s}", flush=True)
    else:
        suggested_history_s = 4.0
        print("[autoconfig] Not enough displacement data, keeping mog2_history_s=4.0", flush=True)

    return {
        "mog2_threshold":  suggested_threshold,
        "morph_open_k":    open_k,
        "morph_close_k":   close_k,
        "mog2_history_s":  suggested_history_s,
    }


def main():
    parser = argparse.ArgumentParser(description="Track a rat in a water maze video.")
    parser.add_argument("--video",               required=True,  type=str)
    parser.add_argument("--language",            default="en",   type=str,    choices=["en", "fr", "tr"])
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
    parser.add_argument("--autoconfig",          default=False,  action="store_true",
                        help="Auto-detect optimal mog2_threshold, morph kernels, and mog2_history_s from the video")
    args = parser.parse_args()

    tracemap_color   = parse_tracemap_color(args.tracemapcolor)
    rat_color        = parse_tracemap_color(args.ratcolor) if args.ratcolor else None
    lang             = args.language
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
            confirmed = confirm_pool_from_args(first_frame, cfg, lang)
            if not confirmed:
                result = run_calibration(first_frame, lang, require_platform=require_platform)
                if result is None:
                    raise RuntimeError("Pool calibration aborted.")
                cfg.update(result)
            else:
                if require_platform:
                    if platform_coords_valid(cfg):
                        plat_confirmed = confirm_platform_from_args(first_frame, cfg, lang)
                        if not plat_confirmed:
                            plat_result = run_platform_calibration(first_frame, lang)
                            if plat_result is None:
                                raise RuntimeError("Platform calibration aborted.")
                            cfg.update(plat_result)
                    else:
                        plat_result = run_platform_calibration(first_frame, lang)
                        if plat_result is None:
                            raise RuntimeError("Platform calibration aborted.")
                        cfg.update(plat_result)
                else:
                    cfg["platform_nw"] = None
                    cfg["platform_ne"] = None
                    cfg["platform_se"] = None
                    cfg["platform_sw"] = None
        else:
            result = run_calibration(first_frame, lang, require_platform=require_platform)
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
        # Store resolved history_s in cfg so build_rerun_command can emit it
        cfg["mog2_history_s"] = ac["mog2_history_s"]
        # Reset cap to start_frame after autoconfig probing
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
<<<<<<< HEAD
        pos, rat_contour = detect_rat(frame, subtractor, cfg, pool_mask, pool, frame_idx, prev_pos, max_jump_px=rx * 0.25)
=======
        pos, rat_contour, raw_candidates = detect_rat(frame, subtractor, cfg, pool_mask, pool, frame_idx, prev_pos)

        if pos is None:
            missed_candidates[frame_idx] = raw_candidates
>>>>>>> 3f148e3 (added --autoconfig, and improved previous Retroactive jump correction)

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
        if rat_contour is not None and rat_color is not None:
            cv2.drawContours(annotated, [rat_contour], -1, rat_color, -1)
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

        status    = S(lang, "status_detected") if pos else S(lang, "status_interpolated")
        hud_color = (0, 210, 0) if pos else (0, 210, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        hud_dist  = f"{running_dist_px:.1f} px  |  {running_dist_cm:.1f} cm"

        hud_lines = [
            (S(lang, "hud_frame",    frame=frame_idx, time=timestamp), (220, 220, 220)),
            (S(lang, "hud_position", pos=pos_str),                     (220, 220, 220)),
            (status,                                                     hud_color),
            (S(lang, "hud_dist",     dist=hud_dist),                   (255, 200, 50)),
        ]
        if args.platformcross and has_platform:
            hud_lines.append((S(lang, "hud_platform_exits", n=platform_exits), (200, 200, 50)))
        if para_corners is not None:
            hud_lines.append((S(lang, "hud_paraplatform", t=para_time_s, d=para_dist_cm, x=para_exits), (0, 180, 255)))
        if args.proximity and has_platform:
            live_prox = (live_proximity_sum / live_proximity_count) if live_proximity_count > 0 else 0.0
            hud_lines.append((S(lang, "hud_proximity", d=live_prox), (180, 130, 255)))
        if args.latency and has_platform:
            if latency_done:
                hud_lines.append((S(lang, "hud_latency_done", t=latency_time_s, d=latency_dist_cm), (180, 255, 100)))
            else:
                hud_lines.append((S(lang, "hud_latency_pending"), (180, 180, 180)))
        if args.latency and para_corners is not None:
            if para_latency_done:
                hud_lines.append((S(lang, "hud_para_latency_done", t=para_latency_time_s, d=para_latency_dist_cm), (100, 255, 180)))
            else:
                hud_lines.append((S(lang, "hud_para_latency_pending"), (140, 140, 140)))

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
        draw_leaderboard(annotated, q_stats, total_q_time, total_q_dist, lang, quad_exits=q_exits)

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
    col_q  = S(lang, "summary_col_q")
    col_t  = S(lang, "summary_col_t")
    col_tp = S(lang, "summary_col_tp")
    col_d  = S(lang, "summary_col_d")
    col_dp = S(lang, "summary_col_dp")
    col_ex = S(lang, "summary_col_exits")

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
        ]
        if args.platformcross:
            lines.append(S(lang, "summary_platform_exits", n=platform_exits))
        lines.append("")

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

    total_label = S(lang, "summary_total")
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
        lines += ["", S(lang, "summary_quad_exits_hdr")]
        for q in QUADRANT_NAMES:
            lines.append(S(lang, "summary_quad_exit", q=q, n=q_exits[q]))

    if para_corners is not None:
        t_pct = (para_time_s / total_q_time * 100) if total_q_time > 0 else 0.0
        d_pct = (para_dist_cm / total_q_dist * 100) if total_q_dist > 0 else 0.0
        lines += [
            "",
            S(lang, "summary_paraplatform_hdr", s=para_scale, sl=para_side_scale),
            S(lang, "summary_paraplatform_t",   t=para_time_s,  p=t_pct),
            S(lang, "summary_paraplatform_d",   d=para_dist_cm, p=d_pct),
            S(lang, "summary_paraplatform_x",   n=para_exits),
        ]

    if args.proximity and proximity_avg_cm is not None:
        lines += [
            "",
            S(lang, "summary_proximity_hdr"),
            S(lang, "summary_proximity_avg", d=proximity_avg_cm, n=proximity_n_frames),
        ]

    if args.latency and has_platform:
        lines += ["", S(lang, "summary_latency_hdr")]
        if latency_done:
            lines += [
                S(lang, "summary_latency_t", t=latency_time_s),
                S(lang, "summary_latency_d", d=latency_dist_cm),
            ]
        else:
            lines.append(S(lang, "summary_latency_none"))

    if args.latency and para_corners is not None:
        lines += ["", S(lang, "summary_para_latency_hdr")]
        if para_latency_done:
            lines += [
                S(lang, "summary_para_latency_t", t=para_latency_time_s),
                S(lang, "summary_para_latency_d", d=para_latency_dist_cm),
            ]
        else:
            lines.append(S(lang, "summary_para_latency_none"))

    lines += ["", S(lang, "summary_rerun"), rerun_cmd]

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
        }
        if args.quadrantcross:
            out["quadrant_exits"] = q_exits
        print(json.dumps(out), flush=True)

if __name__ == "__main__":
    main()