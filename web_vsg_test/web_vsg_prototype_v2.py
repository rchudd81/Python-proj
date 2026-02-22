import ctypes
import os
from ctypes import byref, c_int, c_double
from flask import Flask, render_template_string, request, redirect, url_for, Response
import numpy as np
import matplotlib.pyplot as plt
import io
import base64
import threading
import time
import math
import random

app = Flask(__name__)
vsg_status = {'dll_loaded': False, 'device_opened': False, 'error': '', 'handle': c_int(-1)}
dll_dir = r"C:\Users\Richard\Python-proj\vsg60_series\lib\win\vs2019\x64"
if not os.path.exists(dll_dir):
    vsg_status['error'] = f"DLL path not found: {dll_dir}"
else:
    try:
        os.add_dll_directory(dll_dir)
        vsg = ctypes.cdll.LoadLibrary("vsg_api.dll")
        vsg_status['dll_loaded'] = True
        status = vsg.vsgOpenDevice(byref(vsg_status['handle']))
        if status == 0:
            vsg_status['device_opened'] = True
        else:
            vsg_status['error'] = f"Could not open device. Error code: {status}"
    except Exception as e:
        vsg_status['error'] = f"Failed to load DLL or open device: {e}"

# --- Helper functions ---
def generate_cw(freq_offset, gain_dbm, sample_rate, num_samples):
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * freq_offset * t)

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
    if mod_type == 'bpsk':
        M = 2
        symbols = np.random.choice([1, -1], size=num_symbols)
        phase = np.angle(symbols)
    elif mod_type == 'qpsk':
        M = 4
        bits = np.random.randint(0, 4, num_symbols)
        symbols = np.exp(1j * (np.pi/4 + np.pi/2 * bits))
    elif mod_type == '8psk':
        M = 8
        bits = np.random.randint(0, 8, num_symbols)
        symbols = np.exp(1j * (np.pi/8 + np.pi/4 * bits))
    else:
        raise ValueError('Unsupported PSK type')
    upsampled = np.zeros(num_symbols * sps, dtype=np.complex64)
    upsampled[::sps] = symbols
    num_taps = 11 * sps
    rrc = rrc_filter(num_taps, rolloff, sps)
    shaped = np.convolve(upsampled, rrc, mode='same')
    shaped /= np.max(np.abs(shaped))
    t = np.arange(len(shaped)) / sample_rate
    shaped *= np.exp(2j * np.pi * freq_offset * t)
    shaped *= 10**(gain_dbm/20)
    return shaped

# TDMA PSK slot generator (moved to module level)
def generate_tdma_psk_slots(center_freq, gain_dbm, sample_rate, num_samples, num_slots, slot_bw, min_pulse, max_pulse):
    iq = np.zeros(num_samples, dtype=np.complex64)
    slot_spacing = slot_bw
    for slot in range(num_slots):
        freq_offset = center_freq + (slot - (num_slots-1)/2) * slot_spacing
        mod_type = 'qpsk'
        rolloff = 0.35
        symrate = 1e6
        sps = int(sample_rate / symrate)
        if sps < 2:
            sps = 2
        num_symbols = int(num_samples / sps)
        psk = generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, freq_offset, gain_dbm)
        if len(psk) > num_samples:
            psk = psk[:num_samples]
        elif len(psk) < num_samples:
            psk = np.pad(psk, (0, num_samples - len(psk)))
        pulse_width = 0.0002
        pulse_freq = np.random.uniform(min_pulse, max_pulse)
        psk = apply_pulse_envelope(psk, sample_rate, pulse_width, pulse_freq)
        iq += psk
    if np.max(np.abs(iq)) > 0:
        iq /= np.max(np.abs(iq))
    return iq

def generate_sweeping_cw(freq_offset, gain_dbm, sample_rate, num_samples, sweep_bw, sweep_speed):
    # sweep_bw: sweep bandwidth in Hz (centered on freq_offset)
    # sweep_speed: sweep cycles per second (Hz)
    t = np.arange(num_samples) / sample_rate
    # Sweep: freq_offset + sweep_bw/2 * sin(2*pi*sweep_speed*t)
    sweep_freq = freq_offset + (sweep_bw/2) * np.sin(2 * np.pi * sweep_speed * t)
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * sweep_freq * t)

