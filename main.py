import csv
import json
import math
import time
import cv2
import numpy as np
from datetime import datetime
from pathlib  import Path

from constants      import NAMED_COLORS, QUADRANT_NAMES, PLATFORM_STEPS, PLATFORM_COLORS, QUADRANT_COLORS
from cli            import build_arg_parser, parse_point, parse_tracemap_color, fmt_pt
from geometry       import (pool_ellipse_from_nsew, make_ellipse_mask, euclidean_px,
                            euclidean_cm, point_in_platform, segment_crosses_platform_twice,
                            segment_enters_platform, scale_platform_corners, platform_center)
from detection      import detect_rat, detect_rat_appearance, interpolate_missing, retroactive_jump_correction
from calibration    import (pool_coords_valid, platform_coords_valid, needs_platform,
                            run_calibration, run_platform_calibration,
                            confirm_pool_from_args, confirm_platform_from_args,
                            appmode_calib, appmode_confirm)
from quadrant_stats import (empty_quadrant_stats, empty_quadrant_exits,
                            accumulate_segment, accumulate_static, count_quadrant_exits)
from drawing        import sc, sc_f, draw_transparent_banner, draw_leaderboard
from output         import tracemap, heatmap, emit_progress, build_rerun_command
from autoconfig      import run_autoconfig


def main():
    parser = build_arg_parser()
    args   = parser.parse_args()

    tracemap_color = parse_tracemap_color(args.tracemapcolor)
    if args.ratcolor:
        rat_color = parse_tracemap_color(args.ratcolor)
    elif args.colorall:
        rat_color = NAMED_COLORS["yellow"]
    else:
        rat_color = None
    secondary_color  = tuple(max(0, int(c * 0.60)) for c in rat_color) if args.colorall and rat_color is not None else None
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

    cap      = cv2.VideoCapture(str(video_path))
    _raw_fps = cap.get(cv2.CAP_PROP_FPS)
    if not _raw_fps:
        print("WARNING: Could not read FPS from video metadata; defaulting to 4.0. "
              "Timestamps and distances will be wrong if this is incorrect.", flush=True)
    fps          = _raw_fps or 4.0
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
                result = run_calibration(first_frame, require_platform=require_platform,
                                         para_scale=args.paraplatform if args.paraplatform is not None else 4)
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
            result = run_calibration(first_frame, require_platform=require_platform,
                                     para_scale=args.paraplatform if args.paraplatform is not None else 4)
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

    if args.autoconfig:
        ac = run_autoconfig(cap, fps, total_frames, start_frame, end_frame, cfg, pool_mask, pool)
        cfg["mog2_threshold"]       = ac["mog2_threshold"]
        cfg["morph_open_k"]         = ac["morph_open_k"]
        cfg["morph_close_k"]        = ac["morph_close_k"]
        cfg["mog2_history"]         = max(1, int(round(ac["mog2_history_s"] * fps)))
        cfg["mog2_history_s"]       = ac["mog2_history_s"]
        cfg["median_blob_area"]     = ac["median_blob_area"]
        cfg["rat_body_radius_px"]   = ac["rat_body_radius_px"]
        cfg["appearance_threshold"] = ac["appearance_threshold"]
        cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    has_platform     = require_platform and platform_coords_valid(cfg)
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

    para_latency_time_s          = None
    para_latency_dist_cm         = None
    para_latency_done            = False
    para_latency_dist_acc        = 0.0
    prev_inside_para_for_latency = False

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
    missed_candidates    = {}
    appearance_frames    = {}
    miss_streak          = 0
    APPEARANCE_TRIGGER   = 7

    live_proximity_sum   = 0.0
    live_proximity_count = 0

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
            if miss_streak == APPEARANCE_TRIGGER:
                streak_start_idx = frame_idx - (miss_streak - 1)
                for fi in range(streak_start_idx, frame_idx + 1):
                    if fi in appearance_frames and not missed_candidates.get(fi):
                        app_candidates = detect_rat_appearance(
                            appearance_frames[fi], cfg, pool_mask, pool, prev_pos)
                        if app_candidates:
                            missed_candidates[fi] = app_candidates
        else:
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
            cv2.putText(annotated, q, lp, cv2.FONT_HERSHEY_DUPLEX,
                        sc_f(annotated, 0.55), QUADRANT_COLORS[q], 1, cv2.LINE_AA)

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
            (status,                                         hud_color),
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
    tracemap_path = tracemap(records, first_frame, output_dir, video_path, ts, color=tracemap_color)
    heatmap_path  = heatmap(records, first_frame, output_dir, video_path, ts, sigma=heatmap_sigma)

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
