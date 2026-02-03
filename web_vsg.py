import os
import sys
import threading
import time
from flask import Flask, render_template, request, jsonify
from flask import Response, stream_with_context
import json
import numpy as np

app = Flask(__name__, template_folder="templates", static_folder="static")

# Ensure the example vsg wrapper can be imported
ROOT = os.path.dirname(__file__)
EXAMPLES_PY = os.path.join(ROOT, "vsg60_series", "examples", "python")
if EXAMPLES_PY not in sys.path:
    sys.path.insert(0, EXAMPLES_PY)

try:
    from vsgdevice import vsg_api as vsg
except Exception as exc:
    vsg = None
    print("Warning: could not import vsg API wrapper:", exc)

# Add DLL search path if present (matches vsg_test.py)
DLL_DIR = os.path.join(ROOT, "vsg60_series", "lib", "win", "vs2019", "x64")
if os.path.exists(DLL_DIR):
    try:
        os.add_dll_directory(DLL_DIR)
    except Exception:
        pass

# Global device state
device_handle = None
device_lock = threading.Lock()

# Sweep thread state
sweep_thread = None
sweep_stop = None
sweep_current_freq = None
sweep_lock = threading.Lock()

# IQ stream state
iq_stream_thread = None
iq_stream_stop = None
iq_latest = None
iq_lock = threading.Condition()


def open_device():
    global device_handle
    with device_lock:
        if device_handle is not None:
            return device_handle
        if vsg is None:
            raise RuntimeError("VSG API not available")
        result = vsg.vsg_open_device()
        if result.get("status", -1) != 0:
            raise RuntimeError(f"Failed to open device: {result}")
        device_handle = result["handle"]
        return device_handle


def close_device():
    global device_handle
    with device_lock:
        if device_handle is None:
            return
        try:
            vsg.vsg_abort(device_handle)
        except Exception:
            pass
        vsg.vsg_close_device(device_handle)
        device_handle = None


def stop_output():
    global device_handle
    with device_lock:
        if device_handle is None:
            return
        try:
            vsg.vsg_abort(device_handle)
            vsg.vsg_set_RF_output_state(device_handle, 0)
        except Exception:
            pass


def generate_iq(tone_freq_hz, sample_rate_hz, num_samples):
    t = np.arange(num_samples) / float(sample_rate_hz)
    i = np.cos(2 * np.pi * tone_freq_hz * t).astype(np.float32)
    q = np.sin(2 * np.pi * tone_freq_hz * t).astype(np.float32)
    # interleave I/Q
    iq = np.empty(num_samples * 2, dtype=np.float32)
    iq[0::2] = i
    iq[1::2] = q
    return iq


def iq_producer(sample_rate, tone_freq, length, interval=0.1):
    global iq_latest, iq_stream_stop
    while not iq_stream_stop.is_set():
        # generate interleaved IQ but we'll send separate lists i and q
        iq = generate_iq(tone_freq, sample_rate, length)
        # split
        i = iq[0::2].tolist()
        q = iq[1::2].tolist()
        with iq_lock:
            iq_latest = {"i": i, "q": q}
            iq_lock.notify_all()
        time.sleep(interval)


@app.route('/start_iq_stream', methods=['POST'])
def start_iq_stream():
    data = request.json or {}
    sample_rate = float(data.get('sample_rate', 1e6))
    tone_freq = float(data.get('tone_freq', 100e3))
    length = int(data.get('length', 1024))
    interval = float(data.get('interval', 0.1))
    global iq_stream_thread, iq_stream_stop
    if iq_stream_thread and iq_stream_thread.is_alive():
        return jsonify({"status": "error", "message": "IQ stream already running"}), 400
    iq_stream_stop = threading.Event()
    iq_stream_thread = threading.Thread(target=iq_producer, args=(sample_rate, tone_freq, length, interval), daemon=True)
    iq_stream_thread.start()
    return jsonify({"status": "ok"})


@app.route('/stop_iq_stream', methods=['POST'])
def stop_iq_stream():
    global iq_stream_thread, iq_stream_stop
    if iq_stream_stop is not None:
        iq_stream_stop.set()
    if iq_stream_thread is not None:
        iq_stream_thread.join(timeout=1.0)
    return jsonify({"status": "ok"})


