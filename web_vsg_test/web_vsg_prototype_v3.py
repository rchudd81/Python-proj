import ctypes
import os
from ctypes import byref, c_int, c_double
from flask import Flask, render_template, render_template_string, request, redirect, url_for, jsonify, send_file
import numpy as np
import threading
import time
import random
import scipy.signal
from flask_socketio import SocketIO, emit

app = Flask(__name__)
vsg_status = {'dll_loaded': False, 'device_opened': False, 'error': '', 'handle': c_int(-1)}
dll_dir = r"C:\Users\Richard\Python-proj\vsg60_series\lib\win\vs2019\x64"
if not os.path.exists(dll_dir):
    vsg_status['error'] = f"DLL path not found: {dll_dir}"
else:
    try:
        os.add_dll_directory(dll_dir)
        # Add DLL dir to PATH for dependency resolution (helps on some systems)
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

# After device open attempt, print connection status
if vsg_status['dll_loaded']:
    if vsg_status['device_opened']:
        print("[VSG] Device connection: SUCCESS (DLL loaded, device opened)")
    else:
        print(f"[VSG] Device connection: FAIL (DLL loaded, device NOT opened) - {vsg_status['error']}")
else:
    print(f"[VSG] Device connection: FAIL (DLL NOT loaded) - {vsg_status['error']}")

# Move update_interval to a mutable object so changes are reflected in the thread
update_config = {'interval': 0.5}

socketio = SocketIO(app, async_mode='eventlet')

def generate_cw(freq_offset, gain_dbm, sample_rate, num_samples):
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * freq_offset * t)

def generate_sweeping_cw(freq_offset, gain_dbm, sample_rate, sweep_bw, sweep_speed):
    # sweep_speed: Hz/s (rate of frequency change)
    # sweep_bw: total sweep bandwidth (Hz)
    # sweep_period = time to sweep full bandwidth (seconds)
    sweep_period = sweep_bw / sweep_speed
    num_samples = int(sample_rate * sweep_period)
    t = np.arange(num_samples) / sample_rate
    try:
        from scipy.signal import sawtooth
    except ImportError:
        sawtooth = lambda x: 2 * (x / (2 * np.pi) - np.floor(0.5 + x / (2 * np.pi)))
    sweep = sweep_bw/2 * sawtooth(2 * np.pi * t / sweep_period)
    inst_freq = freq_offset + sweep
    phase = 2 * np.pi * np.cumsum(inst_freq) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(1j * phase)

def rrc_filter(num_taps, beta, sps):
    t = np.arange(-num_taps//2, num_taps//2 + 1)
    t = t / sps
    pi = np.pi
    with np.errstate(divide='ignore', invalid='ignore'):
        h = np.sinc(t) * np.cos(pi * beta * t) / (1 - (2 * beta * t)**2)
    h[t == 0] = 1.0 - beta + 4 * beta / pi
    t2 = np.abs(t) == 1/(4*beta)
    h[t2] = (beta/np.sqrt(2)) * ((1 + 2/pi) * np.sin(pi/(4*beta)) + (1 - 2/pi) * np.cos(pi/(4*beta)))
    h = h / np.sqrt(np.sum(h**2))
    return h

def generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, freq_offset, gain_dbm):
    # Ensure sps is at least 8 for better image rejection
    if sps < 8:
        print(f"[PSK] sps too low ({sps}), setting to 8 for better image rejection.")
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
    num_taps = 41 * sps  # More taps for better filtering
    rrc = rrc_filter(num_taps, rolloff, sps)
    print(f"[PSK] sps={sps}, num_taps={num_taps}, rrc sum={np.sum(rrc):.4f}, max={np.max(rrc):.4f}, min={np.min(rrc):.4f}")
    shaped = np.convolve(upsampled, rrc, mode='same')
    shaped /= np.max(np.abs(shaped))
    t = np.arange(len(shaped)) / sample_rate
    shaped *= np.exp(2j * np.pi * freq_offset * t)
    shaped *= 10**(gain_dbm/20)
    return shaped