def generate_freq_hopping_cw(center_freq, gain_dbm, sample_rate, num_samples, hop_bw, num_slots, hop_rate):
    # center_freq: center frequency offset (Hz)
    # hop_bw: total hopping bandwidth (Hz)
    # num_slots: number of frequency slots
    # hop_rate: hops per second
    t = np.arange(num_samples) / sample_rate
    slot_width = hop_bw / num_slots
    slot_freqs = [center_freq - hop_bw/2 + slot_width/2 + i*slot_width for i in range(num_slots)]
    hop_period = 1.0 / hop_rate
    slot_indices = np.zeros(num_samples, dtype=int)
    current_slot = random.randint(0, num_slots-1)
    next_hop_time = hop_period
    for i in range(num_samples):
        if i / sample_rate >= next_hop_time:
            current_slot = random.randint(0, num_slots-1)
            next_hop_time += hop_period
        slot_indices[i] = current_slot
    inst_freq = np.array([slot_freqs[idx] for idx in slot_indices])
    phase = 2 * np.pi * np.cumsum(inst_freq) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(1j * phase)

def generate_composite_iq(signals, sample_rate, duration=0.01):
    num_samples = int(sample_rate * duration)
    iq = np.zeros(num_samples, dtype=np.complex64)
    for sig in signals:
        if not sig.get('enabled', True):
            continue
        pulse_width = sig.get('pulse_width', None)
        pulse_freq = sig.get('pulse_freq', None)
        if sig['type'] == 'cw':
            iq_cw = generate_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples)
            if pulse_width and pulse_freq:
                iq_cw = apply_pulse_envelope(iq_cw, sample_rate, pulse_width, pulse_freq)
            iq += iq_cw
        elif sig['type'] == 'psk':
            mod_type = sig.get('mod_type', 'qpsk')
            rolloff = sig.get('rolloff', 0.35)
            symrate = sig.get('symrate', 1e6)
            sps = int(sample_rate / symrate)
            if sps < 2:
                sps = 2
            num_symbols = int(num_samples / sps)
            psk = generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate, sig['freq_offset'], sig['gain_dbm'])
            if len(psk) > num_samples:
                psk = psk[:num_samples]
            elif len(psk) < num_samples:
                psk = np.pad(psk, (0, num_samples - len(psk)))
            if pulse_width and pulse_freq:
                psk = apply_pulse_envelope(psk, sample_rate, pulse_width, pulse_freq)
            iq += psk
        elif sig['type'] == 'sweeping_cw':
            sweep_bw = sig.get('sweep_bw', 1e6)
            sweep_speed = sig.get('sweep_speed', 100)
            iq += generate_sweeping_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples, sweep_bw, sweep_speed)
        elif sig['type'] == 'freq_hopping_cw':
            hop_bw = sig.get('hop_bw', 1e6)
            num_slots = sig.get('num_slots', 8)
            hop_rate = sig.get('hop_rate', 100)
            iq += generate_freq_hopping_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples, hop_bw, num_slots, hop_rate)
        elif sig['type'] == 'tdma':
            # TDMA Sim: use generate_tdma_psk_slots
            num_slots = sig.get('num_slots', 4)
            slot_bw = sig.get('slot_bw', 200000)
            min_pulse = sig.get('min_pulse', 500)
            max_pulse = sig.get('max_pulse', 2000)
            # Use the freq_offset as center_freq
            iq += generate_tdma_psk_slots(
                sig.get('freq_offset', 0),
                sig.get('gain_dbm', 0),
                sample_rate,
                num_samples,
                num_slots,
                slot_bw,
                min_pulse,
                max_pulse
            )
    if np.max(np.abs(iq)) > 0:
        iq /= np.max(np.abs(iq))
    return iq

def apply_pulse_envelope(iq, sample_rate, pulse_width, pulse_freq):
    num_samples = len(iq)
    t = np.arange(num_samples) / sample_rate
    period = 1.0 / pulse_freq
    pulse_samples = int(pulse_width * sample_rate)
    env = np.zeros(num_samples)
    for i in range(num_samples):
        in_pulse = (t[i] % period) < pulse_width
        env[i] = 1.0 if in_pulse else 0.0
    return iq * env

