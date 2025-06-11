import cv2
import tkinter as tk
from tkinter import ttk
from threading import Thread
from flask import Flask, Response, request
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash
import time
import requests

# Flask setup
app = Flask(__name__)
auth = HTTPBasicAuth()
users = {"admin": generate_password_hash("password123")}

@auth.verify_password
def verify_password(username, password):
    return username in users and check_password_hash(users.get(username), password)

# Globals
cameras = []
video_writers = []
streaming_flags = []

# Generate MJPEG stream with timestamp
def generate_frames(cam_index):
    cap = cameras[cam_index]
    out = video_writers[cam_index]
    font = cv2.FONT_HERSHEY_SIMPLEX

    while streaming_flags[cam_index]:
        success, frame = cap.read()
        if not success:
            break
        timestamp = time.strftime('%d-%m-%Y %H:%M:%S')
        cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), font, 0.6, (0, 255, 0), 2)
        out.write(frame)
        _, buffer = cv2.imencode('.jpg', frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
    out.release()
    cap.release()

# Snapshot preview
@app.route('/snapshot_<int:cam_index>')
@auth.login_required
def snapshot(cam_index):
    if cam_index >= len(cameras):
        return "Camera not found", 404
    cap = cameras[cam_index]
    success, frame = cap.read()
    if not success:
        return "Failed to capture frame", 500
    frame = add_timestamp(frame)
    _, buffer = cv2.imencode('.jpg', frame)
    return Response(buffer.tobytes(), mimetype='image/jpeg')

# Home page with all previews
@app.route('/')
@auth.login_required
def index():
    html = "<h1>Active Camera Streams</h1><div style='display:flex;flex-wrap:wrap;'>"
    for i in range(len(cameras)):
        html += f"""
            <div style="margin:10px;text-align:center;">
                <p>Camera {i}</p>
                <a href="/video_feed/{i}">
                    <img src="/snapshot_{i}?t={time.time()}" width="320" height="240" style="border:1px solid #ccc;" />
                </a>
            </div>
        """
    html += """</div>
        <script>
setInterval(() => {
    document.querySelectorAll('img').forEach(img => {
        const url = new URL(img.src);
        url.searchParams.set('t', Date.now());
        img.src = url.href;
    });
}, 1000);  // ~10 fps preview

        </script>
    """
    return html

# Dynamic stream route
@app.route('/video_feed/<int:cam_index>')
@auth.login_required
def stream_page(cam_index):
    if cam_index >= len(cameras):
        return "Camera not found", 404
    return f"""
        <html>
        <head><title>Camera {cam_index}</title></head>
        <body style="background:#000; color:white; text-align:center;">
            <h2>Camera {cam_index}</h2>
            <a href="/" style="color:#0f0; font-size:18px;">← Back to Cameras</a><br><br>
            <img src="/stream_feed/{cam_index}" style="border:2px solid #ccc; max-width:90%;">
        </body>
        </html>
    """

@app.route('/stream_feed/<int:cam_index>')
@auth.login_required
def stream_feed(cam_index):
    if cam_index >= len(cameras):
        return "Camera not found", 404
    return Response(generate_frames(cam_index), mimetype='multipart/x-mixed-replace; boundary=frame')
def add_timestamp(frame):
    font = cv2.FONT_HERSHEY_SIMPLEX
    timestamp = time.strftime('%d-%m-%Y %H:%M:%S')
    cv2.putText(frame, timestamp, (10, frame.shape[0] - 10),
                font, 0.6, (0, 255, 0), 2)
    return frame

# Shutdown
@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Shutting down...'

# Camera scanner
def scan_all_cameras(max_index=5):
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.read()[0]:
            found.append(i)
        cap.release()
    return found

# GUI
class StreamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Camera Streamer")

        self.start_btn = ttk.Button(root, text="Start Streaming", command=self.start_stream)
        self.start_btn.pack(pady=5)

        self.stop_btn = ttk.Button(root, text="Stop Streaming", command=self.stop_stream, state='disabled')
        self.stop_btn.pack(pady=5)

        self.status = tk.Label(root, text="Ready.")
        self.status.pack(pady=10)

    def start_stream(self):
        global cameras, video_writers, streaming_flags

        indices = scan_all_cameras()
        if not indices:
            self.status.config(text="No cameras found.")
            return

        cameras.clear()
        video_writers.clear()
        streaming_flags.clear()

        for idx in indices:
            cap = cv2.VideoCapture(idx)
            cameras.append(cap)
            w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            fourcc = cv2.VideoWriter_fourcc(*'MJPG')
            writer = cv2.VideoWriter(f'recording_{idx}.avi', fourcc, 20.0, (w, h))
            video_writers.append(writer)
            streaming_flags.append(True)

        thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False))
        thread.daemon = True
        thread.start()

        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.status.config(text="Streaming. Open http://localhost:5000 (admin/password123)")

    def stop_stream(self):
        for i in range(len(streaming_flags)):
            streaming_flags[i] = False

        time.sleep(1)

        for cap in cameras:
            cap.release()
        for writer in video_writers:
            writer.release()

        try:
            requests.post("http://127.0.0.1:5000/shutdown")
        except:
            pass

        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.status.config(text="Stopped. Recordings saved.")

# Launch GUI
if __name__ == "__main__":
    root = tk.Tk()
    app_gui = StreamApp(root)
    root.mainloop()