def generate_composite_iq(signals, sample_rate, duration=None):
    # If duration is None, for sweeping_cw, use one sweep period
    if duration is None:
        for sig in signals:
            if sig['type'] == 'sweeping_cw':
                sweep_bw = sig.get('sweep_bw', 1e6)
                sweep_speed = sig.get('sweep_speed', 100)
                sweep_period = sweep_bw / sweep_speed
                duration = sweep_period
                break
        if duration is None:
            duration = 0.01
    num_samples = int(sample_rate * duration)
    iq = np.zeros(num_samples, dtype=np.complex64)
    for sig in signals:
        if not sig.get('enabled', True):
            continue
        if sig['type'] == 'cw':
            iq += generate_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples)
        elif sig['type'] == 'sweeping_cw':
            sweep_bw = sig.get('sweep_bw', 1e6)
            sweep_speed = sig.get('sweep_speed', 100)
            sweep_iq = generate_sweeping_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, sweep_bw, sweep_speed)
            if len(sweep_iq) > num_samples:
                sweep_iq = sweep_iq[:num_samples]
            elif len(sweep_iq) < num_samples:
                sweep_iq = np.pad(sweep_iq, (0, num_samples - len(sweep_iq)))
            iq += sweep_iq
        elif sig['type'] == 'psk':
            mod_type = sig.get('mod_type', 'qpsk')
            rolloff = sig.get('rolloff', 0.35)
            symrate = sig.get('symrate', 1e6)
            sps = int(sample_rate / symrate)
            if sps < 8:
                sps = 8
            num_symbols = int(num_samples / sps)
            psk = generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, sig['freq_offset'], sig['gain_dbm'])
            if len(psk) > num_samples:
                psk = psk[:num_samples]
            elif len(psk) < num_samples:
                psk = np.pad(psk, (0, num_samples - len(psk)))
            iq += psk
    if np.max(np.abs(iq)) > 0:
        iq /= np.max(np.abs(iq))
    return iq

data = {
    'frequency_hz': 1.23e9,
    'level_dbm': -60.0,
    'sample_rate': 10e6,
    'signals': []
}

spectrum_data = {'freqs': [], 'power': []}
update_interval = 0.5

def spectrum_update_loop():
    global spectrum_data
    while True:
        iq = generate_composite_iq(data['signals'], data['sample_rate'])
        spectrum = np.fft.fftshift(np.fft.fft(iq))
        freqs = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0/data['sample_rate']))
        power = 20 * np.log10(np.abs(spectrum) + 1e-12)
        spectrum_data['freqs'] = (freqs/1e6).tolist()
        spectrum_data['power'] = power.tolist()
        socketio.emit('spectrum_update', spectrum_data)
        time.sleep(update_config['interval'])

threading.Thread(target=spectrum_update_loop, daemon=True).start()

