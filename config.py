from pathlib import Path
import json


CONFIG_FILE = Path(__file__).parent / "config.json"

DEFAULTS = {
    "mog2_history":       120,
    "mog2_threshold":     20,        # ↓ was 40 - more sensitive to low-contrast rats
    "mog2_detect_shadow": False,
    "morph_open_k":       3,
    "morph_close_k":      15,
    "min_contour_area":   300,
    "max_contour_area":   12000,
    "trail_len":          40,
    "debug_frames":       0,
    "pool_radius_cm":     60,
    "pool_nw":            None,
    "pool_ne":            None,
    "pool_sw":            None,
    "pool_se":            None,
    # ── CLAHE ──────────────────────────────────
    "clahe_clip_limit":   2.0,       # contrast amplification ceiling per tile
    "clahe_tile_size":    8,         # grid tile size (NxN); smaller = more local
    # ── Nearest-neighbour gating ───────────────
    "max_jump_px":        80,        # reject detections farther than this from last pos
    "gate_warmup_frames": 10,        # frames before gating activates (lets MOG2 settle)
}

def load_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
            # Merge with DEFAULTS so new keys always have a value
            cfg = {**DEFAULTS, **saved}
            for key in ("pool_nw", "pool_ne", "pool_sw", "pool_se"):
                if cfg[key] is not None:
                    cfg[key] = tuple(cfg[key])
            print(f"Config loaded from {CONFIG_FILE}")
            return cfg
        except Exception as e:
            print(f"Warning: could not read config.json ({e}). Using defaults.")
    return dict(DEFAULTS)

def save_config(cfg: dict):
    serialisable = {}
    for k, v in cfg.items():
        serialisable[k] = list(v) if isinstance(v, tuple) else v
    with open(CONFIG_FILE, "w") as f:
        json.dump(serialisable, f, indent=2)
    print(f"Config saved to {CONFIG_FILE}")


def pool_coords_valid(cfg: dict) -> bool:
    return all(cfg.get(k) is not None
               for k in ("pool_nw", "pool_ne", "pool_sw", "pool_se"))