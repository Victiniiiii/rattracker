import cv2

# Path to your video
video_path = "video1.mp4"

# Load the video
cap = cv2.VideoCapture(video_path)
ret, frame = cap.read()
if not ret:
    print("Error: Cannot read video")
    cap.release()
    exit()

# -----------------------------
# Mouse callback function
# -----------------------------
def click_event(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:  # Left mouse button
        print(f"Clicked coordinates: x={x}, y={y}")

# -----------------------------
# Show the frame and set callback
# -----------------------------
cv2.namedWindow("Video Frame")
cv2.setMouseCallback("Video Frame", click_event)

print("Click anywhere on the video frame to print coordinates. Press 'q' to quit.")

while True:
    # Display the first frame
    cv2.imshow("Video Frame", frame)

    # Press 'q' to exit
    if cv2.waitKey(1) & 0xFF == ord('q'):
        break

cv2.destroyAllWindows()
cap.release()