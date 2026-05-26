import cv2
import argparse
import os

parser = argparse.ArgumentParser(description="Convert video to 4 FPS and 960x576 resolution")
parser.add_argument("--input", required=True, help="Input video path")

args = parser.parse_args()

input_path = args.input

base, ext = os.path.splitext(input_path)
output_path = f"{base}_resized.mp4"

cap = cv2.VideoCapture(input_path)

if not cap.isOpened():
    print("Error: Cannot open input video")
    exit()

original_fps = cap.get(cv2.CAP_PROP_FPS)
target_fps = 4

frame_interval = int(round(original_fps / target_fps))

width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

target_size = (960, 576)

fourcc = cv2.VideoWriter_fourcc(*"mp4v")
out = cv2.VideoWriter(output_path, fourcc, target_fps, target_size)

frame_count = 0

while True:
    ret, frame = cap.read()
    if not ret:
        break

    if frame_count % frame_interval == 0:
        if (width, height) != target_size:
            frame = cv2.resize(frame, target_size, interpolation=cv2.INTER_AREA)

        out.write(frame)

    frame_count += 1

cap.release()
out.release()

print(f"Done → {output_path}")