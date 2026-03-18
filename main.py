import cv2
import numpy as np
import csv
import math
import argparse
from pathlib import Path

# ─────────────────────────────────────────────
# CONFIG  (tweak these if detection is off)
# ─────────────────────────────────────────────
# Background subtractor
MOG2_HISTORY       = 120     # Frames used to build background model (try 60–200)
MOG2_THRESHOLD     = 40      # Sensitivity — lower = more sensitive (try 20–80)
MOG2_DETECT_SHADOW = False   # Shadow detection (keep False for water maze)

# Morphology — cleans up the foreground mask
MORPH_OPEN_K       = 3       # Erosion kernel size — removes small noise blobs
MORPH_CLOSE_K      = 15      # Dilation kernel size — fills holes in the rat blob

# Blob size filter
MIN_CONTOUR_AREA   = 300     # Ignore blobs smaller than this (pixels²)
MAX_CONTOUR_AREA   = 12000   # Ignore blobs larger than this (reflections, artefacts)

# Trail length in the debug video
TRAIL_LEN          = 40      # How many past positions to draw as a fading trail

# Pool boundary — click the westmost, northmost, eastmost, southmost points of the pool edge
# Each value is (x, y). Set all to None to use the full frame instead.
POOL_WEST  = (286,  316)
POOL_NORTH = (514, 134)
POOL_EAST  = (742,  316)
POOL_SOUTH = (514, 498)
# To disable: POOL_WEST = POOL_NORTH = POOL_EAST = POOL_SOUTH = None

# Debug: save foreground mask images for the first N frames (0 = disabled)
DEBUG_FRAMES       = 0
# ─────────────────────────────────────────────


def pool_ellipse_from_nsew(west, north, east, south):
    """
    Derive an axis-aligned ellipse from the 4 cardinal edge points.
    centre = midpoint of west-east and north-south
    rx     = half the west-east width
    ry     = half the north-south height
    Returns (cx, cy, rx, ry)
    """
    cx = (west[0] + east[0])  / 2
    cy = (north[1] + south[1]) / 2
    rx = (east[0] - west[0])  / 2
    ry = (south[1] - north[1]) / 2
    return int(round(cx)), int(round(cy)), int(round(rx)), int(round(ry))


def make_ellipse_mask(shape, cx, cy, rx, ry):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), 0, 0, 360, 255, -1)
    return mask


def point_in_ellipse(x, y, cx, cy, rx, ry) -> bool:
    return ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0


