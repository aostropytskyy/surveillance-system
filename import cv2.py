import cv2

def view_camera(camera_index=0):
    # Open the video capture with the specified camera index
    cap = cv2.VideoCapture(camera_index)

    if not cap.isOpened():
        print("Error: Could not open camera.")
        return

    print("Press 'q' to quit.")
    while True:
        ret, frame = cap.read()  # Read a frame from the camera
        if not ret:
            print("Error: Failed to grab frame.")
            break

        cv2.imshow('Camera View', frame)  # Display the frame in a window

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    # Release the capture and close the window
    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    view_camera()