# Helper to send composite IQ to VSG (if available)
def vsg_transmit_composite(signals, sample_rate, handle, vsg):
    try:
        iq = generate_composite_iq(signals, sample_rate)
        iq_interleaved = np.empty(2 * len(iq), dtype=np.float32)
        iq_interleaved[0::2] = np.real(iq)
        iq_interleaved[1::2] = np.imag(iq)
        vsg.vsgRepeatWaveform.restype = ctypes.c_int
        vsg.vsgRepeatWaveform.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int]
        arr = iq_interleaved.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
        handle_ptr = ctypes.c_void_p(handle.value if hasattr(handle, 'value') else handle)
        status = vsg.vsgRepeatWaveform(handle_ptr, arr, len(iq))
        return status == 0, 'Composite IQ transmit started.' if status == 0 else f'VSG error: {status}'
    except Exception as e:
        return False, f'Error: {e}'

# In-memory signal list and settings
data = {
    'frequency_hz': 1.23e9,
    'level_dbm': -60.0,
    'sample_rate': 10e6,
    'signals': []
}

composite_iq_enabled = {'state': False}
single_cw_enabled = False

# --- Real-time spectrum update ---
spectrum_img_b64 = ''
update_interval = 0.5  # seconds

def spectrum_update_loop():
    global spectrum_img_b64
    while True:
        iq = generate_composite_iq(data['signals'], data['sample_rate'])
        spectrum = np.fft.fftshift(np.fft.fft(iq))
        freqs = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0/data['sample_rate']))
        power = 20 * np.log10(np.abs(spectrum) + 1e-12)
        fig, ax = plt.subplots(figsize=(8,4))
        ax.plot(freqs/1e6, power)
        ax.set_xlabel('Frequency (MHz)')
        ax.set_ylabel('Power (dB)')
        ax.set_title('CW/PSK Composite Spectrum')
        ax.grid(True)
        buf = io.BytesIO()
        plt.tight_layout()
        plt.savefig(buf, format='png')
        plt.close(fig)
        buf.seek(0)
        spectrum_img_b64 = base64.b64encode(buf.read()).decode('ascii')
        time.sleep(update_interval)

threading.Thread(target=spectrum_update_loop, daemon=True).start()

def vsg_abort(handle, vsg):
    try:
        vsg.vsgAbort(handle)
        return True, 'Transmit stopped.'
    except Exception as e:
        return False, f'Error: {e}'

