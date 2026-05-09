import cv2
import numpy as np

from geometry import point_in_ellipse, euclidean_px


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