@app.route('/', methods=['GET', 'POST'])
def index():
    msg = ''
    if request.method == 'POST':
        if request.form.get('add_signal_btn') == '1':
            sig_type = request.form.get('sig_type', 'cw')
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            if sig_type == 'cw':
                data['signals'].append({'type': 'cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'enabled': True})
                msg = 'CW signal added.'
            elif sig_type == 'sweeping_cw':
                sweep_bw = float(request.form.get('sweep_bw', 1e6))
                sweep_speed = float(request.form.get('sweep_speed', 100))
                num_slots = int(request.form.get('num_slots', 8))
                data['signals'].append({'type': 'sweeping_cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'sweep_bw': sweep_bw, 'sweep_speed': sweep_speed, 'num_slots': num_slots, 'enabled': True})
                msg = 'Sweeping CW signal added.'
            elif sig_type == 'psk':
                mod_type = request.form.get('mod_type', 'qpsk')
                rolloff = float(request.form.get('rolloff', 0.35))
                symrate = float(request.form.get('symrate', 1e6))
                data['signals'].append({'type': 'psk', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'mod_type': mod_type, 'rolloff': rolloff, 'symrate': symrate, 'enabled': True})
                msg = 'PSK signal added.'
            return redirect(url_for('index'))
        if request.form.get('update_freq_sr') == '1':
            try:
                data['frequency_hz'] = float(request.form.get('frequency_hz', data['frequency_hz']))
                data['sample_rate'] = float(request.form.get('sample_rate', data['sample_rate']))
                msg = 'Frequency and sample rate updated.'
            except Exception:
                msg = 'Invalid frequency or sample rate.'
            return redirect(url_for('index'))
        if request.form.get('set_refresh_rate') == '1':
            try:
                update_config['interval'] = float(request.form.get('refresh_rate', update_config['interval']))
                msg = f'Refresh rate set to {update_config["interval"]} s.'
            except Exception:
                msg = 'Invalid refresh rate.'
            return redirect(url_for('index'))
        for i, sig in enumerate(data['signals']):
            if request.form.get(f'delete_{i}'):
                data['signals'].pop(i)
                msg = f"Signal {i+1} deleted."
                return redirect(url_for('index'))
            if request.form.get(f'toggle_{i}'):
                sig['enabled'] = not sig.get('enabled', True)
                msg = f"Signal {i+1} toggled."
                return redirect(url_for('index'))
    return render_template(
        'index.html',
        signals=data['signals'],
        frequency_hz=data['frequency_hz'],
        sample_rate=data['sample_rate'],
        msg=msg,
        interval=update_config['interval'],
        vsg_status=vsg_status
    )

@app.route('/spectrum_json')
def spectrum_json():
    return jsonify(spectrum_data)

@app.route('/preview_signal', methods=['GET'])
def preview_signal():
    try:
        sample_rate = data.get('sample_rate', 1e6)
        # For sweeping_cw, generate one sweep cycle
        iq = generate_composite_iq(data['signals'], sample_rate, duration=None)
        i = np.real(iq).tolist()
        q = np.imag(iq).tolist()
        return jsonify({
            'status': 'ok',
            'i': i,
            'q': q,
            'sample_rate': sample_rate,
            'num_samples': len(iq),
            'center_freq': data.get('frequency_hz', 0)
        })
    except Exception as e:
        import traceback
        print('Error in /preview_signal:', e)
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/iq-viewer_v3.html')
def serve_iq_viewer():
    return send_file('../iq-viewer_v3.html')

@app.route('/iq_purity_check', methods=['GET'])
def iq_purity_check():
    sample_rate = data.get('sample_rate', 1e6)
    iq = generate_composite_iq(data['signals'], sample_rate, duration=None)
    spectrum = np.fft.fft(iq)
    N = len(spectrum)
    pos = np.sum(np.abs(spectrum[N//2:]))
    neg = np.sum(np.abs(spectrum[:N//2]))
    image_rejection_db = float(10 * np.log10(pos / (neg + 1e-12)))
    dc = np.mean(iq)
    dc_mag = float(np.abs(dc))
    orthogonality = float(np.mean(np.real(iq) * np.imag(iq)))
    return jsonify({
        'status': 'ok',
        'image_rejection_db': image_rejection_db,
        'dc_magnitude': dc_mag,
        'orthogonality': orthogonality
    })

@app.route('/rrc_plot')
def rrc_plot():
    import matplotlib.pyplot as plt
    from io import BytesIO
    import base64
    sps = 8
    num_taps = 21 * sps
    rolloff = 0.35
    rrc = rrc_filter(num_taps, rolloff, sps)
    t = np.arange(-num_taps//2, num_taps//2 + 1) / sps
    plt.figure(figsize=(6,3))
    plt.plot(t, rrc, label=f'RRC taps={num_taps}, sps={sps}, rolloff={rolloff}')
    plt.title('Root Raised Cosine Filter')
    plt.xlabel('Time (symbols)')
    plt.ylabel('Amplitude')
    plt.grid(True)
    plt.legend()
    buf = BytesIO()
    plt.savefig(buf, format='png')
    plt.close()
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('utf-8')
    html = f'<img src="data:image/png;base64,{img_b64}"/><br>sps={sps}, num_taps={num_taps}, rolloff={rolloff}'
    return html

@app.route('/transmit_vsg', methods=['POST'])
def transmit_vsg():
    try:
        if not vsg_status['dll_loaded'] or not vsg_status['device_opened']:
            return jsonify({'status': 'error', 'message': 'VSG not connected'}), 400
        iq = generate_composite_iq(data['signals'], data['sample_rate'])
        iq_interleaved = np.empty(2 * len(iq), dtype=np.float32)
        iq_interleaved[0::2] = np.real(iq)
        iq_interleaved[1::2] = np.imag(iq)
        status = vsg.vsgRepeatWaveform(vsg_status['handle'], iq_interleaved.ctypes.data_as(ctypes.POINTER(ctypes.c_float)), len(iq))
        if status == 0:
            return jsonify({'status': 'ok', 'message': 'Composite IQ transmitted to VSG and looping.'})
        else:
            return jsonify({'status': 'error', 'message': f'VSG error code: {status}'})
    except Exception as e:
        import traceback
        print('Error in /transmit_vsg:', e)
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/abort_vsg', methods=['POST'])
def abort_vsg():
    try:
        if not vsg_status['dll_loaded'] or not vsg_status['device_opened']:
            return jsonify({'status': 'error', 'message': 'VSG not connected'}), 400
        status = vsg.vsgAbort(vsg_status['handle'])
        if status == 0:
            return jsonify({'status': 'ok', 'message': 'VSG transmit stopped.'})
        else:
            return jsonify({'status': 'error', 'message': f'VSG error code: {status}'})
    except Exception as e:
        import traceback
        print('Error in /abort_vsg:', e)
        traceback.print_exc()
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    socketio.run(app, debug=True)
