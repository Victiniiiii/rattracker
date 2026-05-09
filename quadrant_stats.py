from constants import QUADRANT_NAMES
from geometry  import euclidean_px, euclidean_cm, get_quadrant, segment_quadrant_splits


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
    prev_q    = get_quadrant(prev_pos[0], prev_pos[1], west, north, east, south)
    splits    = segment_quadrant_splits(prev_pos, curr_pos, west, north, east, south)
    current_q = prev_q
    for (_, _, q) in splits:
        if q != current_q and current_q in exits_dict:
            exits_dict[current_q] += 1
        current_q = q
