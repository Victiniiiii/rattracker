import cv2
import math
import numpy as np

from detection import detect_rat
from geometry  import point_in_ellipse, euclidean_px


def run_autoconfig(cap, fps, total_frames, start_frame, end_frame, cfg, pool_mask, pool):
    print("[autoconfig] Starting analysis...", flush=True)

    cx, cy, rx, ry, angle = pool
    mean_pool_r_px = (rx + ry) / 2

    PROBE_THRESHOLD  = 32
    PROBE_WARMUP_S   = 3.0
    probe_warmup_f   = max(1, int(PROBE_WARMUP_S * fps))

    probe_cfg = dict(cfg)
    probe_cfg["mog2_threshold"]     = PROBE_THRESHOLD
    probe_cfg["mog2_learning_rate"] = -1.0
    probe_cfg["debug_frames"]       = 0

    def _make_probe_subtractor(start_at):
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
        sub  = _make_probe_subtractor(scan_start)
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
        rat_brightness = None
        bg_brightness  = None
        contrast       = None
    else:
        BRIGHTNESS_SAMPLES = 7
        sample_interval    = max(1, (end_frame - start_frame) // BRIGHTNESS_SAMPLES)
        rat_samples        = []
        bg_samples         = []

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
            probe_frame, probe_pos, probe_cnt = probe_result
            mask_rat = np.zeros(probe_frame.shape[:2], dtype=np.uint8)
            cv2.drawContours(mask_rat, [probe_cnt], -1, 255, -1)
            gray_frame     = cv2.cvtColor(probe_frame, cv2.COLOR_BGR2GRAY)
            rat_brightness = cv2.mean(gray_frame, mask=mask_rat)[0]
            cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
            ret_fb, ff = cap.read()
            if ret_fb:
                ff_gray       = cv2.cvtColor(ff, cv2.COLOR_BGR2GRAY) if len(ff.shape) == 3 else ff
                bg_brightness = cv2.mean(ff_gray, mask=pool_mask)[0]
            else:
                bg_brightness = 128.0

        contrast = abs(rat_brightness - bg_brightness)
        print(f"[autoconfig] rat_brightness={rat_brightness:.1f}  "
              f"bg_brightness={bg_brightness:.1f}  contrast={contrast:.1f}  "
              f"(from {len(rat_samples)} samples)", flush=True)

    if rat_brightness is not None and bg_brightness is not None:
        appearance_threshold = int((rat_brightness + bg_brightness) / 2)
    else:
        appearance_threshold = 180
    print(f"[autoconfig] appearance_threshold={appearance_threshold}", flush=True)

    TVAR_FRAMES  = 12
    TVAR_SAMPLES = 4
    tvar_values  = []

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
            cap.set(cv2.CAP_PROP_POS_FRAMES, anchor)
            pixel_stack = []
            for _ in range(TVAR_FRAMES):
                ret2, frm2 = cap.read()
                if not ret2:
                    break
                gray2 = cv2.cvtColor(frm2, cv2.COLOR_BGR2GRAY) if len(frm2.shape) == 3 else frm2
                vals  = gray2[pixel_coords[:, 0], pixel_coords[:, 1]].astype(np.float32)
                pixel_stack.append(vals)
            if len(pixel_stack) < 3:
                continue
            pixel_stack = np.array(pixel_stack)
            per_pixel_std = np.std(pixel_stack, axis=0)
            tvar_values.append(float(np.median(per_pixel_std)))

    if tvar_values:
        median_tvar        = float(np.median(tvar_values))
        suggested_threshold = max(8, int(round(median_tvar * 0.80)))
        print(f"[autoconfig] median_temporal_variance={median_tvar:.1f}  "
              f"suggested mog2_threshold={suggested_threshold}", flush=True)
    else:
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

    SWEEP_FRAMES   = 120
    sweep_interval = max(1, (end_frame - start_frame) // SWEEP_FRAMES)

    pool_area_px = math.pi * ((rx + ry) / 2) ** 2
    sweep_cfg = dict(cfg)
    sweep_cfg["mog2_threshold"] = suggested_threshold
    sweep_cfg["morph_open_k"]   = cfg["morph_open_k"]
    sweep_cfg["morph_close_k"]  = cfg["morph_close_k"]
    sweep_cfg["debug_frames"]   = 0
    sweep_cfg["max_contour_area"] = pool_area_px * 0.04

    sweep_sub = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = suggested_threshold,
        detectShadows = False,
    )
    warmup_begin = max(0, start_frame - cfg["mog2_history"])
    cap.set(cv2.CAP_PROP_POS_FRAMES, warmup_begin)
    for _ in range(start_frame - warmup_begin):
        ret, wf = cap.read()
        if not ret:
            break
        if len(wf.shape) == 3:
            wf = cv2.cvtColor(wf, cv2.COLOR_BGR2GRAY)
        sweep_sub.apply(wf, learningRate=-1.0)

    noise_counts   = []
    fragmentation  = []
    displacements  = []
    blob_areas     = []
    prev_sweep_pos = None

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

        noise_cnt        = 0
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

        if len(valid_candidates) >= 2:
            valid_candidates.sort(key=lambda c: c[2], reverse=True)
            top1 = valid_candidates[0]
            top2 = valid_candidates[1]
            dist_12       = euclidean_px((top1[0], top1[1]), (top2[0], top2[1]))
            combined_area = top1[2] + top2[2]
            fragmentation.append((dist_12, combined_area))
        else:
            fragmentation.append(None)

        if valid_candidates:
            best     = max(valid_candidates, key=lambda c: c[2])
            best_pos = (best[0], best[1])
            blob_areas.append(best[2])
            if prev_sweep_pos is not None:
                displacements.append(euclidean_px(prev_sweep_pos, best_pos))
            prev_sweep_pos = best_pos
        else:
            prev_sweep_pos = None

        fi += sweep_interval

    avg_noise  = sum(noise_counts) / len(noise_counts) if noise_counts else 0
    base_open_k = cfg["morph_open_k"]
    if avg_noise > 10:
        open_k = base_open_k + 4
    elif avg_noise > 5:
        open_k = base_open_k + 2
    else:
        open_k = base_open_k
    open_k = max(3, open_k | 1)

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

    frag_rate    = sum(split_flags) / len(split_flags) if split_flags else 0
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

    if displacements:
        near_zero  = sum(1 for d in displacements if d < 5.0)
        zero_ratio = near_zero / len(displacements)
        disp_std   = float(np.std(displacements))

        if partial_rate > 0.35 or zero_ratio > 0.3 or disp_std > mean_pool_r_px * 0.15:
            suggested_history_s = 1.0
        elif partial_rate > 0.20 or zero_ratio > 0.15:
            suggested_history_s = 2.0
        else:
            suggested_history_s = 3.0
        print(f"[autoconfig] zero_ratio={zero_ratio:.2f}  disp_std={disp_std:.1f}  "
              f"suggested mog2_history_s={suggested_history_s}", flush=True)
    else:
        suggested_history_s = 3.0
        print("[autoconfig] Not enough displacement data, keeping mog2_history_s=3.0", flush=True)

    return {
        "mog2_threshold":       suggested_threshold,
        "morph_open_k":         open_k,
        "morph_close_k":        close_k,
        "mog2_history_s":       suggested_history_s,
        "median_blob_area":     median_blob_area,
        "rat_body_radius_px":   rat_body_radius_px,
        "appearance_threshold": appearance_threshold,
    }