import argparse

from constants import NAMED_COLORS


def parse_point(s):
    try:
        parts = s.split(",")
        if len(parts) != 2:
            raise ValueError
        return (int(parts[0]), int(parts[1]))
    except (ValueError, AttributeError):
        raise argparse.ArgumentTypeError(f"Invalid point '{s}'. Expected format: x,y (e.g. 320,240)")

def fmt_pt(pt):
    return f"{pt[0]},{pt[1]}"

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

def build_arg_parser():
    parser = argparse.ArgumentParser(description="Track a rat in a water maze video.")
    parser.add_argument("--video",               required=True,  type=str)
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
    parser.add_argument("--paraplatform",        default=None,   type=int, nargs="?", const=4)
    parser.add_argument("--proximity",           default=False,  action="store_true")
    parser.add_argument("--latency",             default=False,  action="store_true")
    parser.add_argument("--tracemapcolor",       default=None,   type=str)
    parser.add_argument("--appmode",             default=False,  action="store_true")
    parser.add_argument("--ratcolor",            default=None,   type=str)
    parser.add_argument("--colorall",            default=False,  action="store_true")
    parser.add_argument("--autoconfig",          default=False,  action="store_true",
                        help="Auto-detect optimal mog2_threshold, morph kernels, and mog2_history_s from the video")
    return parser
