import cv2
import json
import time
import numpy as np

from calibration import platform_coords_valid
from cli        import fmt_pt


def tracemap(records, first_frame, output_dir, video_path, ts, color=(0, 255, 255)):
    canvas     = first_frame.copy()
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
    return output_path


def heatmap(records, first_frame, output_dir, video_path, ts, sigma=20):
    h, w       = first_frame.shape[:2]
    heat       = np.zeros((h, w), dtype=np.float32)
    prev_time  = None
    fps_est    = None
    for r in records:
        t = r.get("timestamp_s")
        if t is not None and prev_time is not None and fps_est is None:
            dt_sample = t - prev_time
            if 0 < dt_sample < 1:
                fps_est = dt_sample
        if t is not None:
            prev_time = t
            break
    frame_dt_est = fps_est if fps_est is not None else (1.0 / 4.0)
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
                dt = frame_dt_est
            if 0 <= x < w and 0 <= y < h:
                heat[y, x] += dt
        prev_time = t
    heat      = cv2.GaussianBlur(heat, (0, 0), sigmaX=sigma, sigmaY=sigma)
    heat_norm = cv2.normalize(heat, None, 0, 255, cv2.NORM_MINMAX)
    heat_uint8 = heat_norm.astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_uint8, cv2.COLORMAP_JET)
    overlay    = cv2.addWeighted(first_frame, 0.6, heat_color, 0.4, 0)
    output_path = output_dir / f"{video_path.stem}_{ts}_heatmap.jpg"
    cv2.imwrite(str(output_path), overlay)
    return output_path


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


def build_rerun_command(video_path, args, cfg):
    resolved_mog2_threshold = cfg.get("mog2_threshold",  args.mog2_threshold)
    resolved_morph_open_k   = cfg.get("morph_open_k",    args.morph_open_k)
    resolved_morph_close_k  = cfg.get("morph_close_k",   args.morph_close_k)
    resolved_mog2_history_s = cfg.get("mog2_history_s",  args.mog2_history_s)

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
