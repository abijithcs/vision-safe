import cv2
import os
import time
from datetime import datetime
from flask import Flask, Response
from ultralytics import YOLO
from plyer import notification

app = Flask(__name__)

# ---------------- YOLO ----------------
model = YOLO("yolov8n.pt")
model.to("cpu")

# ---------------- CAMERA ----------------
camera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
camera.set(cv2.CAP_PROP_FPS, 10)

# ---------------- STATES ----------------
payment = "WAITING"
status = "WAITING"
current_error = "None"
last_error = "None"
last_time = "None"
alert_msg = ""

last_ai = 0
last_phone = False
last_person = False
phone_timer = 0
cash_timer = 0
error_timer = 0

EVIDENCE = "evidence"
os.makedirs(EVIDENCE, exist_ok=True)


def generate_frames():
    global payment, status, current_error, last_error, last_time, alert_msg
    global last_ai, last_phone, last_person, phone_timer, cash_timer, error_timer

    while True:
        ok, frame = camera.read()
        if not ok:
            break

        now = time.time()

        # ---------- RUN AI EVERY 3 SECONDS ----------
        if now - last_ai > 3:
            last_ai = now
            phone = False
            person = False

            frame = cv2.convertScaleAbs(frame, alpha=1.2, beta=20)
            results = model.predict(frame, conf=0.25, device="cpu", verbose=False)

            for r in results:
                for b in r.boxes:
                    label = model.names[int(b.cls[0])]
                    x1, y1, x2, y2 = map(int, b.xyxy[0])

                    if label == "cell phone":
                        phone = True
                        cv2.rectangle(frame, (x1,y1),(x2,y2),(0,255,0),2)
                        cv2.putText(frame,"PHONE",(x1,y1-5),
                        cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

                    if label == "person":
                        person = True
                        cv2.rectangle(frame,(x1,y1),(x2,y2),(0,255,0),2)
                        cv2.putText(frame,"PERSON",(x1,y1-5),
                        cv2.FONT_HERSHEY_SIMPLEX,0.6,(0,255,0),2)

            last_phone = phone
            last_person = person

        # ---------- UPI CONFIRM ----------
        if last_phone:
            if phone_timer == 0:
                phone_timer = now
        else:
            phone_timer = 0

        upi_confirmed = phone_timer != 0 and (now - phone_timer) > 2

        # ---------- PAYMENT MODE ----------
        if upi_confirmed:
            payment = "UPI"
            cash_timer = 0

        elif last_person:
            if cash_timer == 0:
                cash_timer = now
            payment = "CARD" if (now - cash_timer) > 4 else "CASH"

        else:
            payment = "UNKNOWN"
            cash_timer = 0

        # ---------- FRAUD LOGIC ----------
        fraud = False
        reason = "NORMAL"
        alert_msg = ""

        if payment == "UNKNOWN":
            fraud = True
            reason = "NO PAYMENT DETECTED"

        elif payment == "UPI" and not upi_confirmed:
            fraud = True
            reason = "UPI NOT CONFIRMED"

        elif payment == "CASH" and not last_person:
            fraud = True
            reason = "CASH ERROR"

        # ---------- ALERT + SCREENSHOT ----------
        if fraud:
            notification.notify(
                title="🚨 VisionSafe Alert",
                message=reason,
                timeout=5
            )

            status = "ERROR"
            current_error = reason
            last_error = reason
            alert_msg = f"🚨 {reason}"
            error_timer = now

            cv2.rectangle(frame,(40,40),(600,420),(0,0,255),2)
            cv2.putText(frame,"ERROR",(50,35),
            cv2.FONT_HERSHEY_SIMPLEX,0.9,(0,0,255),2)

            cv2.putText(frame,reason,(50,395),
            cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)

            t = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            last_time = t
            cv2.imwrite(f"{EVIDENCE}/error_{t}.jpg", frame)

        else:
            if now - error_timer > 5:
                status = "NORMAL"
                current_error = "None"
                alert_msg = ""

            cv2.rectangle(frame,(40,40),(600,420),(0,255,0),2)
            cv2.putText(frame,"NORMAL",(50,35),
            cv2.FONT_HERSHEY_SIMPLEX,0.9,(0,255,0),2)

        _, buf = cv2.imencode(".jpg", frame)
        yield (b"--frame\r\nContent-Type:image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")


@app.route("/")
def index():
    return f"""
<html>
<body style="background:#020617;color:white;font-family:Segoe UI">

<h2 style="color:#38bdf8;text-align:center">VisionSafe – AI Cyber Transaction Monitor</h2>

<div style="display:flex;gap:20px;padding:20px">

<div style="border:1px solid #0ea5e9;padding:15px;width:300px">
<p>Payment: {payment}</p>
<p>Status: {status}</p>
<p>Error: {current_error}</p>
<p style="color:red">{alert_msg}</p>
</div>

<img src="/video">

<div style="border:1px solid #22c55e;padding:15px;width:250px">
<h4 style="color:#22c55e">Cyber Security</h4>
<p style="color:red">Threat Monitor: ACTIVE</p>
<p style="color:#22c55e">Network: SECURE</p>
<p style="color:#38bdf8">AI Engine: RUNNING</p>
<p style="color:#facc15">Fraud Layer: ENABLED</p>
<p style="color:#c084fc">Evidence Logger: ONLINE</p>
</div>

</div>

<footer style="text-align:center;color:#64748b">
Developed by Abijith C S • VisionSafe © 2026
</footer>

</body>
</html>
"""


@app.route("/video")
def video():
    return Response(generate_frames(),
    mimetype="multipart/x-mixed-replace; boundary=frame")


if __name__ == "__main__":
    print("VisionSafe Started")
    app.run(host="127.0.0.1", port=5000)