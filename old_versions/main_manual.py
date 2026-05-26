"""
main_manual.py  –  Manual rat-position tagging for water-maze videos.

Instead of automatic MOG2 detection the user clicks the rat's position on
every frame.  The video is paused at each frame waiting for input.

Controls (per frame)
--------------------
  Left-click          – place / move the rat dot for this frame
  ENTER / SPACE       – confirm current frame and advance
  S                   – skip this frame (mark as missing → will be interpolated)
  B / Backspace       – go back one frame to re-click
  ESC                 – abort (no output saved)

Output files  (same folder as the video, suffix _manual)
---------------------------------------------------------
  {stem}_{ts}_manual.mp4
  {stem}_{ts}_manual_coordinates.csv
  {stem}_{ts}_manual_summary.txt
  {stem}_{ts}_manual_tracemap.jpg
  {stem}_{ts}_manual_heatmap.jpg

Comparison
----------
If a previous regular run is found in the same folder
  ({stem}_*_summary.txt, NOT containing "manual")
the latest one is parsed and a comparison file is written:
  {stem}_{ts}_manual_comparison.txt
"""

import cv2
import numpy as np
import csv
import math
import json
import argparse
import re
import sys
import time
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# All shared constants and helpers are copied verbatim from main.py so that
# this script is fully self-contained.
# ---------------------------------------------------------------------------

QUADRANT_NAMES  = ["NE", "NW", "SW", "SE"]
QUADRANT_COLORS = {
    "NE": (0,   200, 255),
    "NW": (0,   255, 100),
    "SW": (255, 180,   0),
    "SE": (180,   0, 255),
}

CALIB_STEPS = [
    ("WEST",  "west"),
    ("NORTH", "north"),
    ("EAST",  "east"),
    ("SOUTH", "south"),
]

CALIB_COLORS = {
    "WEST":  (255, 140, 0),
    "NORTH": (50, 205, 50),
    "EAST":  (30, 144, 255),
    "SOUTH": (238, 58, 140),
}

PLATFORM_STEPS = [
    ("NW", "platform_nw"),
    ("NE", "platform_ne"),
    ("SE", "platform_se"),
    ("SW", "platform_sw"),
]

PLATFORM_COLORS = {
    "NW": (255, 100, 200),
    "NE": (100, 200, 255),
    "SE": (200, 255, 100),
    "SW": (255, 200, 100),
}

NAMED_COLORS = {
    "red":     (0,   0,   255),
    "green":   (0,   255, 0),
    "blue":    (255, 0,   0),
    "yellow":  (0,   255, 255),
    "cyan":    (255, 255, 0),
    "magenta": (255, 0,   255),
    "white":   (255, 255, 255),
    "black":   (0,   0,   0),
    "orange":  (0,   165, 255),
    "purple":  (128, 0,   128),
    "pink":    (147, 20,  255),
    "lime":    (0,   255, 128),
    "teal":    (128, 128, 0),
    "navy":    (128, 0,   0),
    "maroon":  (0,   0,   128),
    "coral":   (80,  127, 255),
    "salmon":  (114, 128, 250),
    "gold":    (0,   215, 255),
    "silver":  (192, 192, 192),
    "indigo":  (130, 0,   75),
}

# ---------------------------------------------------------------------------
# Geometry helpers
# ---------------------------------------------------------------------------

def pool_ellipse_from_nsew(west, north, east, south):
    cx = (west[0] + east[0] + north[0] + south[0]) / 4
    cy = (west[1] + east[1] + north[1] + south[1]) / 4
    r1x = east[0] - cx;  r1y = east[1] - cy
    r2x = north[0] - cx; r2y = north[1] - cy
    M = np.array([
        [r1x*r1x + r2x*r2x, r1x*r1y + r2x*r2y],
        [r1x*r1y + r2x*r2y, r1y*r1y + r2y*r2y],
    ], dtype=np.float64)
    eigenvalues, eigenvectors = np.linalg.eigh(M)
    rx    = int(round(math.sqrt(eigenvalues[1])))
    ry    = int(round(math.sqrt(eigenvalues[0])))
    angle = math.degrees(math.atan2(eigenvectors[1, 1], eigenvectors[0, 1]))
    return int(round(cx)), int(round(cy)), rx, ry, angle

def make_ellipse_mask(shape, cx, cy, rx, ry, angle):
    mask = np.zeros(shape[:2], dtype=np.uint8)
    cv2.ellipse(mask, (cx, cy), (rx, ry), angle, 0, 360, 255, -1)
    return mask

def point_in_ellipse(x, y, cx, cy, rx, ry, angle) -> bool:
    px, py = x - cx, y - cy
    theta  = -math.radians(angle)
    xr = px * math.cos(theta) - py * math.sin(theta)
    yr = px * math.sin(theta) + py * math.cos(theta)
    return (xr / rx) ** 2 + (yr / ry) ** 2 <= 1.0

def euclidean_px(p1, p2) -> float:
    return math.sqrt((p2[0]-p1[0])**2 + (p2[1]-p1[1])**2)

def euclidean_cm(p1, p2, scale_x, scale_y) -> float:
    dx = (p2[0]-p1[0]) * scale_x
    dy = (p2[1]-p1[1]) * scale_y
    return math.sqrt(dx**2 + dy**2)

def cross2d(ax, ay, bx, by) -> float:
    return ax*by - ay*bx

def line_intersection(p1, p2, p3, p4):
    x1,y1=p1; x2,y2=p2; x3,y3=p3; x4,y4=p4
    denom = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4)
    if abs(denom) < 1e-9:
        return None
    px = ((x1*y2-y1*x2)*(x3-x4) - (x1-x2)*(x3*y4-y3*x4)) / denom
    py = ((x1*y2-y1*x2)*(y3-y4) - (y1-y2)*(x3*y4-y3*x4)) / denom
    return px, py

def line_segment_intersection_t(p1, p2, q1, q2):
    dx=p2[0]-p1[0]; dy=p2[1]-p1[1]
    qx=q2[0]-q1[0]; qy=q2[1]-q1[1]
    denom = cross2d(dx,dy,qx,qy)
    if abs(denom) < 1e-9:
        return None
    wx=q1[0]-p1[0]; wy=q1[1]-p1[1]
    t = cross2d(wx,wy,qx,qy) / denom
    u = cross2d(wx,wy,dx,dy) / denom
    if 0.0 <= t <= 1.0 and 0.0 <= u <= 1.0:
        return t
    return None

def get_quadrant(x, y, west, north, east, south) -> str:
    center = line_intersection(west, east, north, south)
    if center is None:
        return "UNKNOWN"
    cx, cy = center
    we_dx=east[0]-west[0];  we_dy=east[1]-west[1]
    ns_dx=south[0]-north[0]; ns_dy=south[1]-north[1]
    px=x-cx; py=y-cy
    side_ns = cross2d(ns_dx,ns_dy,px,py)
    side_we = cross2d(we_dx,we_dy,px,py)
    east_side  = side_ns < 0
    south_side = side_we > 0
    if east_side and not south_side:   return "NE"
    elif not east_side and not south_side: return "NW"
    elif not east_side and south_side: return "SW"
    else:                              return "SE"

def segment_quadrant_splits(p1, p2, west, north, east, south):
    x1,y1=p1[0],p1[1]; x2,y2=p2[0],p2[1]
    dx=x2-x1; dy=y2-y1
    t_vals = [0.0, 1.0]
    t_ns = line_segment_intersection_t(p1,p2,north,south)
    if t_ns is not None and 0.0 < t_ns < 1.0: t_vals.append(t_ns)
    t_we = line_segment_intersection_t(p1,p2,west,east)
    if t_we is not None and 0.0 < t_we < 1.0: t_vals.append(t_we)
    t_vals = sorted(set(t_vals))
    splits=[]
    for i in range(len(t_vals)-1):
        ta,tb = t_vals[i], t_vals[i+1]
        xa=x1+ta*dx; ya=y1+ta*dy
        xb=x1+tb*dx; yb=y1+tb*dy
        xm=(xa+xb)/2; ym=(ya+yb)/2
        q = get_quadrant(xm,ym,west,north,east,south)
        splits.append(((xa,ya),(xb,yb),q))
    return splits

def get_platform_edges(platform_corners):
    nw,ne,se,sw = platform_corners
    return [(nw,ne),(ne,se),(se,sw),(sw,nw)]

def point_in_platform(pt, platform_corners) -> bool:
    x,y = pt
    corners = list(platform_corners)
    n = len(corners)
    inside = False
    j = n-1
    for i in range(n):
        xi,yi = corners[i]
        xj,yj = corners[j]
        if ((yi>y)!=(yj>y)) and (x < (xj-xi)*(y-yi)/(yj-yi+1e-12)+xi):
            inside = not inside
        j=i
    return inside

def segment_crosses_platform_twice(p1, p2, platform_corners) -> bool:
    edges = get_platform_edges(platform_corners)
    crossings=[]
    for ea,eb in edges:
        t = line_segment_intersection_t(p1,p2,ea,eb)
        if t is not None: crossings.append(t)
    unique=[]
    for t in sorted(crossings):
        if not unique or abs(t-unique[-1])>1e-6: unique.append(t)
    return len(unique)>=2

def segment_enters_platform(p1, p2, platform_corners, prev_inside: bool) -> bool:
    curr_inside = point_in_platform(p2, platform_corners)
    if not prev_inside and curr_inside:     return True
    if not prev_inside and not curr_inside: return segment_crosses_platform_twice(p1,p2,platform_corners)
    return False

def scale_platform_corners(corners, scale):
    cx = sum(p[0] for p in corners)/4
    cy = sum(p[1] for p in corners)/4
    return [(cx+(p[0]-cx)*scale, cy+(p[1]-cy)*scale) for p in corners]

