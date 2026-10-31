import cv2

from .constants import QUADRANT_NAMES, QUADRANT_COLORS


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
