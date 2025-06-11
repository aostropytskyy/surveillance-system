import cv2
import tkinter as tk
from tkinter import ttk
from threading import Thread

class CameraApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Camera Selector")

        self.selected_camera = tk.IntVar()
        self.camera_list = self.scan_cameras()

        ttk.Label(root, text="Select Camera:").pack(pady=5)

        self.combo = ttk.Combobox(root, values=self.camera_list, state="readonly")
        self.combo.pack(pady=5)
        if self.camera_list:
            self.combo.current(0)

        self.start_button = ttk.Button(root, text="Start Camera", command=self.start_camera_thread)
        self.start_button.pack(pady=10)

    def scan_cameras(self, max_index=5):
        available = []
        for i in range(max_index):
            cap = cv2.VideoCapture(i)
            if cap.read()[0]:
                available.append(f"Camera {i}")
                cap.release()
        return available

    def start_camera_thread(self):
        Thread(target=self.open_camera).start()

    def open_camera(self):
        index = int(self.combo.get().split()[-1])
        cap = cv2.VideoCapture(index)
        if not cap.isOpened():
            print("Error: Cannot open camera.")
            return

        cv2.namedWindow("Camera Feed", cv2.WINDOW_NORMAL)
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            cv2.imshow("Camera Feed", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()

if __name__ == "__main__":
    root = tk.Tk()
    app = CameraApp(root)
    root.mainloop()