def iq_stream_generator():
    # SSE generator that yields latest IQ whenever available
    def format_sse(data):
        return f"data: {data}\n\n"

    while True:
        with iq_lock:
            iq_lock.wait(timeout=5.0)
            data = iq_latest
        if data is None:
            # keep-alive
            yield format_sse(json.dumps({"keep": True}))
            continue
        # send i and q as JSON
        yield format_sse(json.dumps(data))


@app.route('/iq_stream')
def iq_stream():
    return Response(stream_with_context(iq_stream_generator()), mimetype='text/event-stream')


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/start", methods=["POST"])
def start():
    data = request.json or {}
    mode = data.get("mode", "cw")
    freq = float(data.get("frequency", 1.0e9))
    level = float(data.get("level", -10.0))
    sample_rate = float(data.get("sample_rate", 1e6))
    tone_freq = float(data.get("tone_freq", 100e3))
    iq_length = int(data.get("iq_length", 16384))

    try:
        dev = open_device()
        vsg.vsg_set_level(dev, level)
        # enable RF output
        vsg.vsg_set_RF_output_state(dev, 1)

        if mode == "cw":
            vsg.vsg_set_frequency(dev, freq)
            vsg.vsg_output_CW(dev)
            return jsonify({"status": "ok", "mode": "cw"})

        if mode == "iq":
            # IQ mode: generate waveform and repeat it on the device
            vsg.vsg_set_frequency(dev, freq)
            iq = generate_iq(tone_freq, sample_rate, iq_length)
            # send waveform to device and request repeat
            vsg.vsg_repeat_waveform(dev, iq, iq_length)
            return jsonify({"status": "ok", "mode": "iq", "samples": iq_length})

        if mode == "sweep":
            # start a background sweep thread that updates frequency
            bandwidth = float(data.get("bandwidth", 1e6))
            sweep_speed = float(data.get("sweep_speed", 1e6))  # Hz per second
            global sweep_thread, sweep_stop
            if sweep_thread and sweep_thread.is_alive():
                return jsonify({"status": "error", "message": "Sweep already running"}), 400

            sweep_stop = threading.Event()

            def sweep_worker(handle, center_freq, bw, speed, stop_event):
                half = bw / 2.0
                f_min = center_freq - half
                f_max = center_freq + half
                # update every 50 ms
                interval = 0.05
                step = speed * interval
                current = f_min
                direction = 1
                try:
                    vsg.vsg_set_frequency(handle, current)
                    vsg.vsg_set_RF_output_state(handle, 1)
                    vsg.vsg_output_CW(handle)
                except Exception:
                    pass
                while not stop_event.is_set():
                    try:
                        vsg.vsg_set_frequency(handle, current)
                        # update shared current frequency for UI polling
                        with sweep_lock:
                            global sweep_current_freq
                            sweep_current_freq = current
                    except Exception:
                        pass
                    time.sleep(interval)
                    current += direction * step
                    if current >= f_max:
                        current = f_max
                        direction = -1
                    elif current <= f_min:
                        current = f_min
                        direction = 1

            sweep_thread = threading.Thread(target=sweep_worker, args=(dev, freq, bandwidth, sweep_speed, sweep_stop), daemon=True)
            sweep_thread.start()
            return jsonify({"status": "ok", "mode": "sweep", "bandwidth": bandwidth, "sweep_speed": sweep_speed})

        return jsonify({"status": "error", "message": "Unknown mode"}), 400

    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route("/stop", methods=["POST"])
def stop():
    try:
        # stop sweep if running
        global sweep_thread, sweep_stop
        if sweep_stop is not None:
            sweep_stop.set()
        if sweep_thread is not None:
            sweep_thread.join(timeout=1.0)
        stop_output()
        close_device()
        return jsonify({"status": "ok"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)}), 500


@app.route('/sweep_status')
def sweep_status():
    with sweep_lock:
        f = sweep_current_freq
    return jsonify({"sweep_active": sweep_thread is not None and sweep_thread.is_alive(), "frequency": f})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
