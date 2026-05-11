import math
import cv2
import numpy as np

from geometry import point_in_ellipse, euclidean_px, euclidean_cm

SLOW_HISTORY_S = 15.0
_SPEED_WINDOW  = 15


def create_speed_adaptive_detector(cfg, fps, scale_x, scale_y, p15, p85):
    slow_history = max(1, int(round(SLOW_HISTORY_S * fps)))
    fast_sub = cv2.createBackgroundSubtractorMOG2(
        history       = cfg["mog2_history"],
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )
    slow_sub = cv2.createBackgroundSubtractorMOG2(
        history       = slow_history,
        varThreshold  = cfg["mog2_threshold"],
        detectShadows = cfg["mog2_detect_shadow"],
    )
    return {
        "fast_sub":    fast_sub,
        "slow_sub":    slow_sub,
        "scale_x":     scale_x,
        "scale_y":     scale_y,
        "fps":         fps,
        "p15":         p15,
        "p85":         p85,
        "speed_buf":   [],
        "last_speed":  None,
        "gap_frames":  0,
    }


def warmup_detector(detector, frame, learning_rate):
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame
    detector["fast_sub"].apply(gray, learningRate=learning_rate)
    detector["slow_sub"].apply(gray, learningRate=learning_rate)


def _sigmoid_blend(speed, p15, p85):
    if p85 <= p15:
        return 0.5
    mid   = (p15 + p85) / 2.0
    scale = (p85 - p15) / 2.0
    x     = (speed - mid) / (scale * 0.6)
    return 1.0 / (1.0 + math.exp(-x))


def _update_speed(detector, pos, prev_pos):
    if pos is None or prev_pos is None:
        detector["gap_frames"] += 1
        decay = math.exp(-detector["gap_frames"] / detector["fps"])
        if detector["last_speed"] is not None:
            detector["last_speed"] *= decay
        return

    detector["gap_frames"] = 0
    dist_cm = euclidean_cm(prev_pos, pos, detector["scale_x"], detector["scale_y"])
    speed   = dist_cm * detector["fps"]

    buf = detector["speed_buf"]
    buf.append(speed)
    if len(buf) > _SPEED_WINDOW:
        buf.pop(0)
    detector["last_speed"] = float(np.median(buf))


def compute_temporal_bg(frame_buffer):
    if not frame_buffer:
        return None
    return np.median(np.stack(frame_buffer, axis=0), axis=0).astype(np.uint8)


def detect_temporal(frame, temporal_bg, cfg, pool_mask, pool):
    if temporal_bg is None:
        return []
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY) if len(frame.shape) == 3 else frame.copy()
    diff = cv2.absdiff(gray, temporal_bg)
    if pool_mask is not None:
        diff = cv2.bitwise_and(diff, diff, mask=pool_mask)
    masked_vals = diff[pool_mask > 0] if pool_mask is not None else diff.ravel()
    if masked_vals.size == 0:
        return []
    thresh = float(np.std(masked_vals)) * 1.5
    thresh = max(thresh, 8.0)
    _, binary = cv2.threshold(diff, thresh, 255, cv2.THRESH_BINARY)
    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg["morph_open_k"],  cfg["morph_open_k"]))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (cfg["morph_close_k"], cfg["morph_close_k"]))
    binary  = cv2.morphologyEx(binary, cv2.MORPH_OPEN,  k_open)
    binary  = cv2.morphologyEx(binary, cv2.MORPH_CLOSE, k_close)
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
    return candidates


def _temporal_confirms(cx, cy, temporal_candidates, radius):
    for tx, ty, _, _ in temporal_candidates:
        if euclidean_px((cx, cy), (tx, ty)) <= radius:
            return True
    return False


