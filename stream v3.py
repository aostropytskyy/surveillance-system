import os
import time
import cv2
import tkinter as tk
from tkinter import ttk
from threading import Thread
from flask import Flask, Response
from flask_httpauth import HTTPBasicAuth
from werkzeug.security import generate_password_hash, check_password_hash

# Flask setup
app = Flask(__name__)
auth = HTTPBasicAuth()
users = {"admin": generate_password_hash("password123")}

@auth.verify_password
def verify_password(username, password):
    return username in users and check_password_hash(users.get(username), password)

# Globals
cameras = []
streaming_flags = []
recording_flags = []
recording_writers = []
RECORDINGS_FOLDER = "recordings"

# Create recordings folder if missing
if not os.path.exists(RECORDINGS_FOLDER):
    os.makedirs(RECORDINGS_FOLDER)

def add_timestamp(frame):
    font = cv2.FONT_HERSHEY_SIMPLEX
    timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
    cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), font, 0.6, (0, 255, 0), 2)
    return frame

# MJPEG stream generator with timestamp on preview only
def generate_frames(cam_index):
    cap = cameras[cam_index]
    while streaming_flags[cam_index]:
        success, frame = cap.read()
        if not success:
            break

        # Add timestamp overlay to frame (for preview and recording)
        font = cv2.FONT_HERSHEY_SIMPLEX
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        cv2.putText(frame, timestamp, (10, frame.shape[0] - 10), font, 0.6, (0, 255, 0), 2)

        preview_frame = frame.copy()  # for preview streaming

        # Recording raw frames with timestamp overlay
        if recording_flags[cam_index]:
            if recording_writers[cam_index] is None:
                w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                fourcc = cv2.VideoWriter_fourcc(*'MJPG')
                timestamp_str = time.strftime('%Y%m%d_%H%M%S')
                filename = os.path.join(RECORDINGS_FOLDER, f'recording_cam{cam_index}_{timestamp_str}.avi')
                recording_writers[cam_index] = cv2.VideoWriter(filename, fourcc, 20.0, (w, h))
                print(f"Started recording camera {cam_index} to {filename}")
            recording_writers[cam_index].write(frame)
        else:
            if recording_writers[cam_index] is not None:
                recording_writers[cam_index].release()
                recording_writers[cam_index] = None
                print(f"Stopped recording camera {cam_index}")

        _, buffer = cv2.imencode('.jpg', preview_frame)
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')


# Snapshot preview route (with timestamp)
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
    html = "<h1>Camera Previews</h1><div style='display:flex;flex-wrap:wrap;'>"
    for i in range(len(cameras)):
        html += f"""
            <div style="margin:10px; text-align:center;">
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
        }, 500);  // Refresh every 500ms (~2fps)
    </script>
    """
    return html

# Stream page per camera
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

# MJPEG stream route
@app.route('/stream_feed/<int:cam_index>')
@auth.login_required
def stream_feed(cam_index):
    if cam_index >= len(cameras):
        return "Camera not found", 404
    return Response(generate_frames(cam_index), mimetype='multipart/x-mixed-replace; boundary=frame')

# Shutdown server route
@app.route('/shutdown', methods=['POST'])
def shutdown():
    func = flask.request.environ.get('werkzeug.server.shutdown')
    if func:
        func()
    return 'Shutting down...'

# Scan available cameras
def scan_all_cameras(max_index=5):
    found = []
    for i in range(max_index):
        cap = cv2.VideoCapture(i)
        if cap.read()[0]:
            found.append(i)
        cap.release()
    return found

# GUI Application
class StreamApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Multi-Camera Streamer")

        self.start_btn = ttk.Button(root, text="Start Streaming", command=self.start_stream)
        self.start_btn.pack(pady=5)

        self.stop_btn = ttk.Button(root, text="Stop Streaming", command=self.stop_stream, state='disabled')
        self.stop_btn.pack(pady=5)

        self.record_btn = ttk.Button(root, text="Start Recording", command=self.start_recording, state='disabled')
        self.record_btn.pack(pady=5)

        self.stop_record_btn = ttk.Button(root, text="Stop Recording", command=self.stop_recording, state='disabled')
        self.stop_record_btn.pack(pady=5)

        self.status = tk.Label(root, text="Ready.")
        self.status.pack(pady=10)

    def start_stream(self):
        global cameras, streaming_flags, recording_flags, recording_writers

        indices = scan_all_cameras()
        if not indices:
            self.status.config(text="No cameras found.")
            return

        cameras.clear()
        streaming_flags.clear()
        recording_flags.clear()
        recording_writers.clear()

        for idx in indices:
            cap = cv2.VideoCapture(idx)
            cameras.append(cap)
            streaming_flags.append(True)
            recording_flags.append(False)
            recording_writers.append(None)

        thread = Thread(target=lambda: app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False))
        thread.daemon = True
        thread.start()

        self.start_btn.config(state='disabled')
        self.stop_btn.config(state='normal')
        self.record_btn.config(state='normal')
        self.status.config(text=f"Streaming. Open http://localhost:5000 (admin/password123)")

    def stop_stream(self):
        global streaming_flags, recording_flags, recording_writers

        for i in range(len(streaming_flags)):
            streaming_flags[i] = False
            recording_flags[i] = False
            if recording_writers[i] is not None:
                recording_writers[i].release()
                recording_writers[i] = None

        # Release cameras
        for cap in cameras:
            cap.release()

        self.start_btn.config(state='normal')
        self.stop_btn.config(state='disabled')
        self.record_btn.config(state='disabled')
        self.stop_record_btn.config(state='disabled')
        self.status.config(text="Stopped streaming. Recordings saved.")

    def start_recording(self):
        global recording_flags
        for i in range(len(recording_flags)):
            recording_flags[i] = True

        self.record_btn.config(state='disabled')
        self.stop_record_btn.config(state='normal')
        self.status.config(text="Recording started for all cameras.")

    def stop_recording(self):
        global recording_flags
        for i in range(len(recording_flags)):
            recording_flags[i] = False

        self.record_btn.config(state='normal')
        self.stop_record_btn.config(state='disabled')
        self.status.config(text="Recording stopped for all cameras.")

if __name__ == "__main__":
    root = tk.Tk()
    app_gui = StreamApp(root)
    root.mainloop()
