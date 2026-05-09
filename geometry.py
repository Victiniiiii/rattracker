import cv2
import math
import numpy as np


def pool_ellipse_from_nsew(west, north, east, south):
    center = line_intersection(west, east, north, south)
    if center is not None:
        cx, cy = center
    else:
        cx = (west[0] + east[0] + north[0] + south[0]) / 4
        cy = (west[1] + east[1] + north[1] + south[1]) / 4
    r1x = east[0] - cx
    r1y = east[1] - cy
    r2x = north[0] - cx
    r2y = north[1] - cy
    M = np.array([
        [r1x*r1x + r2x*r2x, r1x*r1y + r2x*r2y],
        [r1x*r1y + r2x*r2y, r1y*r1y + r2y*r2y],
    ], dtype=np.float64)
    eigenvalues, eigenvectors = np.linalg.eigh(M)
    rx = int(round(math.sqrt(eigenvalues[1])))
    ry = int(round(math.sqrt(eigenvalues[0])))
    angle = math.degrees(math.atan2(eigenvectors[1, 1], eigenvectors[0, 1]))
    return int(round(cx)), int(round(cy)), rx, ry, angle

def make_ellipse_mask(shape, cx, cy, rx, ry, angle):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
    return mask

def point_in_ellipse(x, y, cx, cy, rx, ry, angle) -> bool:
    px = x - cx
    py = y - cy
    theta = -math.radians(angle)
    cos_t = math.cos(theta)
    sin_t = math.sin(theta)
    xr = px * cos_t - py * sin_t
    yr = px * sin_t + py * cos_t
    return (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0

def euclidean_px(p1, p2) -> float:
    return math.sqrt((p2[0] - p1[0]) ** 2 + (p2[1] - p1[1]) ** 2)

def euclidean_cm(p1, p2, scale_x, scale_y) -> float:
    dx_real = (p2[0] - p1[0]) * scale_x
    dy_real = (p2[1] - p1[1]) * scale_y
    return math.sqrt(dx_real**2 + dy_real**2)

def cross2d(ax, ay, bx, by) -> float:
    return ax * by - ay * bx

def line_intersection(p1, p2, p3, p4):
    x1, y1 = p1
    x2, y2 = p2
    x3, y3 = p3
    x4, y4 = p4
    denom = (x1 - x2)*(y3 - y4) - (y1 - y2)*(x3 - x4)
    if abs(denom) < 1e-9:
        return None
    px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / denom
    py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / denom
    return px, py

def line_segment_intersection_t(p1, p2, q1, q2):
    dx = p2[0] - p1[0]
    dy = p2[1] - p1[1]
    qx = q2[0] - q1[0]
    qy = q2[1] - q1[1]
    denom = cross2d(dx, dy, qx, qy)
    if abs(denom) < 1e-9:
        return None
    wx = q1[0] - p1[0]
    wy = q1[1] - p1[1]
    t = cross2d(wx, wy, qx, qy) / denom
    u = cross2d(wx, wy, dx, dy) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None

def get_quadrant(x, y, west, north, east, south) -> str:
    center = line_intersection(west, east, north, south)
    if center is None:
        return "UNKNOWN"
    cx, cy = center
    we_dx = east[0] - west[0]
    we_dy = east[1] - west[1]
    ns_dx = south[0] - north[0]
    ns_dy = south[1] - north[1]
    px = x - cx
    py = y - cy
    side_ns = cross2d(ns_dx, ns_dy, px, py)
    side_we = cross2d(we_dx, we_dy, px, py)
    east_side  = side_ns < 0
    south_side = side_we > 0
    if east_side and not south_side:
        return "NE"
    elif not east_side and not south_side:
        return "NW"
    elif not east_side and south_side:
        return "SW"
    else:
        return "SE"

def segment_quadrant_splits(p1, p2, west, north, east, south):
    x1, y1 = p1[0], p1[1]
    x2, y2 = p2[0], p2[1]
    dx = x2 - x1
    dy = y2 - y1
    t_vals = [0.0, 1.0]
    t_ns = line_segment_intersection_t(p1, p2, north, south)
    if t_ns is not None and 0.0 < t_ns < 1.0:
        t_vals.append(t_ns)
    t_we = line_segment_intersection_t(p1, p2, west, east)
    if t_we is not None and 0.0 < t_we < 1.0:
        t_vals.append(t_we)
    t_vals = sorted(set(t_vals))
    splits = []
    for i in range(len(t_vals) - 1):
        t_a = t_vals[i]
        t_b = t_vals[i + 1]
        xa = x1 + t_a * dx
        ya = y1 + t_a * dy
        xb = x1 + t_b * dx
        yb = y1 + t_b * dy
        xm = (xa + xb) / 2
        ym = (ya + yb) / 2
        q  = get_quadrant(xm, ym, west, north, east, south)
        splits.append(((xa, ya), (xb, yb), q))
    return splits

def get_platform_edges(platform_corners):
    nw, ne, se, sw = platform_corners
    return [(nw, ne), (ne, se), (se, sw), (sw, nw)]

def point_in_platform(pt, platform_corners) -> bool:
    x, y = pt
    corners = list(platform_corners)
    n = len(corners)
    inside = False
    px, py = x, y
    j = n - 1
    for i in range(n):
        xi, yi = corners[i][0], corners[i][1]
        xj, yj = corners[j][0], corners[j][1]
        if ((yi > py) != (yj > py)) and (px < (xj - xi) * (py - yi) / (yj - yi + 1e-12) + xi):
            inside = not inside
        j = i
    return inside

def segment_crosses_platform_twice(p1, p2, platform_corners) -> bool:
    edges = get_platform_edges(platform_corners)
    crossings = []
    for edge_a, edge_b in edges:
        t = line_segment_intersection_t(p1, p2, edge_a, edge_b)
        if t is not None:
            crossings.append(t)
    unique_crossings = []
    for t in sorted(crossings):
        if not unique_crossings or abs(t - unique_crossings[-1]) > 1e-6:
            unique_crossings.append(t)
    return len(unique_crossings) >= 2

def segment_enters_platform(p1, p2, platform_corners, prev_inside: bool) -> bool:
    curr_inside = point_in_platform(p2, platform_corners)
    if not prev_inside and curr_inside:
        return True
    if not prev_inside and not curr_inside:
        return segment_crosses_platform_twice(p1, p2, platform_corners)
    return False

def scale_platform_corners(corners, scale):
    cx = sum(p[0] for p in corners) / 4
    cy = sum(p[1] for p in corners) / 4
    return [(cx + (p[0] - cx) * scale, cy + (p[1] - cy) * scale) for p in corners]

def platform_center(corners):
    return (sum(p[0] for p in corners) / 4, sum(p[1] for p in corners) / 4)