@app.route('/', methods=['GET', 'POST'])
def index():
    msg = ''
    if request.method == 'POST':
        # Add signal logic (must come before inline editing logic)
        if request.form.get('add_signal_btn') == '1' and request.form.get('sig_type') in ['cw', 'psk']:
            sig_type = request.form.get('sig_type', 'cw')
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            pulse_width = request.form.get('pulse_width', None)
            pulse_freq = request.form.get('pulse_freq', None)
            if pulse_width is not None and pulse_freq is not None and pulse_width != '' and pulse_freq != '':
                pulse_width = float(pulse_width)
                pulse_freq = float(pulse_freq)
            else:
                pulse_width = None
                pulse_freq = None
            if sig_type == 'cw':
                data['signals'].append({'type': 'cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'enabled': True, 'pulse_width': pulse_width, 'pulse_freq': pulse_freq})
                msg = 'CW signal added.'
            elif sig_type == 'psk':
                mod_type = request.form.get('mod_type', 'qpsk')
                rolloff = float(request.form.get('rolloff', 0.35))
                symrate = float(request.form.get('symrate', 1e6))
                data['signals'].append({'type': 'psk', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'mod_type': mod_type, 'rolloff': rolloff, 'symrate': symrate, 'enabled': True, 'pulse_width': pulse_width, 'pulse_freq': pulse_freq})
                msg = 'PSK signal added.'
            return redirect(url_for('index'))
        if request.form.get('add_tdma') == '1':
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            num_slots = int(request.form.get('tdma_num_slots', 4))
            slot_bw = float(request.form.get('tdma_slot_bw', 200000))
            min_pulse = float(request.form.get('tdma_min_pulse', 500))
            max_pulse = float(request.form.get('tdma_max_pulse', 2000))
            data['signals'].append({'type': 'tdma', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'num_slots': num_slots, 'slot_bw': slot_bw, 'min_pulse': min_pulse, 'max_pulse': max_pulse, 'enabled': True})
            msg = 'TDMA simulation added.'
            return redirect(url_for('index'))
        if request.form.get('add_sweeping_cw') == '1':
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            sweep_bw = float(request.form.get('sweep_bw', 1e6))
            sweep_speed = float(request.form.get('sweep_speed', 100))
            data['signals'].append({'type': 'sweeping_cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'sweep_bw': sweep_bw, 'sweep_speed': sweep_speed, 'enabled': True})
            msg = 'Sweeping CW signal added.'
            return redirect(url_for('index'))
        if request.form.get('add_freq_hopping_cw') == '1':
            freq_offset = float(request.form.get('freq_offset', 0))
            gain_dbm = float(request.form.get('gain_dbm', 0))
            hop_bw = float(request.form.get('hop_bw', 1e6))
            num_slots = int(request.form.get('num_slots', 8))
            hop_rate = float(request.form.get('hop_rate', 100))
            data['signals'].append({'type': 'freq_hopping_cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'hop_bw': hop_bw, 'num_slots': num_slots, 'hop_rate': hop_rate, 'enabled': True})
            msg = 'Freq Hopping CW signal added.'
            return redirect(url_for('index'))
        # Update frequency and sample rate
        if request.form.get('update_freq_sr') == '1':
            try:
                data['frequency_hz'] = float(request.form.get('frequency_hz', data['frequency_hz']))
                data['sample_rate'] = float(request.form.get('sample_rate', data['sample_rate']))
                msg = 'Frequency and sample rate updated.'
            except Exception:
                msg = 'Invalid frequency or sample rate.'
            return redirect(url_for('index'))
        # Enable/disable composite IQ transmit
        if request.form.get('toggle_composite') == '1':
            composite_iq_enabled['state'] = not composite_iq_enabled['state']
            if composite_iq_enabled['state']:
                ok, msg = vsg_transmit_composite(data['signals'], data['sample_rate'], vsg_status['handle'], vsg)
            else:
                ok, msg = vsg_abort(vsg_status['handle'], vsg)
            return redirect(url_for('index'))
        # Enable/disable single test CW
        if request.form.get('single_cw') == '1':
            global single_cw_enabled
            single_cw_enabled = not single_cw_enabled
            if single_cw_enabled:
                # Transmit a single CW at center frequency
                test_signal = [{'type': 'cw', 'freq_offset': 0, 'gain_dbm': data['level_dbm'], 'enabled': True}]
                ok, msg = vsg_transmit_composite(test_signal, data['sample_rate'], vsg_status['handle'], vsg)
            else:
                ok, msg = vsg_abort(vsg_status['handle'], vsg)
            return redirect(url_for('index'))
        # Inline signal editing logic
        for i, sig in enumerate(data['signals']):
            if request.form.get(f'delete_{i}'):
                data['signals'].pop(i)
                msg = f"Signal {i+1} deleted."
                return redirect(url_for('index'))
            if request.form.get(f'toggle_{i}'):
                sig['enabled'] = not sig.get('enabled', True)
                msg = f"Signal {i+1} toggled."
                return redirect(url_for('index'))
        if request.form.get('update_signals'):
            for i, sig in enumerate(data['signals']):
                try:
                    sig['freq_offset'] = float(request.form.get(f'freq_offset_{i}', sig['freq_offset']))
                    sig['gain_dbm'] = float(request.form.get(f'gain_dbm_{i}', sig['gain_dbm']))
                    if sig['type'] == 'psk':
                        sig['mod_type'] = request.form.get(f'mod_type_{i}', sig['mod_type'])
                        sig['rolloff'] = float(request.form.get(f'rolloff_{i}', sig['rolloff']))
                        sig['symrate'] = float(request.form.get(f'symrate_{i}', sig['symrate']))
                    if sig['type'] == 'sweeping_cw':
                        sig['sweep_bw'] = float(request.form.get(f'sweep_bw_{i}', sig['sweep_bw']))
                        sig['sweep_speed'] = float(request.form.get(f'sweep_speed_{i}', sig['sweep_speed']))
                    if sig['type'] == 'freq_hopping_cw':
                        sig['hop_bw'] = float(request.form.get(f'hop_bw_{i}', sig['hop_bw']))
                        sig['num_slots'] = int(request.form.get(f'num_slots_{i}', sig['num_slots']))
                        sig['hop_rate'] = float(request.form.get(f'hop_rate_{i}', sig['hop_rate']))
                    if sig['type'] == 'tdma':
                        sig['num_slots'] = int(request.form.get(f'tdma_num_slots_{i}', sig['num_slots']))
                        sig['slot_bw'] = float(request.form.get(f'tdma_slot_bw_{i}', sig['slot_bw']))
                        sig['min_pulse'] = float(request.form.get(f'tdma_min_pulse_{i}', sig['min_pulse']))
                        sig['max_pulse'] = float(request.form.get(f'tdma_max_pulse_{i}', sig['max_pulse']))
                    if sig['type'] == 'cw' or sig['type'] == 'psk':
                        pulse_enabled = request.form.get(f'pulse_enable_{i}', None)
                        pw = request.form.get(f'pulse_width_{i}', '')
                        pf = request.form.get(f'pulse_freq_{i}', '')
                        if pulse_enabled and pw and pf:
                            sig['pulse_width'] = float(pw)
                            sig['pulse_freq'] = float(pf)
                        else:
                            sig['pulse_width'] = None
                            sig['pulse_freq'] = None
                except Exception:
                    msg = f"Error updating signal {i+1}."
            msg = "Signals updated."
            return redirect(url_for('index'))
    return render_template_string('''
        <h2>VSG Web Prototype v2 (CW, PSK, Sweeping CW, Real-Time Spectrum, TDMA Sim)</h2>
        <b>VSG DLL Loaded:</b> {{vsg_status['dll_loaded']}}<br>
        <b>Device Opened:</b> {{vsg_status['device_opened']}}<br>
        {% if vsg_status['error'] %}<span style="color:red;">{{vsg_status['error']}}</span><br>{% endif %}
        <form method="post" style="margin-bottom:1em;">
            <b>Frequency (Hz):</b> <input name="frequency_hz" type="number" step="any" value="{{frequency_hz}}" required>
            <b>Sample Rate (Hz):</b> <input name="sample_rate" type="number" step="any" value="{{sample_rate}}" required>
            <button name="update_freq_sr" value="1" type="submit">Update</button>
        </form>
        <form method="post">
            Signal Type:
            <select name="sig_type" id="sig_type" onchange="toggleSignalFields()">
                <option value="cw">CW</option>
                <option value="psk">PSK</option>
                <option value="sweeping_cw">Sweeping CW</option>
                <option value="freq_hopping_cw">Freq Hopping CW</option>
                <option value="tdma">TDMA Sim</option>
            </select><br>
            Offset from center (Hz): <input name="freq_offset" type="number" step="any" required> <br>
            Gain (dBm): <input name="gain_dbm" type="number" step="any" required> <br>
            <div id="psk_fields" style="display:none;">
                PSK Type: <select name="mod_type">
                    <option value="bpsk">BPSK</option>
                    <option value="qpsk">QPSK</option>
                    <option value="8psk">8PSK</option>
                </select><br>
                RRC Roll-off: <input name="rolloff" type="number" value="0.35" step="0.05" min="0.2" max="0.35"><br>
                Symbol Rate (Hz): <input name="symrate" type="number" value="1000000" step="any"><br>
            </div>
            <div id="sweeping_cw_fields" style="display:none;">
                Sweep Bandwidth (Hz): <input name="sweep_bw" type="number" value="1000000" step="any"><br>
                Sweep Speed (Hz): <input name="sweep_speed" type="number" value="100" step="any"><br>
            </div>
            <div id="freq_hopping_cw_fields" style="display:none;">
                Hopping Bandwidth (Hz): <input name="hop_bw" type="number" value="1000000" step="any"><br>
                Number of Slots: <input name="num_slots" type="number" value="8" min="2" step="1"><br>
                Hop Rate (Hz): <input name="hop_rate" type="number" value="100" step="any"><br>
            </div>
            <div id="tdma_fields" style="display:none;">
                Number of Slots: <input name="tdma_num_slots" type="number" value="4" min="1" max="10" step="1"><br>
                Slot Bandwidth (Hz): <input name="tdma_slot_bw" type="number" value="200000" step="any"><br>
                Min Pulse Rate (Hz): <input name="tdma_min_pulse" type="number" value="500" step="any"><br>
                Max Pulse Rate (Hz): <input name="tdma_max_pulse" type="number" value="2000" step="any"><br>
            </div>
            <div id="cw_pulse_fields" style="display:none;">
                Pulse Width (s): <input name="pulse_width" type="number" value="0.0001" step="any"><br>
                Pulse Frequency (Hz): <input name="pulse_freq" type="number" value="1000" step="any"><br>
            </div>
            <button id="add_signal_btn" name="add_signal_btn" value="1" type="submit">Add Signal</button>
            <button id="add_sweeping_cw_btn" name="add_sweeping_cw" value="1" type="submit" style="display:none;">Add Sweeping CW Signal</button>
            <button id="add_freq_hopping_cw_btn" name="add_freq_hopping_cw" value="1" type="submit" style="display:none;">Add Freq Hopping CW</button>
            <button id="add_tdma_btn" name="add_tdma" value="1" type="submit" style="display:none;">Add TDMA Sim</button>
        </form>
        <script>
        function toggleSignalFields() {
            var type = document.getElementById('sig_type').value;
            document.getElementById('psk_fields').style.display = (type === 'psk') ? '' : 'none';
            document.getElementById('sweeping_cw_fields').style.display = (type === 'sweeping_cw') ? '' : 'none';
            document.getElementById('freq_hopping_cw_fields').style.display = (type === 'freq_hopping_cw') ? '' : 'none';
            document.getElementById('tdma_fields').style.display = (type === 'tdma') ? '' : 'none';
            document.getElementById('cw_pulse_fields').style.display = (type === 'cw' || type === 'psk') ? '' : 'none';
            document.getElementById('add_signal_btn').style.display = (type !== 'sweeping_cw' && type !== 'freq_hopping_cw' && type !== 'tdma') ? '' : 'none';
            document.getElementById('add_sweeping_cw_btn').style.display = (type === 'sweeping_cw') ? '' : 'none';
            document.getElementById('add_freq_hopping_cw_btn').style.display = (type === 'freq_hopping_cw') ? '' : 'none';
            document.getElementById('add_tdma_btn').style.display = (type === 'tdma') ? '' : 'none';
        }
        document.addEventListener('DOMContentLoaded', toggleSignalFields);
        document.getElementById('sig_type').addEventListener('change', toggleSignalFields);
        </script>
        <form method="post" style="margin-top:1em; display:inline;">
            <button name="toggle_composite" value="1" type="submit">{{ 'Disable' if composite_iq_enabled else 'Enable' }} Composite IQ Transmit</button>
            <span style="margin-left:1em;">Current: <b>{{ 'ON' if composite_iq_enabled else 'OFF' }}</b></span>
        </form>
        <form method="post" style="margin-top:1em; display:inline;">
            <button name="single_cw" value="1" type="submit">{{ 'Disable' if single_cw_enabled else 'Enable' }} Single Test CW</button>
            <span style="margin-left:1em;">Current: <b>{{ 'ON' if single_cw_enabled else 'OFF' }}</b></span>
        </form>
        <h2>Signal List</h2>
        <form method="post">
        <ul>
        {% for i in range(signals|length) %}
            {% set sig = signals[i] %}
            <li>
                <input type="hidden" name="sig_index" value="{{i}}">
                {{i+1}}. {{sig.type|upper}} |
                Offset: <input name="freq_offset_{{i}}" type="number" step="any" value="{{sig.freq_offset}}" style="width:100px;">
                Gain: <input name="gain_dbm_{{i}}" type="number" step="any" value="{{sig.gain_dbm}}" style="width:80px;">
                {% if sig.type == 'psk' %}
                    | PSK: <select name="mod_type_{{i}}">
                        <option value="bpsk" {% if sig.mod_type=='bpsk' %}selected{% endif %}>BPSK</option>
                        <option value="qpsk" {% if sig.mod_type=='qpsk' %}selected{% endif %}>QPSK</option>
                        <option value="8psk" {% if sig.mod_type=='8psk' %}selected{% endif %}>8PSK</option>
                    </select>
                    | RRC: <input name="rolloff_{{i}}" type="number" value="{{sig.rolloff}}" step="0.05" min="0.2" max="0.35" style="width:60px;">
                    | Symrate: <input name="symrate_{{i}}" type="number" value="{{sig.symrate}}" step="any" style="width:80px;">
                {% endif %}
                {% if sig.type == 'sweeping_cw' %}
                    | BW: <input name="sweep_bw_{{i}}" type="number" value="{{sig.sweep_bw}}" step="any" style="width:80px;">
                    | Speed: <input name="sweep_speed_{{i}}" type="number" value="{{sig.sweep_speed}}" step="any" style="width:80px;">
                {% endif %}
                {% if sig.type == 'freq_hopping_cw' %}
                    | BW: <input name="hop_bw_{{i}}" type="number" value="{{sig.hop_bw}}" step="any" style="width:80px;">
                    | Slots: <input name="num_slots_{{i}}" type="number" value="{{sig.num_slots}}" min="2" step="1" style="width:60px;">
                    | Rate: <input name="hop_rate_{{i}}" type="number" value="{{sig.hop_rate}}" step="any" style="width:80px;">
                {% endif %}
                {% if sig.type == 'tdma' %}
                    | Slots: <input name="tdma_num_slots_{{i}}" type="number" value="{{sig.num_slots}}" min="1" max="10" step="1" style="width:60px;">
                    | Slot BW: <input name="tdma_slot_bw_{{i}}" type="number" value="{{sig.slot_bw}}" step="any" style="width:80px;">
                    | Min Pulse: <input name="tdma_min_pulse_{{i}}" type="number" value="{{sig.min_pulse}}" step="any" style="width:80px;">
                    | Max Pulse: <input name="tdma_max_pulse_{{i}}" type="number" value="{{sig.max_pulse}}" step="any" style="width:80px;">
                {% endif %}
                {% if sig.type == 'cw' or sig.type == 'psk' %}
                    | <label><input type="checkbox" name="pulse_enable_{{i}}" value="1" {% if sig.pulse_width and sig.pulse_freq %}checked{% endif %}> Pulse</label>
                    <span style="margin-left:8px;">Width (s): <input name="pulse_width_{{i}}" type="number" step="any" value="{{sig.pulse_width if sig.pulse_width is not none else ''}}" style="width:80px;"></span>
                    <span style="margin-left:8px;">Freq (Hz): <input name="pulse_freq_{{i}}" type="number" step="any" value="{{sig.pulse_freq if sig.pulse_freq is not none else ''}}" style="width:80px;"></span>
                {% endif %}
                <b>{{'ENABLED' if sig.get('enabled', True) else 'DISABLED'}}</b>
                <button name="toggle_{{i}}" value="1" type="submit">Toggle</button>
                <button name="delete_{{i}}" value="1" type="submit" onclick="return confirm('Delete this signal?');">Delete</button>
            </li>
        {% endfor %}
        </ul>
        <button name="update_signals" value="1" type="submit">Update All</button>
        </form>
        <div style="margin-top:2em;">Spectrum (updates every {{interval}}s):</div>
        <img id="spectrum_img" src="/spectrum_img" width="850" height="400" />
        <script>
        setInterval(function() {
            document.getElementById('spectrum_img').src = '/spectrum_img?' + Date.now();
        }, {{interval}} * 1000);
        </script>
        <div style="color:red;">{{msg}}</div>
    ''', signals=data['signals'], frequency_hz=data['frequency_hz'], sample_rate=data['sample_rate'], composite_iq_enabled=composite_iq_enabled['state'], single_cw_enabled=single_cw_enabled, msg=msg, interval=update_interval, vsg_status=vsg_status)

@app.route('/spectrum_img')
def spectrum_img():
    global spectrum_img_b64
    # Return the actual PNG image, not an HTML tag
    if spectrum_img_b64:
        img_bytes = base64.b64decode(spectrum_img_b64)
        return Response(img_bytes, mimetype='image/png')
    else:
        return Response('', mimetype='image/png')

@app.route('/edit_signal/<int:index>', methods=['GET', 'POST'])
def edit_signal_route(index):
    if index < 0 or index >= len(data['signals']):
        return redirect(url_for('index'))
    sig = data['signals'][index]
    if request.method == 'POST':
        action = request.form.get('action')
        if action == 'delete':
            del data['signals'][index]
            return redirect(url_for('index'))
        elif action == 'toggle':
            sig['enabled'] = not sig.get('enabled', True)
        else:
            # Update fields based on type
            try:
                sig['freq_offset'] = float(request.form.get('freq_offset', sig['freq_offset']))
                sig['gain_dbm'] = float(request.form.get('gain_dbm', sig['gain_dbm']))
                if sig['type'] == 'psk':
                    sig['mod_type'] = request.form.get('mod_type', sig['mod_type'])
                    sig['rolloff'] = float(request.form.get('rolloff', sig['rolloff']))
                    sig['symrate'] = float(request.form.get('symrate', sig['symrate']))
                if sig['type'] == 'sweeping_cw':
                    sig['sweep_bw'] = float(request.form.get('sweep_bw', sig['sweep_bw']))
                    sig['sweep_speed'] = float(request.form.get('sweep_speed', sig['sweep_speed']))
                if sig['type'] == 'freq_hopping_cw':
                    sig['hop_bw'] = float(request.form.get(f'hop_bw_{i}', sig['hop_bw']))
                    sig['num_slots'] = int(request.form.get(f'num_slots_{i}', sig['num_slots']))
                    sig['hop_rate'] = float(request.form.get(f'hop_rate_{i}', sig['hop_rate']))
                if sig['type'] == 'cw' or sig['type'] == 'psk':
                    pulse_enabled = request.form.get(f'pulse_enable_{i}', None)
                    pw = request.form.get(f'pulse_width_{i}', '')
                    pf = request.form.get(f'pulse_freq_{i}', '')
                    if pulse_enabled and pw and pf:
                        sig['pulse_width'] = float(pw)
                        sig['pulse_freq'] = float(pf)
                    else:
                        sig['pulse_width'] = None
                        sig['pulse_freq'] = None
            except Exception:
                pass
        return redirect(url_for('index'))
    # Render edit form
    return render_template_string('''
        <h2>Edit Signal {{index+1}}</h2>
        <form method="post">
            Offset from center (Hz): <input name="freq_offset" type="number" step="any" value="{{sig.freq_offset}}" required><br>
            Gain (dBm): <input name="gain_dbm" type="number" step="any" value="{{sig.gain_dbm}}" required><br>
            {% if sig.type == 'psk' %}
                PSK Type: <select name="mod_type">
                    <option value="bpsk" {% if sig.mod_type=='bpsk' %}selected{% endif %}>BPSK</option>
                    <option value="qpsk" {% if sig.mod_type=='qpsk' %}selected{% endif %}>QPSK</option>
                    <option value="8psk" {% if sig.mod_type=='8psk' %}selected{% endif %}>8PSK</option>
                </select><br>
                RRC Roll-off: <input name="rolloff" type="number" value="{{sig.rolloff}}" step="0.05" min="0.2" max="0.35" style="width:60px;">
                | Symrate: <input name="symrate" type="number" value="{{sig.symrate}}" step="any" style="width:80px;">
            {% endif %} {% if sig.type == 'sweeping_cw' %}
                Sweep Bandwidth (Hz): <input name="sweep_bw" type="number" value="{{sig.sweep_bw}}" step="any" style="width:80px;">
                | Speed: <input name="sweep_speed" type="number" value="{{sig.sweep_speed}}" step="any" style="width:80px;">
            {% endif %} {% if sig.type == 'freq_hopping_cw' %}
                | BW: <input name="hop_bw_{{i}}" type="number" value="{{sig.hop_bw}}" step="any" style="width:80px;">
                | Slots: <input name="num_slots_{{i}}" type="number" value="{{sig.num_slots}}" min="2" step="1" style="width:60px;">
                | Rate: <input name="hop_rate_{{i}}" type="number" value="{{sig.hop_rate}}" step="any" style="width:80px;">
            {% endif %} <b>{{'ENABLED' if sig.get('enabled', True) else 'DISABLED'}}</b>
            <button name="action" value="update" type="submit">Update</button>
            <button name="action" value="toggle" type="submit">Toggle Enable/Disable</button>
            <button name="action" value="delete" type="submit" onclick="return confirm('Delete this signal?');">Delete</button>
        </form>
        <a href="{{url_for('index')}}">Back</a>
    ''', sig=sig, index=index)

if __name__ == '__main__':
    app.run(debug=True)
