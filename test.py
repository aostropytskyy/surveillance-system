import cv2

for i in range(2):
    cap = cv2.VideoCapture(i)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print(f'Camera {i} works fine.')
        else:
            print(f'Camera {i} opened but no frame read.')
        cap.release()
    else:
        print(f'Camera {i} is not available.')