def platform_center(corners):
    return (sum(p[0] for p in corners)/4, sum(p[1] for p in corners)/4)

def empty_quadrant_stats():
    return {q: {"time_s": 0.0, "dist_cm": 0.0} for q in QUADRANT_NAMES}

def empty_quadrant_exits():
    return {q: 0 for q in QUADRANT_NAMES}

def accumulate_segment(stats, p1, p2, west, north, east, south, frame_dt, scale_x, scale_y):
    total_dist_px = euclidean_px(p1, p2)
    splits = segment_quadrant_splits(p1, p2, west, north, east, south)
    for idx, (sa, sb, q) in enumerate(splits):
        sub_dist_px = euclidean_px(sa, sb)
        frac = (sub_dist_px/total_dist_px) if total_dist_px>0 else (1.0 if idx==0 else 0.0)
        stats[q]["time_s"]  += frac * frame_dt
        stats[q]["dist_cm"] += euclidean_cm(sa, sb, scale_x, scale_y)

def accumulate_static(stats, pos, west, north, east, south, frame_dt):
    q = get_quadrant(pos[0], pos[1], west, north, east, south)
    stats[q]["time_s"] += frame_dt

def count_quadrant_exits(prev_pos, curr_pos, west, north, east, south, exits_dict):
    current_q = get_quadrant(prev_pos[0],prev_pos[1],west,north,east,south)
    splits = segment_quadrant_splits(prev_pos, curr_pos, west, north, east, south)
    for (_,_,q) in splits:
        if q!=current_q and current_q in exits_dict:
            exits_dict[current_q] += 1
        current_q = q

def interpolate_missing(records, max_gap=0):
    n = len(records)
    result = list(records)
    i = 0
    while i < n:
        if result[i]["x"] is None:
            left = i-1
            while left>=0 and result[left]["x"] is None: left-=1
            right = i
            while right<n and result[right]["x"] is None: right+=1
            if left>=0 and right<n:
                gap = right-left
                if max_gap==0 or gap-1<=max_gap:
                    x0,y0 = result[left]["x"],  result[left]["y"]
                    x1,y1 = result[right]["x"], result[right]["y"]
                    for j in range(left+1, right):
                        t = (j-left)/gap
                        result[j]["x"]            = round(x0+t*(x1-x0),2)
                        result[j]["y"]            = round(y0+t*(y1-y0),2)
                        result[j]["interpolated"] = True
            i = right
        else:
            i += 1
    return result

# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def res_scale(img):
    return min(img.shape[1], img.shape[0]) / 720.0

def sc(img, px):
    return max(1, int(round(px * res_scale(img))))

def sc_f(img, val):
    return val * res_scale(img)

def draw_transparent_banner(img, x0, y0, x1, y1, alpha=0.65):
    overlay = img.copy()
    cv2.rectangle(overlay, (x0,y0), (x1,y1), (8,8,8), -1)
    cv2.addWeighted(overlay, alpha, img, 1-alpha, 0, img)
    cv2.rectangle(img, (x0,y0), (x1,y1), (60,60,60), 1)

def draw_leaderboard(img, stats, total_time_s, total_dist_cm, quad_exits=None):
    sorted_q   = ["NW","NE","SW","SE"]
    show_exits = quad_exits is not None
    s          = res_scale(img)
    panel_w    = int((380 if show_exits else 320)*s)
    row_h      = int(26*s)
    pad        = int(10*s)
    header_h   = int(28*s)
    panel_h    = header_h + len(QUADRANT_NAMES)*row_h + pad
    x0 = img.shape[1]-panel_w-sc(img,10)
    y0 = sc(img,10)
    x1 = x0+panel_w
    y1 = y0+panel_h
    overlay = img.copy()
    cv2.rectangle(overlay,(x0,y0),(x1,y1),(8,8,8),-1)
    cv2.addWeighted(overlay,0.65,img,0.35,0,img)
    cv2.rectangle(img,(x0,y0),(x1,y1),(70,70,70),1)
    title_fs = sc_f(img,0.48)
    cv2.putText(img,"QUADRANT LEADERBOARD",(x0+pad,y0+int(18*s)),
                cv2.FONT_HERSHEY_DUPLEX,title_fs,(210,210,210),1,cv2.LINE_AA)
    row_fs   = sc_f(img,0.42)
    col2_off = int(58*s); col3_off = int(178*s); col4_off = int(308*s)
    for rank,q in enumerate(sorted_q):
        t_s  = stats[q]["time_s"];  d_cm = stats[q]["dist_cm"]
        t_pct= (t_s /total_time_s *100) if total_time_s >0 else 0.0
        d_pct= (d_cm/total_dist_cm*100) if total_dist_cm>0 else 0.0
        color = QUADRANT_COLORS[q]
        row_y = y0+header_h+rank*row_h+row_h-int(5*s)
        cv2.putText(img,f"#{rank+1} {q}",(x0+pad,row_y),cv2.FONT_HERSHEY_DUPLEX,row_fs,color,1,cv2.LINE_AA)
        cv2.putText(img,f"T:{t_s:5.1f}s {t_pct:4.1f}%",(x0+pad+col2_off,row_y),cv2.FONT_HERSHEY_DUPLEX,row_fs,(220,220,220),1,cv2.LINE_AA)
        cv2.putText(img,f"D:{d_cm:6.1f}cm {d_pct:4.1f}%",(x0+pad+col3_off,row_y),cv2.FONT_HERSHEY_DUPLEX,row_fs,(255,200,50),1,cv2.LINE_AA)
        if show_exits:
            cv2.putText(img,f"X:{quad_exits.get(q,0)}",(x0+pad+col4_off,row_y),cv2.FONT_HERSHEY_DUPLEX,row_fs,(100,200,255),1,cv2.LINE_AA)

# ---------------------------------------------------------------------------
# Output helpers  (tracemap / heatmap – identical logic to main.py)
# ---------------------------------------------------------------------------

def tracemap(records, first_frame, output_dir, video_path, ts, color=(0,255,255)):
    canvas = first_frame.copy()
    output_path = output_dir / f"{video_path.stem}_{ts}_manual_tracemap.jpg"
    prev_point = None
    for r in records:
        x,y = r.get("x"), r.get("y")
        if x is None or y is None: prev_point=None; continue
        point = (int(x),int(y))
        if prev_point is not None:
            cv2.line(canvas,prev_point,point,color,2,lineType=cv2.LINE_AA)
        prev_point = point
    cv2.imwrite(str(output_path), canvas)
    return output_path

def heatmap(records, first_frame, output_dir, video_path, ts, sigma=20):
    h,w = first_frame.shape[:2]
    heat = np.zeros((h,w), dtype=np.float32)
    prev_time = None
    for r in records:
        x,y,t = r.get("x"),r.get("y"),r.get("timestamp_s")
        if x is None or y is None or t is None: prev_time=None; continue
        x,y = int(x),int(y)
        if prev_time is not None:
            dt = t-prev_time
            if dt<0 or dt>1: dt=0
            if 0<=x<w and 0<=y<h: heat[y,x]+=dt
        prev_time = t
    heat  = cv2.GaussianBlur(heat,(0,0),sigmaX=sigma,sigmaY=sigma)
    heat_norm  = cv2.normalize(heat,None,0,255,cv2.NORM_MINMAX)
    heat_uint8 = heat_norm.astype(np.uint8)
    heat_color = cv2.applyColorMap(heat_uint8,cv2.COLORMAP_JET)
    overlay    = cv2.addWeighted(first_frame,0.6,heat_color,0.4,0)
    output_path = output_dir / f"{video_path.stem}_{ts}_manual_heatmap.jpg"
    cv2.imwrite(str(output_path), overlay)
    return output_path

# ---------------------------------------------------------------------------
# Calibration  (reused from main.py, no changes)
# ---------------------------------------------------------------------------

def parse_point(s):
    parts = s.split(",")
    return (int(parts[0]), int(parts[1]))

def fmt_pt(pt):
    return f"{pt[0]},{pt[1]}"

def pool_coords_valid(cfg):
    return all(cfg.get(k) is not None for k in ("pool_west","pool_north","pool_east","pool_south"))

def platform_coords_valid(cfg):
    return all(cfg.get(k) is not None for k in ("platform_nw","platform_ne","platform_se","platform_sw"))

def needs_platform(args):
    return any([args.platformcross, args.paraplatform is not None, args.proximity, args.latency])