def detect_rat(frame: np.ndarray, subtractor, pool_mask=None, pool=None, frame_idx=0):
    """
    Return (x, y) centroid of the rat using MOG2 background subtraction.
    Picks the largest foreground blob in the full frame.
    """
    fg_mask = subtractor.apply(frame)

    # Restrict to pool area if mask provided
    if pool_mask is not None:
        fg_mask = cv2.bitwise_and(fg_mask, fg_mask, mask=pool_mask)

    k_open  = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_OPEN_K,  MORPH_OPEN_K))
    k_close = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (MORPH_CLOSE_K, MORPH_CLOSE_K))
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_OPEN,  k_open)
    fg_mask = cv2.morphologyEx(fg_mask, cv2.MORPH_CLOSE, k_close)

    if DEBUG_FRAMES > 0 and frame_idx < DEBUG_FRAMES:
        cv2.imwrite(f"debug_frame_{frame_idx:03d}.png", fg_mask)

    contours, _ = cv2.findContours(fg_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    best      = None
    best_area = 0
    for cnt in contours:
        area = cv2.contourArea(cnt)
        if area < MIN_CONTOUR_AREA or area > MAX_CONTOUR_AREA:
            continue
        M = cv2.moments(cnt)
        if M["m00"] == 0:
            continue
        bx = int(M["m10"] / M["m00"])
        by = int(M["m01"] / M["m00"])
        # Discard if outside pool circle
        if pool is not None and not point_in_ellipse(bx, by, *pool):
            continue
        if area > best_area:
            best_area = area
            best = (bx, by)

    return best


def interpolate_missing(records: list) -> list:
    """
    Linearly interpolate (x, y) for frames where detection failed.
    Frames at the very start/end with no neighbours are left as None.
    """
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


def euclidean(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)


def main(video_path: str):
    video_path = Path(video_path)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap          = cv2.VideoCapture(str(video_path))
    fps          = cap.get(cv2.CAP_PROP_FPS) or 4.0
    frame_h      = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w      = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    print(f"Video : {video_path.name} | {frame_w}x{frame_h} | FPS: {fps:.2f} | Frames: {total_frames}")

    subtractor = cv2.createBackgroundSubtractorMOG2(
        history       = MOG2_HISTORY,
        varThreshold  = MOG2_THRESHOLD,
        detectShadows = MOG2_DETECT_SHADOW,
    )

    # ── Pool boundary circle ──
    pool      = None
    pool_mask = None
    if None not in (POOL_NORTH, POOL_SOUTH, POOL_WEST, POOL_EAST):
        pool = pool_ellipse_from_nsew(POOL_WEST, POOL_NORTH, POOL_EAST, POOL_SOUTH)
        pool_mask = make_ellipse_mask((frame_h, frame_w), *pool)
        cx, cy, rx, ry = pool
        print(f"Pool ellipse → centre=({cx}, {cy}), rx={rx}px, ry={ry}px")
    else:
        print("Pool boundary disabled — using full frame.")

    out_dir   = video_path.parent
    video_out = out_dir / (video_path.stem + "_tracked.mp4")
    fourcc    = cv2.VideoWriter_fourcc(*"mp4v")
    writer    = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    records        = []
    trail          = []
    frame_idx      = 0
    running_dist   = 0.0
    prev_pos       = None

    while True:
        ret, frame = cap.read()
        if not ret:
            break

        timestamp = frame_idx / fps
        pos       = detect_rat(frame, subtractor, pool_mask, pool, frame_idx)

        # Accumulate distance in real time
        if pos and prev_pos:
            running_dist += euclidean(prev_pos, pos)
        if pos:
            prev_pos = pos

        records.append({
            "frame":        frame_idx,
            "timestamp_s":  round(timestamp, 4),
            "x":            pos[0] if pos else None,
            "y":            pos[1] if pos else None,
            "interpolated": False,
        })

        annotated = frame.copy()

        # Draw pool boundary ellipse + cardinal dots + centre dot
        if pool is not None:
            cx, cy, rx, ry = pool
            cv2.ellipse(annotated, (cx, cy), (rx, ry), 0, 0, 360, (255, 100, 0), 2)
            dot_color = (255, 100, 0)
            for pt in [
                (cx,           cy),           # centre
                (POOL_WEST[0], POOL_WEST[1]), # W
                (POOL_NORTH[0],POOL_NORTH[1]),# N
                (POOL_EAST[0], POOL_EAST[1]), # E
                (POOL_SOUTH[0],POOL_SOUTH[1]),# S
            ]:
                cv2.circle(annotated, pt, 5, dot_color, -1)
                cv2.circle(annotated, pt, 6, (255, 255, 255), 1)

        if pos:
            trail.append(pos)
        if len(trail) > TRAIL_LEN:
            trail.pop(0)

        for i in range(1, len(trail)):
            alpha = i / len(trail)
            color = (0, int(255 * alpha), int(100 * (1 - alpha)))
            cv2.line(annotated, trail[i - 1], trail[i], color, 2)

        if pos:
            cv2.circle(annotated, pos, 8,  (0, 0, 255), -1)
            cv2.circle(annotated, pos, 10, (255, 255, 255), 1)

        status    = "DETECTED" if pos else "MISSING"
        hud_color = (0, 210, 0) if pos else (0, 0, 210)
        pos_str   = f"({pos[0]}, {pos[1]})" if pos else "n/a"
        cv2.rectangle(annotated, (5, 5), (300, 100), (0, 0, 0), -1)
        cv2.putText(annotated, f"Frame: {frame_idx:>4}   t = {timestamp:.2f}s",
                    (10, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, f"Position: {pos_str}",
                    (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (220, 220, 220), 1)
        cv2.putText(annotated, status,
                    (10, 72), cv2.FONT_HERSHEY_SIMPLEX, 0.5, hud_color, 1)
        cv2.putText(annotated, f"Distance: {running_dist:.1f} px",
                    (10, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 50), 1)

        writer.write(annotated)
        frame_idx += 1

    cap.release()
    writer.release()

    detected = sum(1 for r in records if r["x"] is not None)
    print(f"Processed {frame_idx} frames. Detected rat in {detected} frames.")
    print(f"Annotated video → {video_out}")

    records       = interpolate_missing(records)
    missing_after = sum(1 for r in records if r["x"] is None)
    if missing_after:
        print(f"Warning: {missing_after} frame(s) have no position "
              "(at start/end of video with no neighbours to interpolate from).")

    csv_path = out_dir / f"{video_path.stem}_coordinates.csv"
    with open(csv_path, "w", newline="") as f:
        writer_csv = csv.DictWriter(f, fieldnames=["frame", "timestamp_s", "x", "y", "interpolated"])
        writer_csv.writeheader()
        writer_csv.writerows(records)
    print(f"Coordinates saved → {csv_path}")

    total_distance = 0.0
    valid_pairs    = 0
    prev           = None
    for rec in records:
        if rec["x"] is not None:
            curr = (rec["x"], rec["y"])
            if prev is not None:
                total_distance += euclidean(prev, curr)
                valid_pairs    += 1
            prev = curr

    summary_path = out_dir / f"{video_path.stem}summary.txt"

    with open(summary_path, "w") as f:
        lines = [
            f"Video           : {video_path.name}",
            f"Resolution      : {frame_w}x{frame_h}",
            f"Total frames    : {frame_idx}",
            f"FPS             : {fps:.2f}",
            f"Duration (s)    : {frame_idx / fps:.2f}",
            f"",
            f"Detected frames : {detected}",
            f"Interpolated    : {sum(1 for r in records if r['interpolated'])}",
            f"Missing (no pos): {missing_after}",
            f"",
            f"Total distance swum : {total_distance:.2f} pixels",
            f"  (over {valid_pairs} consecutive frame pairs)",
            f"",
            f"Note: convert to real units using:",
            f"  scale (cm/px) = tank_real_diameter_cm / tank_diameter_in_pixels",
        ]
        f.write("\n".join(lines))

    print(f"Summary saved   → {summary_path}")
    print(f"\nTotal distance swum: {total_distance:.2f} pixels")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Track a rat in a cropped water maze video.")
    parser.add_argument("--video", required=True, help="Path to the input video file")
    args = parser.parse_args()
    main(args.video)