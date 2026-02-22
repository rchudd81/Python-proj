
import ctypes
import os
from ctypes import byref, c_int
from flask import Flask, render_template, request, redirect, url_for, jsonify, session
import numpy as np
import threading
import time
import scipy.signal
from flask_socketio import SocketIO

app = Flask(__name__)
app.secret_key = 'replace_this_with_a_random_secret_key'  # Needed for session
socketio = SocketIO(app, async_mode='eventlet')

dll_dir = r"C:\Users\Richard\Python-proj\vsg60_series\lib\win\vs2019\x64"
vsg_status = {'dll_loaded': False, 'device_opened': False, 'error': '', 'handle': c_int(-1)}
if os.path.exists(dll_dir):
    try:
        os.add_dll_directory(dll_dir)
        os.environ['PATH'] = dll_dir + os.pathsep + os.environ.get('PATH', '')
        vsg = ctypes.cdll.LoadLibrary("vsg_api.dll")
        vsg_status['dll_loaded'] = True
        status = vsg.vsgOpenDevice(byref(vsg_status['handle']))
        if status == 0:
            vsg_status['device_opened'] = True
        else:
            vsg_status['error'] = f"Could not open device. Error code: {status}"
    except Exception as e:
        vsg_status['error'] = f"Failed to load DLL or open device: {e}"
else:
    vsg_status['error'] = f"DLL path not found: {dll_dir}"

# --- Signal generation helpers ---
def generate_cw(freq_offset, gain_dbm, sample_rate, num_samples):
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * freq_offset * t)

def generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, freq_offset, gain_dbm):
    if sps < 8:
        sps = 8
    if mod_type == 'bpsk':
        symbols = np.random.choice([1, -1], size=num_symbols)
    elif mod_type == 'qpsk':
        bits = np.random.randint(0, 4, num_symbols)
        symbols = np.exp(1j * (np.pi/4 + np.pi/2 * bits))
    elif mod_type == '8psk':
        bits = np.random.randint(0, 8, num_symbols)
        symbols = np.exp(1j * (np.pi/8 + np.pi/4 * bits))
    else:
        raise ValueError('Unsupported PSK type')
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = symbols
    num_taps = 41 * sps
    t = np.arange(-num_taps//2, num_taps//2 + 1) / sps
    pi = np.pi
    with np.errstate(divide='ignore', invalid='ignore'):
        rrc = np.sinc(t) * np.cos(pi * 0.35 * t) / (1 - (2 * 0.35 * t)**2)
    rrc[t == 0] = 1.0 - 0.35 + 4 * 0.35 / pi
    t2 = np.abs(t) == 1/(4*0.35)
    rrc[t2] = (0.35/np.sqrt(2)) * ((1 + 2/pi) * np.sin(pi/(4*0.35)) + (1 - 2/pi) * np.cos(pi/(4*0.35)))
    rrc = rrc / np.sqrt(np.sum(rrc**2))
    shaped = np.convolve(upsampled, rrc, mode='same')
    shaped /= np.max(np.abs(shaped))
    shaped *= 10**(gain_dbm/20)
    t = np.arange(len(shaped)) / sample_rate
    shaped *= np.exp(2j * np.pi * freq_offset * t)
    return shaped


# --- Single signal storage ---
current_signal = None  # dict with all params, plus 'iq', 'sample_rate', 'duration'


@app.route('/', methods=['GET', 'POST'])
def index():
    global current_signal
    msg = ''
    freq = session.get('frequency_hz', 100000000.0)
    sr = session.get('sample_rate', 1000000.0)
    dur = session.get('duration', 0.01)
    if request.method == 'POST':
        if request.form.get('update_freq_sr') == '1':
            freq = float(request.form.get('frequency_hz', freq))
            sr = float(request.form.get('sample_rate', sr))
            dur = float(request.form.get('duration', dur))
            session['frequency_hz'] = freq
            session['sample_rate'] = sr
            session['duration'] = dur
            msg = 'Defaults updated.'
        elif request.form.get('add_signal_btn') == '1':
            sig_type = request.form.get('sig_type', 'cw')
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            sample_rate = float(request.form.get('sample_rate', sr))
            duration = float(request.form.get('duration', dur))
            num_samples = int(sample_rate * duration)
            min_samples = 2048
            if num_samples < min_samples:
                num_samples = min_samples
                duration = num_samples / sample_rate
            if sig_type == 'cw':
                iq = generate_cw(freq_offset, gain_dbm, sample_rate, num_samples)
                sig = {'type': 'cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'sample_rate': sample_rate, 'duration': duration, 'iq': iq}
            elif sig_type == 'psk':
                mod_type = request.form.get('mod_type', 'qpsk')
                rolloff = float(request.form.get('rolloff', 0.35))
                symrate = float(request.form.get('symrate', 1e6))
                sps = int(sample_rate / symrate)
                if sps < 8:
                    sps = 8
                num_symbols = int(num_samples / sps)
                iq = generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, freq_offset, gain_dbm)
                if len(iq) > num_samples:
                    iq = iq[:num_samples]
                elif len(iq) < num_samples:
                    iq = np.pad(iq, (0, num_samples - len(iq)))
                sig = {'type': 'psk', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'mod_type': mod_type, 'rolloff': rolloff, 'symrate': symrate, 'sample_rate': sample_rate, 'duration': duration, 'iq': iq}
            else:
                msg = 'Unsupported signal type.'
                return redirect(url_for('index'))
            current_signal = sig
            msg = f'{sig_type.upper()} signal generated.'
            # Automatically push to IQ viewer
            try:
                import requests
                requests.post('http://localhost:5000/push_signal_to_viewer', json={
                    'type': sig['type'],
                    'sample_rate': sig['sample_rate'],
                    'duration': sig['duration'],
                    'i': np.real(sig['iq']).tolist(),
                    'q': np.imag(sig['iq']).tolist()
                })
            except Exception as e:
                print('Could not push signal to viewer:', e)
        if 'frequency_hz' in request.form:
            session['frequency_hz'] = float(request.form.get('frequency_hz', freq))
        if 'sample_rate' in request.form:
            session['sample_rate'] = float(request.form.get('sample_rate', sr))
        if 'duration' in request.form:
            session['duration'] = float(request.form.get('duration', dur))
        return redirect(url_for('index'))
    return render_template('index_v4.html', signal=current_signal, msg=msg, frequency_hz=freq, sample_rate=sr, duration=dur)


@app.route('/get_signal')
def get_signal():
    global current_signal
    if current_signal is not None:
        iq = current_signal['iq']
        return jsonify({
            'status': 'ok',
            'type': current_signal['type'],
            'sample_rate': current_signal['sample_rate'],
            'duration': current_signal['duration'],
            'i': np.real(iq).tolist(),
            'q': np.imag(iq).tolist()
        })
    return jsonify({'status': 'error', 'message': 'No signal generated'})



# Remove signal_list endpoint (no longer needed)

# --- Serve IQ Viewer v4 HTML ---
@app.route('/iq-viewer_v4.html')
def iq_viewer_v4():
    return app.send_static_file('iq-viewer_v4.html')

if __name__ == '__main__':
    socketio.run(app, debug=True)