def run_calibration(frame, require_platform=False):
    state = {"step":0,"pool_points":{},"platform_points":{},"phase":"pool","frame":frame.copy()}
    window = "Calibration"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame.shape[1],1280), min(frame.shape[0],720))

    def draw(base):
        img = base.copy()
        banner_h = sc(img,70)
        draw_transparent_banner(img,0,0,frame.shape[1],banner_h)
        tx,ty1,ty2 = sc(img,14),sc(img,30),sc(img,56)
        fs1,fs2 = sc_f(img,0.65),sc_f(img,0.50)
        if state["phase"]=="pool":
            step=state["step"]
            if step<len(CALIB_STEPS):
                cardinal,_ = CALIB_STEPS[step]; color=CALIB_COLORS[cardinal]
                cv2.putText(img,f"Step {step+1}/4 -- Click the {cardinal} point of the pool edge",
                            (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,color,1,cv2.LINE_AA)
                cv2.putText(img,"Press R to redo all points  |  ESC to abort",
                            (tx,ty2),cv2.FONT_HERSHEY_DUPLEX,fs2,(180,180,180),1,cv2.LINE_AA)
            else:
                if not require_platform:
                    cv2.putText(img,"All 4 points set -- press ENTER to confirm or R to redo",
                                (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,(100,255,180),1,cv2.LINE_AA)
        elif state["phase"]=="platform":
            step=state["step"]
            if step<len(PLATFORM_STEPS):
                corner,_ = PLATFORM_STEPS[step]; color=PLATFORM_COLORS[corner]
                cv2.putText(img,f"Pool done! Click {corner} platform corner (clockwise)",
                            (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,color,1,cv2.LINE_AA)
                cv2.putText(img,"Press R to redo all points  |  ESC to abort",
                            (tx,ty2),cv2.FONT_HERSHEY_DUPLEX,fs2,(180,180,180),1,cv2.LINE_AA)
            else:
                cv2.putText(img,"All 8 points set -- press ENTER to confirm or R to redo",
                            (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,(100,255,180),1,cv2.LINE_AA)
        dot_r,dot_ro = sc(img,7),sc(img,9)
        lbl_off=sc(img,12); lbl_fs=sc_f(img,0.52)
        for cardinal,pt in state["pool_points"].items():
            col=CALIB_COLORS[cardinal]
            cv2.circle(img,pt,dot_r,col,-1); cv2.circle(img,pt,dot_ro,(255,255,255),1)
            cv2.putText(img,cardinal,(pt[0]+lbl_off,pt[1]+sc(img,5)),cv2.FONT_HERSHEY_DUPLEX,lbl_fs,col,1,cv2.LINE_AA)
        if len(state["pool_points"])==4:
            p=state["pool_points"]
            result=pool_ellipse_from_nsew(p["WEST"],p["NORTH"],p["EAST"],p["SOUTH"])
            if result is not None:
                ecx,ecy,erx,ery,eangle=result
                cv2.ellipse(img,(ecx,ecy),(erx,ery),eangle,0,360,(100,255,180),2)
                cv2.line(img,p["NORTH"],p["SOUTH"],(100,255,180),1)
                cv2.line(img,p["WEST"],p["EAST"],(100,255,180),1)
        for corner,pt in state["platform_points"].items():
            col=PLATFORM_COLORS[corner]
            cv2.circle(img,pt,dot_r,col,-1); cv2.circle(img,pt,dot_ro,(255,255,255),1)
            cv2.putText(img,corner,(pt[0]+lbl_off,pt[1]+sc(img,5)),cv2.FONT_HERSHEY_DUPLEX,lbl_fs,col,1,cv2.LINE_AA)
        pts_ord=[state["platform_points"].get(s[0]) for s in PLATFORM_STEPS if s[0] in state["platform_points"]]
        if len(pts_ord)>=2:
            for i in range(len(pts_ord)-1): cv2.line(img,pts_ord[i],pts_ord[i+1],(200,200,50),1)
        if len(state["platform_points"])==4:
            corners_ordered=[state["platform_points"][s[0]] for s in PLATFORM_STEPS]
            pts_np=np.array(corners_ordered,dtype=np.int32)
            cv2.polylines(img,[pts_np],isClosed=True,color=(200,200,50),thickness=2)
            if require_platform:
                para_preview=scale_platform_corners(corners_ordered,math.sqrt(4))
                para_pts_np=np.array([(int(p[0]),int(p[1])) for p in para_preview],dtype=np.int32)
                cv2.polylines(img,[para_pts_np],isClosed=True,color=(0,180,255),thickness=1)
        return img

    def on_click(event,x,y,flags,param):
        if event!=cv2.EVENT_LBUTTONDOWN: return
        if state["phase"]=="pool":
            step=state["step"]
            if step>=len(CALIB_STEPS): return
            cardinal,_=CALIB_STEPS[step]
            state["pool_points"][cardinal]=(x,y); state["step"]+=1
            if state["step"]==len(CALIB_STEPS) and require_platform:
                state["phase"]="platform"; state["step"]=0
        elif state["phase"]=="platform":
            step=state["step"]
            if step>=len(PLATFORM_STEPS): return
            corner,_=PLATFORM_STEPS[step]
            state["platform_points"][corner]=(x,y); state["step"]+=1
        cv2.imshow(window,draw(state["frame"]))

    cv2.setMouseCallback(window,on_click)
    cv2.imshow(window,draw(state["frame"]))
    result=None
    while True:
        key=cv2.waitKey(20)&0xFF
        if key==27: break
        elif key in (ord('r'),ord('R')):
            state.update({"step":0,"phase":"pool","pool_points":{},"platform_points":{}})
            cv2.imshow(window,draw(state["frame"]))
        elif key in (13,10):
            p=state["pool_points"]
            if len(p)==4:
                if require_platform:
                    plat=state["platform_points"]
                    if len(plat)==4:
                        result={"pool_west":p["WEST"],"pool_north":p["NORTH"],
                                "pool_east":p["EAST"],"pool_south":p["SOUTH"],
                                "platform_nw":plat["NW"],"platform_ne":plat["NE"],
                                "platform_se":plat["SE"],"platform_sw":plat["SW"]}; break
                else:
                    result={"pool_west":p["WEST"],"pool_north":p["NORTH"],
                            "pool_east":p["EAST"],"pool_south":p["SOUTH"]}; break
        cv2.imshow(window,draw(state["frame"]))
    cv2.destroyWindow(window)
    return result

def run_platform_calibration(frame):
    state={"step":0,"points":{},"frame":frame.copy()}
    window="Platform Calibration"
    cv2.namedWindow(window,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window,min(frame.shape[1],1280),min(frame.shape[0],720))

    def draw(base):
        img=base.copy()
        draw_transparent_banner(img,0,0,frame.shape[1],sc(img,70))
        tx,ty1,ty2=sc(img,14),sc(img,30),sc(img,56)
        fs1,fs2=sc_f(img,0.65),sc_f(img,0.50)
        step=state["step"]
        if step<len(PLATFORM_STEPS):
            corner,_=PLATFORM_STEPS[step]; color=PLATFORM_COLORS[corner]
            cv2.putText(img,f"Platform Step {step+1}/4 -- Click the {corner} corner (clockwise)",
                        (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,color,1,cv2.LINE_AA)
            cv2.putText(img,"Press R to redo  |  ESC to skip platform",
                        (tx,ty2),cv2.FONT_HERSHEY_DUPLEX,fs2,(180,180,180),1,cv2.LINE_AA)
        else:
            cv2.putText(img,"All 4 corners set -- press ENTER to confirm or R to redo",
                        (tx,ty1),cv2.FONT_HERSHEY_DUPLEX,fs1,(100,255,180),1,cv2.LINE_AA)
        pts_ord=[state["points"].get(s[0]) for s in PLATFORM_STEPS if s[0] in state["points"]]
        if len(pts_ord)>=2:
            for i in range(len(pts_ord)-1): cv2.line(img,pts_ord[i],pts_ord[i+1],(200,200,50),1)
        if len(state["points"])==4:
            cords=[state["points"][s[0]] for s in PLATFORM_STEPS]
            cv2.polylines(img,[np.array(cords,dtype=np.int32)],True,(200,200,50),2)
        dot_r,dot_ro=sc(img,7),sc(img,9); lbl_off=sc(img,12); lbl_fs=sc_f(img,0.52)
        for corner,pt in state["points"].items():
            col=PLATFORM_COLORS[corner]
            cv2.circle(img,pt,dot_r,col,-1); cv2.circle(img,pt,dot_ro,(255,255,255),1)
            cv2.putText(img,corner,(pt[0]+lbl_off,pt[1]+sc(img,5)),cv2.FONT_HERSHEY_DUPLEX,lbl_fs,col,1,cv2.LINE_AA)
        return img

    def on_click(event,x,y,flags,param):
        if event!=cv2.EVENT_LBUTTONDOWN: return
        step=state["step"]
        if step>=len(PLATFORM_STEPS): return
        corner,_=PLATFORM_STEPS[step]
        state["points"][corner]=(x,y); state["step"]+=1
        cv2.imshow(window,draw(state["frame"]))

    cv2.setMouseCallback(window,on_click)
    cv2.imshow(window,draw(state["frame"]))
    result=None
    while True:
        key=cv2.waitKey(20)&0xFF
        if key==27: break
        elif key in (ord('r'),ord('R')):
            state["step"]=0; state["points"]={}
            cv2.imshow(window,draw(state["frame"]))
        elif key in (13,10):
            p=state["points"]
            if len(p)==4:
                result={"platform_nw":p["NW"],"platform_ne":p["NE"],
                        "platform_se":p["SE"],"platform_sw":p["SW"]}; break
        cv2.imshow(window,draw(state["frame"]))
    cv2.destroyWindow(window)
    return result

def confirm_pool_from_args(frame, cfg):
    p={"WEST":cfg["pool_west"],"NORTH":cfg["pool_north"],"EAST":cfg["pool_east"],"SOUTH":cfg["pool_south"]}
    result=pool_ellipse_from_nsew(p["WEST"],p["NORTH"],p["EAST"],p["SOUTH"])
    if result is None: return False
    ecx,ecy,erx,ery,eangle=result
    img=frame.copy()
    cv2.ellipse(img,(ecx,ecy),(erx,ery),eangle,0,360,(100,255,180),2)
    cv2.line(img,p["NORTH"],p["SOUTH"],(100,255,180),1)
    cv2.line(img,p["WEST"],p["EAST"],(100,255,180),1)
    for cardinal,pt in p.items():
        col=CALIB_COLORS[cardinal]
        cv2.circle(img,pt,sc(img,7),col,-1); cv2.circle(img,pt,sc(img,9),(255,255,255),1)
        cv2.putText(img,cardinal,(pt[0]+sc(img,12),pt[1]+sc(img,5)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.52),col,1,cv2.LINE_AA)
    draw_transparent_banner(img,0,0,frame.shape[1],sc(img,70))
    cv2.putText(img,"Saved pool coordinates found -- confirm or repick",
                (sc(img,14),sc(img,28)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.65),(100,255,180),1,cv2.LINE_AA)
    cv2.putText(img,"ENTER --> Continue     ESC --> Repick",
                (sc(img,14),sc(img,56)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.52),(180,180,180),1,cv2.LINE_AA)
    window="Pool Confirmation"
    cv2.namedWindow(window,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window,min(frame.shape[1],1280),min(frame.shape[0],720))
    cv2.imshow(window,img)
    confirmed=False
    while True:
        key=cv2.waitKey(20)&0xFF
        if key in (13,10): confirmed=True; break
        elif key==27: break
    cv2.destroyWindow(window)
    return confirmed

def confirm_platform_from_args(frame, cfg):
    corners=[cfg["platform_nw"],cfg["platform_ne"],cfg["platform_se"],cfg["platform_sw"]]
    img=frame.copy()
    cv2.polylines(img,[np.array(corners,dtype=np.int32)],True,(200,200,50),2)
    for i,(corner_name,_) in enumerate(PLATFORM_STEPS):
        pt=corners[i]; col=PLATFORM_COLORS[corner_name]
        cv2.circle(img,pt,sc(img,7),col,-1); cv2.circle(img,pt,sc(img,9),(255,255,255),1)
        cv2.putText(img,corner_name,(pt[0]+sc(img,12),pt[1]+sc(img,5)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.52),col,1,cv2.LINE_AA)
    draw_transparent_banner(img,0,0,frame.shape[1],sc(img,70))
    cv2.putText(img,"Saved platform coordinates found -- confirm or repick",
                (sc(img,14),sc(img,28)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.65),(100,255,180),1,cv2.LINE_AA)
    cv2.putText(img,"ENTER --> Continue     ESC --> Repick",
                (sc(img,14),sc(img,56)),cv2.FONT_HERSHEY_DUPLEX,sc_f(img,0.52),(180,180,180),1,cv2.LINE_AA)
    window="Platform Confirmation"
    cv2.namedWindow(window,cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window,min(frame.shape[1],1280),min(frame.shape[0],720))
    cv2.imshow(window,img)
    confirmed=False
    while True:
        key=cv2.waitKey(20)&0xFF
        if key in (13,10): confirmed=True; break
        elif key==27: break
    cv2.destroyWindow(window)
    return confirmed

# ---------------------------------------------------------------------------
# Summary parser  – extract comparable stats from a regular summary.txt
# ---------------------------------------------------------------------------

def parse_summary_stats(path: Path) -> dict:
    """
    Parse a regular (non-manual) summary.txt and return a dict of numeric
    stats used for comparison.  Missing fields are left as None.
    """
    text = path.read_text(encoding="utf-8", errors="replace")
    stats = {}

    def extract_float(pattern):
        m = re.search(pattern, text)
        return float(m.group(1)) if m else None

    def extract_int(pattern):
        m = re.search(pattern, text)
        return int(m.group(1)) if m else None

    # Total distance
    # Line: "Total distance  :  123.45 cm"  (or French/Turkish variants)
    # We look for the cm line (second occurrence of "Total distance")
    dist_matches = re.findall(r"Total distance\s*:\s*([\d.]+)\s*cm", text)
    if not dist_matches:
        dist_matches = re.findall(r"Distance totale\s*:\s*([\d.]+)\s*cm", text)
    if not dist_matches:
        dist_matches = re.findall(r"Toplam mesafe\s*:\s*([\d.]+)\s*cm", text)
    stats["total_dist_cm"] = float(dist_matches[0]) if dist_matches else None

    # Platform exits
    m = re.search(r"Platform exits\s*:\s*(\d+)", text)
    if not m: m = re.search(r"Sorties plateau\s*:\s*(\d+)", text)
    if not m: m = re.search(r"Platform cikisi\s*:\s*(\d+)", text)
    stats["platform_exits"] = int(m.group(1)) if m else None

    # ParaPlatform time / dist / exits
    m = re.search(r"ParaPlatform time\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"Temps ParaPlat\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"ParaPlatform sure\s*:\s*([\d.]+)\s*s", text)
    stats["para_time_s"] = float(m.group(1)) if m else None

    m = re.search(r"ParaPlatform dist\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Dist ParaPlat\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"ParaPlatform mesafe\s*:\s*([\d.]+)\s*cm", text)
    stats["para_dist_cm"] = float(m.group(1)) if m else None

    m = re.search(r"ParaPlatform exits\s*:\s*(\d+)", text)
    if not m: m = re.search(r"Sorties ParaPlat\s*:\s*(\d+)", text)
    if not m: m = re.search(r"ParaPlatform cikis\s*:\s*(\d+)", text)
    stats["para_exits"] = int(m.group(1)) if m else None

    # Proximity
    m = re.search(r"Avg dist to center\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Dist moy centre\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Ort\. merkez mesafesi\s*:\s*([\d.]+)\s*cm", text)
    stats["proximity_avg_cm"] = float(m.group(1)) if m else None

    # Latency time / dist
    m = re.search(r"Time to first entry\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"Temps 1ere entree\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"Ilk girise kadar sure\s*:\s*([\d.]+)\s*s", text)
    stats["latency_time_s"] = float(m.group(1)) if m else None

    m = re.search(r"Dist to first entry\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Dist 1ere entree\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Ilk girise kadar mesafe\s*:\s*([\d.]+)\s*cm", text)
    stats["latency_dist_cm"] = float(m.group(1)) if m else None

    # Para-latency time / dist
    m = re.search(r"Time to first para entry\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"Temps 1ere entree para\s*:\s*([\d.]+)\s*s", text)
    if not m: m = re.search(r"Para ilk girise kadar sure\s*:\s*([\d.]+)\s*s", text)
    stats["para_latency_time_s"] = float(m.group(1)) if m else None

    m = re.search(r"Dist to first para entry\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Dist 1ere entree para\s*:\s*([\d.]+)\s*cm", text)
    if not m: m = re.search(r"Para ilk girise kadar mesafe\s*:\s*([\d.]+)\s*cm", text)
    stats["para_latency_dist_cm"] = float(m.group(1)) if m else None

    # Quadrant stats – look for table rows like "NE         12.34     xx.x%  ..."
    for q in QUADRANT_NAMES:
        m = re.search(rf"{q}\s+([\d.]+)\s+[\d.]+%\s+([\d.]+)", text)
        if m:
            stats[f"quad_{q}_time_s"]  = float(m.group(1))
            stats[f"quad_{q}_dist_cm"] = float(m.group(2))
        else:
            stats[f"quad_{q}_time_s"]  = None
            stats[f"quad_{q}_dist_cm"] = None

    return stats

def find_latest_regular_summary(video_path: Path) -> Path | None:
    """
    Look for {stem}_*_summary.txt files in the same folder that do NOT
    contain 'manual' in their name, and return the most recent one.
    """
    stem = video_path.stem
    candidates = [
        p for p in video_path.parent.glob(f"{stem}_*_summary.txt")
        if "manual" not in p.name
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)

# ---------------------------------------------------------------------------
# Comparison writer
# ---------------------------------------------------------------------------

COMPARE_FIELDS = [
    ("total_dist_cm",        "Total distance (cm)"),
    ("platform_exits",       "Platform exits"),
    ("para_time_s",          "ParaPlatform time (s)"),
    ("para_dist_cm",         "ParaPlatform dist (cm)"),
    ("para_exits",           "ParaPlatform exits"),
    ("proximity_avg_cm",     "Proximity avg (cm)"),
    ("latency_time_s",       "Latency time (s)"),
    ("latency_dist_cm",      "Latency dist (cm)"),
    ("para_latency_time_s",  "Para-latency time (s)"),
    ("para_latency_dist_cm", "Para-latency dist (cm)"),
    ("quad_NE_time_s",       "NE time (s)"),
    ("quad_NE_dist_cm",      "NE dist (cm)"),
    ("quad_NW_time_s",       "NW time (s)"),
    ("quad_NW_dist_cm",      "NW dist (cm)"),
    ("quad_SW_time_s",       "SW time (s)"),
    ("quad_SW_dist_cm",      "SW dist (cm)"),
    ("quad_SE_time_s",       "SE time (s)"),
    ("quad_SE_dist_cm",      "SE dist (cm)"),
]

def write_comparison(path: Path, manual_stats: dict, ref_stats: dict, ref_summary_path: Path):
    lines = [
        "=" * 72,
        "  MANUAL vs AUTO  COMPARISON",
        "=" * 72,
        f"  Reference (auto) : {ref_summary_path.name}",
        f"  Manual result    : {path.stem.replace('_comparison','')}",
        "=" * 72,
        "",
        f"{'Metric':<30} {'Auto':>14} {'Manual':>14} {'Ratio':>10}",
        f"{'-'*30} {'-'*14} {'-'*14} {'-'*10}",
    ]
    for key, label in COMPARE_FIELDS:
        ref_val    = ref_stats.get(key)
        manual_val = manual_stats.get(key)
        if ref_val is None and manual_val is None:
            continue  # stat not present in either run — skip silently
        ref_str    = f"{ref_val:.2f}"    if isinstance(ref_val,    float) else (str(ref_val)    if ref_val    is not None else "N/A")
        manual_str = f"{manual_val:.2f}" if isinstance(manual_val, float) else (str(manual_val) if manual_val is not None else "N/A")
        if ref_val is not None and manual_val is not None and ref_val != 0:
            ratio = manual_val / ref_val * 100
            ratio_str = f"{ratio:.1f}%"
        elif ref_val == 0 and manual_val == 0:
            ratio_str = "100.0%"
        else:
            ratio_str = "N/A"
        lines.append(f"{label:<30} {ref_str:>14} {manual_str:>14} {ratio_str:>10}")
    lines += ["", "  Ratio = manual / auto × 100  (100% = identical)"]
    with open(path,"w",encoding="utf-8") as f:
        f.write("\n".join(lines))
    return lines

# ---------------------------------------------------------------------------
# Manual-stats extractor  (mirrors parse_summary_stats but from live data)
# ---------------------------------------------------------------------------

def build_manual_stats(
    total_dist_cm, platform_exits, para_time_s, para_dist_cm, para_exits,
    proximity_avg_cm, latency_time_s, latency_dist_cm,
    para_latency_time_s, para_latency_dist_cm,
    q_stats_final,
):
    stats = {
        "total_dist_cm":        total_dist_cm,
        "platform_exits":       platform_exits,
        "para_time_s":          para_time_s,
        "para_dist_cm":         para_dist_cm,
        "para_exits":           para_exits,
        "proximity_avg_cm":     proximity_avg_cm,
        "latency_time_s":       latency_time_s,
        "latency_dist_cm":      latency_dist_cm,
        "para_latency_time_s":  para_latency_time_s,
        "para_latency_dist_cm": para_latency_dist_cm,
    }
    for q in QUADRANT_NAMES:
        stats[f"quad_{q}_time_s"]  = q_stats_final[q]["time_s"]
        stats[f"quad_{q}_dist_cm"] = q_stats_final[q]["dist_cm"]
    return stats

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def parse_tracemap_color(value):
    if value is None: return (0,255,255)
    v=value.strip().lower()
    if v in NAMED_COLORS: return NAMED_COLORS[v]
    parts=v.split(",")
    if len(parts)==3:
        try: return (int(parts[2]),int(parts[1]),int(parts[0]))
        except ValueError: pass
    raise argparse.ArgumentTypeError(f"Invalid color '{value}'.")

def main():
    parser = argparse.ArgumentParser(
        description="Manual rat-click tracker for water-maze videos.")
    parser.add_argument("--video",              required=True,  type=str)
    parser.add_argument("--start",              default=None,   type=float)
    parser.add_argument("--end",                default=None,   type=float)
    parser.add_argument("--pool_radius_cm",     default=60,     type=float)
    parser.add_argument("--trail_s",            default=2.0,    type=float)
    parser.add_argument("--max_interp_gap",     default=0,      type=int)
    parser.add_argument("--heatmap_sigma",      default=0,      type=float)
    parser.add_argument("--pool_west",          default=None,   type=str)
    parser.add_argument("--pool_north",         default=None,   type=str)
    parser.add_argument("--pool_east",          default=None,   type=str)
    parser.add_argument("--pool_south",         default=None,   type=str)
    parser.add_argument("--platform_nw",        default=None,   type=str)
    parser.add_argument("--platform_ne",        default=None,   type=str)
    parser.add_argument("--platform_se",        default=None,   type=str)
    parser.add_argument("--platform_sw",        default=None,   type=str)
    parser.add_argument("--quadrantcross",      default=False,  action="store_true")
    parser.add_argument("--platformcross",      default=False,  action="store_true")
    parser.add_argument("--paraplatform",       default=None,   type=int, nargs="?", const=4)
    parser.add_argument("--proximity",          default=False,  action="store_true")
    parser.add_argument("--latency",            default=False,  action="store_true")
    parser.add_argument("--tracemapcolor",      default=None,   type=str)
    parser.add_argument("--ratcolor",           default=None,   type=str)
    args = parser.parse_args()

    tracemap_color  = parse_tracemap_color(args.tracemapcolor)
    rat_dot_color   = parse_tracemap_color(args.ratcolor) if args.ratcolor else (0,0,255)
    require_platform= needs_platform(args)

    cfg = {
        "pool_radius_cm": args.pool_radius_cm,
        "pool_west":      parse_point(args.pool_west)   if args.pool_west   else None,
        "pool_north":     parse_point(args.pool_north)  if args.pool_north  else None,
        "pool_east":      parse_point(args.pool_east)   if args.pool_east   else None,
        "pool_south":     parse_point(args.pool_south)  if args.pool_south  else None,
        "platform_nw":    parse_point(args.platform_nw) if args.platform_nw else None,
        "platform_ne":    parse_point(args.platform_ne) if args.platform_ne else None,
        "platform_se":    parse_point(args.platform_se) if args.platform_se else None,
        "platform_sw":    parse_point(args.platform_sw) if args.platform_sw else None,
    }

    video_path = Path(args.video)
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    cap         = cv2.VideoCapture(str(video_path))
    fps         = cap.get(cv2.CAP_PROP_FPS) or 25.0
    frame_h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frame_w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    total_frames= int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_dt    = 1.0 / fps

    trail_len   = max(1, int(round(args.trail_s * fps)))

    start_frame = int(args.start * fps) if args.start is not None else 0
    end_frame   = int(args.end   * fps) if args.end   is not None else total_frames

    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)
    ret, first_frame = cap.read()
    if not ret:
        raise RuntimeError("Could not read first frame from video.")

    # --- Calibration ---
    if pool_coords_valid(cfg):
        if not confirm_pool_from_args(first_frame, cfg):
            result = run_calibration(first_frame, require_platform=require_platform)
            if result is None: raise RuntimeError("Calibration aborted.")
            cfg.update(result)
        else:
            if require_platform:
                if platform_coords_valid(cfg):
                    if not confirm_platform_from_args(first_frame, cfg):
                        result = run_platform_calibration(first_frame)
                        if result is None: raise RuntimeError("Platform calibration aborted.")
                        cfg.update(result)
                else:
                    result = run_platform_calibration(first_frame)
                    if result is None: raise RuntimeError("Platform calibration aborted.")
                    cfg.update(result)
    else:
        result = run_calibration(first_frame, require_platform=require_platform)
        if result is None: raise RuntimeError("Calibration aborted.")
        cfg.update(result)
        if not require_platform:
            cfg.update({"platform_nw":None,"platform_ne":None,"platform_se":None,"platform_sw":None})

    west  = cfg["pool_west"];  north = cfg["pool_north"]
    east  = cfg["pool_east"];  south = cfg["pool_south"]
    r_cm  = cfg["pool_radius_cm"]

    ellipse = pool_ellipse_from_nsew(west, north, east, south)
    if ellipse is None: raise RuntimeError("Could not compute pool ellipse.")
    cx, cy, rx, ry, angle = ellipse

    raw_rx_px = math.hypot(east[0]-west[0],   east[1]-west[1])   / 2
    raw_ry_px = math.hypot(south[0]-north[0], south[1]-north[1]) / 2
    scale_x = r_cm / raw_rx_px
    scale_y = r_cm / raw_ry_px
    pool    = (cx,cy,rx,ry,angle)

    has_platform    = require_platform and platform_coords_valid(cfg)
    platform_corners= None
    if has_platform:
        platform_corners = [cfg["platform_nw"],cfg["platform_ne"],cfg["platform_se"],cfg["platform_sw"]]

    para_scale      = None; para_side_scale = None; para_corners = None
    para_time_s     = 0.0;  para_dist_cm    = 0.0;  para_exits   = 0
    prev_inside_para= False
    if args.paraplatform is not None and has_platform:
        para_scale      = args.paraplatform
        para_side_scale = math.sqrt(para_scale)
        para_corners    = scale_platform_corners(platform_corners, para_side_scale)

    latency_time_s=None; latency_dist_cm=None; latency_done=False; latency_dist_acc=0.0
    prev_inside_plat_for_latency=False
    para_latency_time_s=None; para_latency_dist_cm=None; para_latency_done=False; para_latency_dist_acc=0.0
    prev_inside_para_for_latency=False

    ts         = datetime.now().strftime("%y-%m-%d_%H-%M-%S")
    output_dir = video_path.parent
    video_out  = output_dir / f"{video_path.stem}_{ts}_manual.mp4"
    csv_path   = output_dir / f"{video_path.stem}_{ts}_manual_coordinates.csv"
    summary_path = output_dir / f"{video_path.stem}_{ts}_manual_summary.txt"
    comparison_path = output_dir / f"{video_path.stem}_{ts}_manual_comparison.txt"

    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(video_out), fourcc, fps, (frame_w, frame_h))

    # Pre-load all frames into memory (or stream on-demand if too large).
    # We need random frame access for the back-step feature.
    # Strategy: read frames lazily into a cache dict.
    frame_cache = {}

    def get_frame(idx):
        abs_idx = start_frame + idx
        if abs_idx in frame_cache:
            return frame_cache[abs_idx].copy()
        cap.set(cv2.CAP_PROP_POS_FRAMES, abs_idx)
        ret, frm = cap.read()
        if not ret:
            return None
        frame_cache[abs_idx] = frm
        return frm.copy()

    # -----------------------------------------------------------------------
    # Per-frame click state
    # -----------------------------------------------------------------------
    total_frames_to_process = end_frame - start_frame
    # records[i] = {"frame":…,"timestamp_s":…,"x":…,"y":…,"interpolated":False}
    # We build it as we go; going back overwrites.
    records = [None] * total_frames_to_process

    # click_state per frame: None = not yet visited, dict otherwise
    # Each entry: {"x":…,"y":…} or {"x":None,"y":None} for skipped

    window = "Manual Tracker  |  Click rat  |  ENTER/SPACE=confirm  S=skip  B=back  ESC=abort"
    cv2.namedWindow(window, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window, min(frame_w, 1280), min(frame_h, 720))

    click_pos = [None]   # current pending click for this frame

    def on_click(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            click_pos[0] = (x, y)
            # Immediately redraw so the user sees the dot move
            _refresh_display()

    cv2.setMouseCallback(window, on_click)

    # Running stats (accumulated as frames are confirmed forward)
    # We recompute from scratch on back-step to keep things simple.
    # Since backing up is rare, this is fine.

    def recompute_running_stats(up_to_idx):
        """Return running distance, quadrant stats, platform tracking up to (not including) up_to_idx."""
        rd_px=0.0; rd_cm=0.0
        q_st=empty_quadrant_stats()
        q_ex=empty_quadrant_exits() if args.quadrantcross else None
        plat_ex=0; prev_in_plat=False
        p_time=0.0; p_dist=0.0; p_ex=0; prev_in_para=False
        lat_t=None; lat_d=None; lat_done=False; lat_acc=0.0; prev_in_plat_lat=False
        plat_lat_t=None; plat_lat_d=None; plat_lat_done=False; plat_lat_acc=0.0; prev_in_para_lat=False
        prox_sum=0.0; prox_cnt=0
        prev=None
        for i in range(up_to_idx):
            if records[i] is None: continue
            pos_x,pos_y = records[i]["x"], records[i]["y"]
            pos = (pos_x,pos_y) if pos_x is not None else None
            ts_  = records[i]["timestamp_s"]
            if pos and prev:
                rd_px += euclidean_px(prev,pos)
                rd_cm += euclidean_cm(prev,pos,scale_x,scale_y)
                accumulate_segment(q_st,prev,pos,west,north,east,south,frame_dt,scale_x,scale_y)
                if args.quadrantcross: count_quadrant_exits(prev,pos,west,north,east,south,q_ex)
            elif pos and prev is None:
                accumulate_static(q_st,pos,west,north,east,south,frame_dt)
            # platform
            if args.platformcross and has_platform and pos:
                curr_in=point_in_platform(pos,platform_corners)
                if prev:
                    if prev_in_plat and not curr_in: plat_ex+=1
                    elif not prev_in_plat and not curr_in and segment_crosses_platform_twice(prev,pos,platform_corners): plat_ex+=1
                prev_in_plat=curr_in
            # para
            if para_corners is not None and pos:
                curr_in_para=point_in_platform(pos,para_corners)
                if prev:
                    if curr_in_para:
                        frac=0.5 if not prev_in_para else 1.0
                        p_time+=frac*frame_dt; p_dist+=euclidean_cm(prev,pos,scale_x,scale_y)*frac
                    if prev_in_para and not curr_in_para: p_ex+=1
                    elif not prev_in_para and not curr_in_para and segment_crosses_platform_twice(prev,pos,para_corners): p_ex+=1
                elif curr_in_para: p_time+=frame_dt
                prev_in_para=curr_in_para
            # latency
            if args.latency and has_platform and not lat_done and pos:
                if prev:
                    lat_acc+=euclidean_cm(prev,pos,scale_x,scale_y)
                    if segment_enters_platform(prev,pos,platform_corners,prev_in_plat_lat):
                        lat_t=ts_; lat_d=lat_acc; lat_done=True
                prev_in_plat_lat=point_in_platform(pos,platform_corners)
            if args.latency and para_corners is not None and not plat_lat_done and pos:
                if prev:
                    plat_lat_acc+=euclidean_cm(prev,pos,scale_x,scale_y)
                    if segment_enters_platform(prev,pos,para_corners,prev_in_para_lat):
                        plat_lat_t=ts_; plat_lat_d=plat_lat_acc; plat_lat_done=True
                prev_in_para_lat=point_in_platform(pos,para_corners)
            # proximity
            if args.proximity and has_platform and pos:
                pcx,pcy=platform_center(platform_corners)
                prox_sum+=euclidean_cm(pos,(pcx,pcy),scale_x,scale_y); prox_cnt+=1
            if pos: prev=pos
        return (rd_px,rd_cm,q_st,q_ex,plat_ex,p_time,p_dist,p_ex,
                lat_t,lat_d,lat_done,plat_lat_t,plat_lat_d,plat_lat_done,
                prox_sum,prox_cnt)

    current_frame_idx = 0   # 0-based index within [start_frame, end_frame)
    trail = []

    # Running stats updated incrementally (reset on back-step)
    running_dist_px=0.0; running_dist_cm=0.0
    q_stats=empty_quadrant_stats(); q_exits=empty_quadrant_exits() if args.quadrantcross else None
    platform_exits=0; prev_inside_platform=False
    para_time_live=0.0; para_dist_live=0.0; para_exits_live=0; prev_in_para_live=False
    lat_t_live=None; lat_d_live=None; lat_done_live=False; lat_acc_live=0.0; prev_in_plat_lat_live=False
    plat_lat_t_live=None; plat_lat_d_live=None; plat_lat_done_live=False; plat_lat_acc_live=0.0; prev_in_para_lat_live=False
    prox_sum_live=0.0; prox_cnt_live=0
    prev_pos_live=None

    def _refresh_display():
        """Render the current frame with overlays and show it."""
        frm = get_frame(current_frame_idx)
        if frm is None: return
        annotated = frm.copy()

        # Pool ellipse + lines
        cv2.ellipse(annotated,(cx,cy),(rx,ry),angle,0,360,(255,100,0),2)
        cv2.line(annotated,north,south,(255,100,0),1)
        cv2.line(annotated,west,east,(255,100,0),1)
        for pt in [west,north,east,south,(cx,cy)]:
            cv2.circle(annotated,pt,sc(annotated,5),(255,100,0),-1)
            cv2.circle(annotated,pt,sc(annotated,7),(255,255,255),1)

        # Platform
        if has_platform:
            pts_np=np.array(platform_corners,dtype=np.int32)
            cv2.polylines(annotated,[pts_np],True,(200,200,50),2)
            for i,(cn,_) in enumerate(PLATFORM_STEPS):
                cv2.circle(annotated,platform_corners[i],sc(annotated,4),PLATFORM_COLORS[cn],-1)
        if para_corners is not None:
            cv2.polylines(annotated,[np.array([(int(p[0]),int(p[1])) for p in para_corners],dtype=np.int32)],True,(0,180,255),2)

        # Quadrant labels
        def qlp(qa,qb):
            return (int((qa[0]+qb[0])//2*0.6+cx*0.4), int((qa[1]+qb[1])//2*0.6+cy*0.4))
        for q,lp in {"NE":qlp(north,east),"NW":qlp(north,west),"SW":qlp(south,west),"SE":qlp(south,east)}.items():
            cv2.putText(annotated,q,lp,cv2.FONT_HERSHEY_DUPLEX,sc_f(annotated,0.55),QUADRANT_COLORS[q],1,cv2.LINE_AA)

        # Trail
        for i in range(1,len(trail)):
            alpha=i/len(trail)
            cv2.line(annotated,trail[i-1],trail[i],(0,int(255*alpha),int(100*(1-alpha))),2)

        # Pending click dot
        cp = click_pos[0]
        if cp:
            cv2.circle(annotated,cp,sc(annotated,8),rat_dot_color,-1)
            cv2.circle(annotated,cp,sc(annotated,10),(255,255,255),1)

        # Previous frame's confirmed dot (grey) if available
        if current_frame_idx > 0 and records[current_frame_idx-1] is not None:
            pr = records[current_frame_idx-1]
            if pr["x"] is not None:
                cv2.circle(annotated,(int(pr["x"]),int(pr["y"])),sc(annotated,6),(150,150,150),-1)

        # HUD
        ts_cur = (start_frame + current_frame_idx) / fps
        pos_str = f"({cp[0]},{cp[1]})" if cp else "not placed"
        hud_lines = [
            (f"Frame: {current_frame_idx}/{total_frames_to_process-1}   t={ts_cur:.2f}s", (220,220,220)),
            (f"Position: {pos_str}", (220,220,220)),
            (f"Dist: {running_dist_px:.1f}px  {running_dist_cm:.1f}cm", (255,200,50)),
            (f"ENTER/SPACE=confirm  S=skip  B=back  ESC=abort", (180,180,180)),
        ]
        if args.platformcross and has_platform:
            hud_lines.append((f"Platform exits: {platform_exits}",(200,200,50)))
        if para_corners is not None:
            hud_lines.append((f"ParaPlatform T:{para_time_live:.1f}s D:{para_dist_live:.1f}cm X:{para_exits_live}",(0,180,255)))
        if args.proximity and has_platform:
            live_prox=(prox_sum_live/prox_cnt_live) if prox_cnt_live>0 else 0.0
            hud_lines.append((f"Proximity: {live_prox:.1f}cm",(180,130,255)))
        if args.latency and has_platform:
            if lat_done_live: hud_lines.append((f"Latency: {lat_t_live:.2f}s / {lat_d_live:.2f}cm",(180,255,100)))
            else:             hud_lines.append(("Latency: tracking...",(180,180,180)))
        if args.latency and para_corners is not None:
            if plat_lat_done_live: hud_lines.append((f"Para Latency: {plat_lat_t_live:.2f}s / {plat_lat_d_live:.2f}cm",(100,255,180)))
            else:                  hud_lines.append(("Para Latency: tracking...",(140,140,140)))

        line_h=sc(annotated,26); hud_pad=sc(annotated,10)
        hud_w=sc(annotated,480); hud_h=hud_pad+len(hud_lines)*line_h+hud_pad//2
        draw_transparent_banner(annotated,sc(annotated,6),sc(annotated,6),sc(annotated,6)+hud_w,sc(annotated,6)+hud_h)
        for li,(text,color) in enumerate(hud_lines):
            cv2.putText(annotated,text,(sc(annotated,16),sc(annotated,6)+hud_pad+(li+1)*line_h-sc(annotated,4)),
                        cv2.FONT_HERSHEY_DUPLEX,sc_f(annotated,0.50),color,1,cv2.LINE_AA)

        total_q_time=sum(v["time_s"]  for v in q_stats.values())
        total_q_dist=sum(v["dist_cm"] for v in q_stats.values())
        draw_leaderboard(annotated,q_stats,total_q_time,total_q_dist,quad_exits=q_exits)

        cv2.imshow(window,annotated)

    def advance_running_stats(frame_i, pos):
        """Update all running stats when frame_i is confirmed with pos (or None for skip)."""
        nonlocal running_dist_px,running_dist_cm,platform_exits,prev_inside_platform
        nonlocal para_time_live,para_dist_live,para_exits_live,prev_in_para_live
        nonlocal lat_t_live,lat_d_live,lat_done_live,lat_acc_live,prev_in_plat_lat_live
        nonlocal plat_lat_t_live,plat_lat_d_live,plat_lat_done_live,plat_lat_acc_live,prev_in_para_lat_live
        nonlocal prox_sum_live,prox_cnt_live,prev_pos_live

        ts_ = (start_frame + frame_i) / fps
        if pos and prev_pos_live:
            running_dist_px += euclidean_px(prev_pos_live,pos)
            running_dist_cm += euclidean_cm(prev_pos_live,pos,scale_x,scale_y)
            accumulate_segment(q_stats,prev_pos_live,pos,west,north,east,south,frame_dt,scale_x,scale_y)
            if args.quadrantcross: count_quadrant_exits(prev_pos_live,pos,west,north,east,south,q_exits)
        elif pos and prev_pos_live is None:
            accumulate_static(q_stats,pos,west,north,east,south,frame_dt)
        if args.platformcross and has_platform and pos:
            curr_in=point_in_platform(pos,platform_corners)
            if prev_pos_live:
                if prev_inside_platform and not curr_in: platform_exits+=1
                elif not prev_inside_platform and not curr_in and segment_crosses_platform_twice(prev_pos_live,pos,platform_corners): platform_exits+=1
            prev_inside_platform=curr_in
        if para_corners is not None and pos:
            curr_in_para=point_in_platform(pos,para_corners)
            if prev_pos_live:
                if curr_in_para:
                    frac=0.5 if not prev_in_para_live else 1.0
                    para_time_live+=frac*frame_dt; para_dist_live+=euclidean_cm(prev_pos_live,pos,scale_x,scale_y)*frac
                if prev_in_para_live and not curr_in_para: para_exits_live+=1
                elif not prev_in_para_live and not curr_in_para and segment_crosses_platform_twice(prev_pos_live,pos,para_corners): para_exits_live+=1
            elif curr_in_para: para_time_live+=frame_dt
            prev_in_para_live=curr_in_para
        if args.latency and has_platform and not lat_done_live and pos:
            if prev_pos_live:
                lat_acc_live+=euclidean_cm(prev_pos_live,pos,scale_x,scale_y)
                if segment_enters_platform(prev_pos_live,pos,platform_corners,prev_in_plat_lat_live):
                    lat_t_live=ts_; lat_d_live=lat_acc_live; lat_done_live=True
            prev_in_plat_lat_live=point_in_platform(pos,platform_corners)
        if args.latency and para_corners is not None and not plat_lat_done_live and pos:
            if prev_pos_live:
                plat_lat_acc_live+=euclidean_cm(prev_pos_live,pos,scale_x,scale_y)
                if segment_enters_platform(prev_pos_live,pos,para_corners,prev_in_para_lat_live):
                    plat_lat_t_live=ts_; plat_lat_d_live=plat_lat_acc_live; plat_lat_done_live=True
            prev_in_para_lat_live=point_in_platform(pos,para_corners)
        if args.proximity and has_platform and pos:
            pcx,pcy=platform_center(platform_corners)
            prox_sum_live+=euclidean_cm(pos,(pcx,pcy),scale_x,scale_y); prox_cnt_live+=1
        if pos: prev_pos_live=pos

    def reset_running_stats_to(frame_i):
        """Recompute all running stats from scratch up to (not including) frame_i."""
        nonlocal running_dist_px,running_dist_cm,q_stats,q_exits,platform_exits,prev_inside_platform
        nonlocal para_time_live,para_dist_live,para_exits_live,prev_in_para_live
        nonlocal lat_t_live,lat_d_live,lat_done_live,lat_acc_live,prev_in_plat_lat_live
        nonlocal plat_lat_t_live,plat_lat_d_live,plat_lat_done_live,plat_lat_acc_live,prev_in_para_lat_live
        nonlocal prox_sum_live,prox_cnt_live,prev_pos_live,trail
        (running_dist_px,running_dist_cm,q_stats,q_exits,platform_exits,
         para_time_live,para_dist_live,para_exits_live,
         lat_t_live,lat_d_live,lat_done_live,plat_lat_t_live,plat_lat_d_live,plat_lat_done_live,
         prox_sum_live,prox_cnt_live) = recompute_running_stats(frame_i)
        q_exits = q_exits if args.quadrantcross else None
        prev_inside_platform=False
        prev_in_para_live=False; prev_in_plat_lat_live=False; prev_in_para_lat_live=False
        # prev_pos_live = last confirmed pos before frame_i
        prev_pos_live=None
        for i in range(frame_i-1,-1,-1):
            if records[i] is not None and records[i]["x"] is not None:
                prev_pos_live=(records[i]["x"],records[i]["y"]); break
        # Rebuild trail
        trail=[]
        for i in range(max(0,frame_i-trail_len), frame_i):
            if records[i] is not None and records[i]["x"] is not None:
                trail.append((int(records[i]["x"]),int(records[i]["y"])))

    # Initial display
    _refresh_display()

    aborted = False
    while current_frame_idx < total_frames_to_process:
        key = cv2.waitKey(20) & 0xFF

        if key == 27:   # ESC – abort
            aborted = True
            break

        elif key in (13, 32):  # ENTER or SPACE – confirm with current click (or None)
            pos = click_pos[0]
            timestamp = (start_frame + current_frame_idx) / fps
            records[current_frame_idx] = {
                "frame":       start_frame + current_frame_idx,
                "timestamp_s": round(timestamp, 4),
                "x":           pos[0] if pos else None,
                "y":           pos[1] if pos else None,
                "interpolated":False,
            }
            advance_running_stats(current_frame_idx, pos)
            if pos:
                trail.append(pos)
                if len(trail) > trail_len: trail.pop(0)
            current_frame_idx += 1
            click_pos[0] = None
            if current_frame_idx < total_frames_to_process:
                _refresh_display()

        elif key in (ord('s'), ord('S')):  # Skip – mark as missing
            timestamp = (start_frame + current_frame_idx) / fps
            records[current_frame_idx] = {
                "frame":       start_frame + current_frame_idx,
                "timestamp_s": round(timestamp, 4),
                "x":           None,
                "y":           None,
                "interpolated":False,
            }
            advance_running_stats(current_frame_idx, None)
            current_frame_idx += 1
            click_pos[0] = None
            if current_frame_idx < total_frames_to_process:
                _refresh_display()

        elif key in (ord('b'), ord('B'), 8):  # B or Backspace – go back
            if current_frame_idx > 0:
                current_frame_idx -= 1
                # Restore previous click position from record
                prev_rec = records[current_frame_idx]
                if prev_rec and prev_rec["x"] is not None:
                    click_pos[0] = (int(prev_rec["x"]), int(prev_rec["y"]))
                else:
                    click_pos[0] = None
                records[current_frame_idx] = None  # mark as not yet finalised
                reset_running_stats_to(current_frame_idx)
                _refresh_display()

    cv2.destroyWindow(window)

    if aborted:
        cap.release(); writer.release()
        print("Aborted – no output saved.")
        return

    # -----------------------------------------------------------------------
    # Post-processing  (same pipeline as main.py)
    # -----------------------------------------------------------------------
    cap.release()

    # Fill any None records (shouldn't happen, but be safe)
    for i in range(total_frames_to_process):
        if records[i] is None:
            ts_ = (start_frame + i) / fps
            records[i] = {"frame":start_frame+i,"timestamp_s":round(ts_,4),"x":None,"y":None,"interpolated":False}

    records = interpolate_missing(records, max_gap=args.max_interp_gap)
    missing_after = sum(1 for r in records if r["x"] is None)

    total_dist_px=0.0; total_dist_cm=0.0; valid_pairs=0; prev_f=None
    q_stats_final = empty_quadrant_stats()
    for rec in records:
        if rec["x"] is not None:
            curr=(rec["x"],rec["y"])
            if prev_f is not None:
                total_dist_px += euclidean_px(prev_f,curr)
                total_dist_cm += euclidean_cm(prev_f,curr,scale_x,scale_y)
                accumulate_segment(q_stats_final,prev_f,curr,west,north,east,south,frame_dt,scale_x,scale_y)
                valid_pairs+=1
            else:
                accumulate_static(q_stats_final,curr,west,north,east,south,frame_dt)
            prev_f=curr
    total_q_time=sum(v["time_s"]  for v in q_stats_final.values())
    total_q_dist=sum(v["dist_cm"] for v in q_stats_final.values())

    # Final platform / para / latency / proximity from clean interpolated records
    plat_exits_final=0; prev_in_plat_f=False
    para_time_f=0.0; para_dist_f=0.0; para_exits_f=0; prev_in_para_f=False
    lat_t_f=None; lat_d_f=None; lat_done_f=False; lat_acc_f=0.0; prev_in_plat_lat_f=False
    plat_lat_t_f=None; plat_lat_d_f=None; plat_lat_done_f=False; plat_lat_acc_f=0.0; prev_in_para_lat_f=False
    prox_sum_f=0.0; prox_cnt_f=0
    prev2=None
    for rec in records:
        if rec["x"] is None: prev2=None; continue
        pos=(rec["x"],rec["y"]); ts_=(rec["timestamp_s"])
        if args.platformcross and has_platform:
            ci=point_in_platform(pos,platform_corners)
            if prev2:
                if prev_in_plat_f and not ci: plat_exits_final+=1
                elif not prev_in_plat_f and not ci and segment_crosses_platform_twice(prev2,pos,platform_corners): plat_exits_final+=1
            prev_in_plat_f=ci
        if para_corners is not None:
            ci=point_in_platform(pos,para_corners)
            if prev2:
                if ci:
                    frac=0.5 if not prev_in_para_f else 1.0
                    para_time_f+=frac*frame_dt; para_dist_f+=euclidean_cm(prev2,pos,scale_x,scale_y)*frac
                if prev_in_para_f and not ci: para_exits_f+=1
                elif not prev_in_para_f and not ci and segment_crosses_platform_twice(prev2,pos,para_corners): para_exits_f+=1
            elif ci: para_time_f+=frame_dt
            prev_in_para_f=ci
        if args.latency and has_platform and not lat_done_f:
            if prev2:
                lat_acc_f+=euclidean_cm(prev2,pos,scale_x,scale_y)
                if segment_enters_platform(prev2,pos,platform_corners,prev_in_plat_lat_f):
                    lat_t_f=ts_; lat_d_f=lat_acc_f; lat_done_f=True
            prev_in_plat_lat_f=point_in_platform(pos,platform_corners)
        if args.latency and para_corners is not None and not plat_lat_done_f:
            if prev2:
                plat_lat_acc_f+=euclidean_cm(prev2,pos,scale_x,scale_y)
                if segment_enters_platform(prev2,pos,para_corners,prev_in_para_lat_f):
                    plat_lat_t_f=ts_; plat_lat_d_f=plat_lat_acc_f; plat_lat_done_f=True
            prev_in_para_lat_f=point_in_platform(pos,para_corners)
        if args.proximity and has_platform:
            pcx,pcy=platform_center(platform_corners)
            prox_sum_f+=euclidean_cm(pos,(pcx,pcy),scale_x,scale_y); prox_cnt_f+=1
        prev2=pos

    proximity_avg_cm = (prox_sum_f/prox_cnt_f) if prox_cnt_f>0 else None

    # Write annotated video
    for rec in records:
        abs_idx = rec["frame"]
        frm = frame_cache.get(abs_idx)
        if frm is None:
            cap2 = cv2.VideoCapture(str(video_path))
            cap2.set(cv2.CAP_PROP_POS_FRAMES, abs_idx)
            ret2,frm=cap2.read(); cap2.release()
            if not ret2: frm=np.zeros((frame_h,frame_w,3),dtype=np.uint8)
        annotated=frm.copy()
        cv2.ellipse(annotated,(cx,cy),(rx,ry),angle,0,360,(255,100,0),2)
        cv2.line(annotated,north,south,(255,100,0),1)
        cv2.line(annotated,west,east,(255,100,0),1)
        if has_platform:
            cv2.polylines(annotated,[np.array(platform_corners,dtype=np.int32)],True,(200,200,50),2)
        if para_corners is not None:
            cv2.polylines(annotated,[np.array([(int(p[0]),int(p[1])) for p in para_corners],dtype=np.int32)],True,(0,180,255),2)
        if rec["x"] is not None:
            pos_=(int(rec["x"]),int(rec["y"]))
            col=rat_dot_color if not rec["interpolated"] else (0,210,210)
            cv2.circle(annotated,pos_,sc(annotated,8),col,-1)
            cv2.circle(annotated,pos_,sc(annotated,10),(255,255,255),1)
        writer.write(annotated)
    writer.release()

    # CSV
    with open(csv_path,"w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=["frame","timestamp_s","x","y","interpolated"])
        w.writeheader(); w.writerows(records)

    detected = sum(1 for r in records if r["x"] is not None)
    interp   = sum(1 for r in records if r["interpolated"])

    # Summary
    def fmt_pt(pt): return f"{pt[0]},{pt[1]}"
    sorted_q = sorted(QUADRANT_NAMES, key=lambda q: q_stats_final[q]["time_s"], reverse=True)
    lines=[
        f"Video           : {video_path.name}",
        f"Resolution      : {frame_w}x{frame_h}",
        f"Total frames    : {total_frames_to_process}",
        f"FPS             : {fps:.2f}",
        f"Duration (s)    : {total_frames_to_process/fps:.2f}",
        f"Start time (s)  : {args.start if args.start is not None else 0}",
        f"End time (s)    : {args.end   if args.end   is not None else round(total_frames_to_process/fps,2)}",
        "",
        f"Pool West       : {cfg['pool_west']}",
        f"Pool North      : {cfg['pool_north']}",
        f"Pool East       : {cfg['pool_east']}",
        f"Pool South      : {cfg['pool_south']}",
        "",
    ]
    if has_platform:
        lines+=[
            f"Platform NW     : {cfg['platform_nw']}",
            f"Platform NE     : {cfg['platform_ne']}",
            f"Platform SE     : {cfg['platform_se']}",
            f"Platform SW     : {cfg['platform_sw']}",
        ]
        if args.platformcross:
            lines.append(f"Platform exits  : {plat_exits_final}")
        lines.append("")
    lines+=[
        f"Detected frames : {detected}",
        f"Interpolated    : {interp}",
        f"Missing (no pos): {missing_after}",
        "",
        f"Pool radius     : {r_cm} cm",
        f"Scale X         : {scale_x:.4f} cm/px  (horizontal)",
        f"Scale Y         : {scale_y:.4f} cm/px  (vertical)",
        "",
        f"Total distance  : {total_dist_px:.2f} px",
        f"Total distance  : {total_dist_cm:.2f} cm",
        f"  (over {valid_pairs} consecutive frame pairs)",
        "",
        "-- Quadrant Analysis (sorted by time spent) --",
        f"{'Quadrant':<10} {'Time (s)':>10} {'Time (%)':>10} {'Dist (cm)':>12} {'Dist (%)':>10}",
        f"{'-'*56}",
    ]
    for q in sorted_q:
        t_s  = q_stats_final[q]["time_s"]; d_cm=q_stats_final[q]["dist_cm"]
        t_pct=(t_s /total_q_time*100) if total_q_time>0 else 0.0
        d_pct=(d_cm/total_q_dist*100) if total_q_dist>0 else 0.0
        lines.append(f"{q:<10} {t_s:>10.2f} {t_pct:>9.1f}% {d_cm:>11.2f} {d_pct:>9.1f}%")
    lines+=[f"{'-'*56}",
            f"{'TOTAL':<10} {total_q_time:>10.2f} {'100.0':>9}% {total_q_dist:>11.2f} {'100.0':>9}%",""]
    if para_corners is not None:
        t_pct=(para_time_f/total_q_time*100) if total_q_time>0 else 0.0
        d_pct=(para_dist_f/total_q_dist*100) if total_q_dist>0 else 0.0
        lines+=[
            f"-- ParaPlatform Analysis (scale: {para_scale}x area / {para_side_scale:.2f}x side) --",
            f"ParaPlatform time  : {para_time_f:.2f} s  ({t_pct:.1f}% of total)",
            f"ParaPlatform dist  : {para_dist_f:.2f} cm ({d_pct:.1f}% of total)",
            f"ParaPlatform exits : {para_exits_f}",
        ]
    if args.proximity and proximity_avg_cm is not None:
        lines+=[
            "",
            "-- Proximity to Platform --",
            f"Avg dist to center : {proximity_avg_cm:.2f} cm  (over {prox_cnt_f} frames)",
        ]
    if args.latency and has_platform:
        lines+=["","-- Latency to Platform --"]
        if lat_done_f: lines+=[f"Time to first entry: {lat_t_f:.2f} s", f"Dist to first entry: {lat_d_f:.2f} cm"]
        else:          lines+=["Rat never entered platform during session"]
    if args.latency and para_corners is not None:
        lines+=["","-- Latency to ParaPlatform --"]
        if plat_lat_done_f: lines+=[f"Time to first para entry: {plat_lat_t_f:.2f} s", f"Dist to first para entry: {plat_lat_d_f:.2f} cm"]
        else:               lines+=["Rat never entered paraplatform during session"]
    with open(summary_path,"w",encoding="utf-8") as f:
        f.write("\n".join(lines))

    heatmap_sigma = args.heatmap_sigma if args.heatmap_sigma>0 else max(5,int(round(min(frame_w,frame_h)/40)))
    tracemap(records, first_frame, output_dir, video_path, ts, color=tracemap_color)
    heatmap(records,  first_frame, output_dir, video_path, ts, sigma=heatmap_sigma)

    print("\n" + "\n".join(lines))

    # -----------------------------------------------------------------------
    # Comparison
    # -----------------------------------------------------------------------
    ref_path = find_latest_regular_summary(video_path)
    if ref_path:
        print(f"\nFound reference summary: {ref_path.name}")
        ref_stats    = parse_summary_stats(ref_path)
        manual_stats = build_manual_stats(
            total_dist_cm, plat_exits_final,
            para_time_f if para_corners is not None else None,
            para_dist_f if para_corners is not None else None,
            para_exits_f if para_corners is not None else None,
            proximity_avg_cm,
            lat_t_f    if lat_done_f       else None,
            lat_d_f    if lat_done_f       else None,
            plat_lat_t_f if plat_lat_done_f else None,
            plat_lat_d_f if plat_lat_done_f else None,
            q_stats_final,
        )
        cmp_lines = write_comparison(comparison_path, manual_stats, ref_stats, ref_path)
        print("\n" + "\n".join(cmp_lines))
        print(f"\nComparison saved → {comparison_path.name}")
    else:
        print("\nNo previous regular summary found – skipping comparison.")

    print(f"\nOutputs saved to: {output_dir}")
    print(f"  Video      : {video_out.name}")
    print(f"  CSV        : {csv_path.name}")
    print(f"  Summary    : {summary_path.name}")

if __name__ == "__main__":
    main()