def detect_rat_adaptive(frame, detector, cfg, pool_mask=None, pool=None, frame_idx=0, prev_pos=None, temporal_bg=None):
    fast_candidates     = _extract_candidates(frame, detector["fast_sub"], cfg, pool_mask, pool, frame_idx)
    slow_candidates     = _extract_candidates(frame, detector["slow_sub"], cfg, pool_mask, pool, frame_idx)
    temporal_candidates = detect_temporal(frame, temporal_bg, cfg, pool_mask, pool)

    current_speed = detector["last_speed"] if detector["last_speed"] is not None else detector["p85"]
    w_fast = _sigmoid_blend(current_speed, detector["p15"], detector["p85"])

    if w_fast >= 0.75 or not slow_candidates:
        candidates = fast_candidates
    elif w_fast <= 0.25 or not fast_candidates:
        candidates = slow_candidates
    else:
        seen   = set()
        merged = []
        for c in fast_candidates + slow_candidates:
            key = (c[0] // 4, c[1] // 4)
            if key not in seen:
                seen.add(key)
                merged.append(c)
        candidates = merged

    if not candidates and prev_pos is not None:
        dive_cfg = dict(cfg)
        dive_cfg["min_contour_area"] = cfg["min_contour_area"] * 0.2
        fast_dive = _extract_candidates(frame, detector["fast_sub"], dive_cfg, pool_mask, pool, frame_idx)
        slow_dive = _extract_candidates(frame, detector["slow_sub"], dive_cfg, pool_mask, pool, frame_idx)
        temp_dive = detect_temporal(frame, temporal_bg, dive_cfg, pool_mask, pool)
        seen   = set()
        merged = []
        for c in fast_dive + slow_dive + temp_dive:
            key = (c[0] // 4, c[1] // 4)
            if key not in seen:
                seen.add(key)
                merged.append(c)
        fast_candidates     = fast_dive
        slow_candidates     = slow_dive
        temporal_candidates = temp_dive
        candidates          = merged

    if not candidates:
        _update_speed(detector, None, prev_pos)
        return None, None, fast_candidates, slow_candidates, temporal_candidates

    confirm_radius = cfg.get("rat_body_radius_px") or math.sqrt(cfg.get("min_contour_area", 300) / math.pi)

    if prev_pos is not None:
        def sort_key(c):
            dist  = euclidean_px(prev_pos, (c[0], c[1]))
            bonus = -confirm_radius if _temporal_confirms(c[0], c[1], temporal_candidates, confirm_radius) else 0
            return dist + bonus
        candidates.sort(key=sort_key)
    else:
        def sort_key_area(c):
            bonus = confirm_radius if _temporal_confirms(c[0], c[1], temporal_candidates, confirm_radius) else 0
            return c[2] + bonus
        candidates.sort(key=sort_key_area, reverse=True)

    bx, by, area, winning_cnt = candidates[0]

    median_blob_area   = cfg.get("median_blob_area")
    rat_body_radius_px = cfg.get("rat_body_radius_px")
    if (prev_pos is not None
            and median_blob_area is not None
            and rat_body_radius_px is not None
            and area < median_blob_area * 0.50):
        dist_to_prev = euclidean_px(prev_pos, (bx, by))
        if dist_to_prev <= rat_body_radius_px * 5.0:
            smallness = 1.0 - (area / (median_blob_area * 0.50))
            alpha     = smallness * 0.6
            bx = int(round(bx * (1 - alpha) + prev_pos[0] * alpha))
            by = int(round(by * (1 - alpha) + prev_pos[1] * alpha))

    pos = (bx, by)
    _update_speed(detector, pos, prev_pos)
    return pos, winning_cnt, fast_candidates, slow_candidates, temporal_candidates


def _extract_candidates(frame, subtractor, cfg, pool_mask, pool, frame_idx):
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
    candidates = _extract_candidates(frame, subtractor, cfg, pool_mask, pool, frame_idx)
    if not candidates:
        return None, None, []
    if prev_pos is not None:
        candidates.sort(key=lambda c: euclidean_px(prev_pos, (c[0], c[1])))
    else:
        candidates.sort(key=lambda c: c[2], reverse=True)
    bx, by, area, winning_cnt = candidates[0]

    median_blob_area   = cfg.get("median_blob_area")
    rat_body_radius_px = cfg.get("rat_body_radius_px")
    if (prev_pos is not None
            and median_blob_area is not None
            and rat_body_radius_px is not None
            and area < median_blob_area * 0.50):
        dist_to_prev = euclidean_px(prev_pos, (bx, by))
        if dist_to_prev <= rat_body_radius_px * 2.0:
            smallness = 1.0 - (area / (median_blob_area * 0.50))
            alpha = smallness * 0.6
            bx = int(round(bx * (1 - alpha) + prev_pos[0] * alpha))
            by = int(round(by * (1 - alpha) + prev_pos[1] * alpha))

    return (bx, by), winning_cnt, candidates


def detect_rat_appearance(frame, cfg, pool_mask, pool, prev_pos=None):
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
    n = len(records)
    i = 0
    while i < n:
        if records[i]["x"] is not None:
            i += 1
            continue
        streak_start = i
        while i < n and records[i]["x"] is None:
            i += 1
        streak_end = i

        if streak_end >= n:
            break

        anchor = (records[streak_end]["x"], records[streak_end]["y"])

        for j in range(streak_end - 1, streak_start - 1, -1):
            candidates = missed_candidates.get(j, [])
            if not candidates:
                continue
            candidates_sorted = sorted(candidates, key=lambda c: euclidean_px(anchor, (c[0], c[1])))
            bx, by, _, _ = candidates_sorted[0]
            dist = euclidean_px(anchor, (bx, by))
            if dist > jump_threshold_px:
                break
            records[j]["x"] = bx
            records[j]["y"] = by
            anchor = (bx, by)