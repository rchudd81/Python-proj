import ctypes
import os
from ctypes import byref, c_int, c_double

# --- Helper functions must be at the very top ---
def generate_cw(freq_offset, gain_dbm, sample_rate, num_samples):
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * freq_offset * t)

def generate_psk(freq_offset, gain_dbm, sample_rate, num_samples, order=2, symbol_rate=1e5):
    # Generate random PSK symbols
    num_symbols = int(num_samples * symbol_rate / sample_rate)
    symbols = np.random.randint(0, order, num_symbols)
    phase = 2 * np.pi * symbols / order
    # Upsample symbols to samples
    samples_per_symbol = int(sample_rate / symbol_rate)
    phase_upsampled = np.repeat(phase, samples_per_symbol)[:num_samples]
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(1j * (2 * np.pi * freq_offset * t + phase_upsampled))

def generate_composite_iq(signals, sample_rate, duration=0.01):
    num_samples = int(sample_rate * duration)
    iq = np.zeros(num_samples, dtype=np.complex64)
    for sig in signals:
        if not sig.get('enabled', True):
            continue
        if sig['type'] == 'cw':
            iq += generate_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples)
        elif sig['type'] == 'psk':
            order = sig.get('order', 2)
            symbol_rate = sig.get('symbol_rate', 1e5)
            iq += generate_psk(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples, order, symbol_rate)
    if np.max(np.abs(iq)) > 0:
        iq /= np.max(np.abs(iq))
    return iq

# VSG DLL and device initialization
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

from flask import Flask, render_template_string, request, redirect, url_for
import numpy as np
import matplotlib.pyplot as plt
import io
import base64

app = Flask(__name__)

# In-memory signal list and settings
data = {
    'frequency_hz': 1.23e9,
    'level_dbm': -60.0,
    'sample_rate': 10e6,
    'signals': []  # Each: {'type': 'cw', 'freq_offset': float, 'gain_dbm': float, 'enabled': True}
}

# Add a flag for composite IQ transmit
composite_iq_enabled = {'state': False}

# Helper to send composite IQ to VSG (if available)
def vsg_transmit_composite(signals, sample_rate, handle, vsg):
    try:
        print('DEBUG: vsg_transmit_composite called')
        iq = generate_composite_iq(signals, sample_rate)
        print(f'DEBUG: IQ shape: {iq.shape}, dtype: {iq.dtype}, max: {np.max(np.abs(iq))}')
        iq_interleaved = np.empty(2 * len(iq), dtype=np.float32)
        iq_interleaved[0::2] = np.real(iq)
        iq_interleaved[1::2] = np.imag(iq)
        print(f'DEBUG: Interleaved IQ shape: {iq_interleaved.shape}, dtype: {iq_interleaved.dtype}')
        # Try to import vsg_api if available, else use ctypes
        if hasattr(vsg, 'vsg_repeat_waveform'):
            print('DEBUG: Using vsg_repeat_waveform')
            status = vsg.vsg_repeat_waveform(handle, iq_interleaved, len(iq))
            print(f'DEBUG: vsg_repeat_waveform status: {status}')
            return status == 0, 'Composite IQ transmit started.' if status == 0 else f'VSG error: {status}'
        else:
            print('DEBUG: Using ctypes fallback vsgRepeatWaveform')
            vsg.vsgRepeatWaveform.restype = ctypes.c_int
            vsg.vsgRepeatWaveform.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_float), ctypes.c_int]
            arr = iq_interleaved.ctypes.data_as(ctypes.POINTER(ctypes.c_float))
            # Convert handle to c_void_p as required by ctypes
            handle_ptr = ctypes.c_void_p(handle.value if hasattr(handle, 'value') else handle)
            status = vsg.vsgRepeatWaveform(handle_ptr, arr, len(iq))
            print(f'DEBUG: vsgRepeatWaveform status: {status}')
            return status == 0, 'Composite IQ transmit started.' if status == 0 else f'VSG error: {status}'
    except Exception as e:
        print(f'DEBUG: Exception in vsg_transmit_composite: {e}')
        return False, f'Error: {e}'

def vsg_transmit_single_cw(handle, vsg):
    try:
        vsg.vsgOutputCW(handle)
        return True, 'Single CW transmit started.'
    except Exception as e:
        return False, f'Error: {e}'

def vsg_abort(handle, vsg):
    try:
        vsg.vsgAbort(handle)
        return True, 'Transmit stopped.'
    except Exception as e:
        return False, f'Error: {e}'

# Track single CW transmit state (initialize once at module level)
single_cw_enabled = False

@app.route('/', methods=['GET', 'POST'])
def index():
    global single_cw_enabled
    msg = ''
    if request.method == 'POST':
        if 'toggle_composite' in request.form:
            composite_iq_enabled['state'] = not composite_iq_enabled['state']
            if vsg_status['dll_loaded'] and vsg_status['device_opened']:
                if composite_iq_enabled['state']:
                    # Transmit composite IQ
                    ok, m = vsg_transmit_composite(data['signals'], data['sample_rate'], vsg_status['handle'], vsg)
                    msg = m
                    # If composite IQ is enabled, turn off single CW
                    single_cw_enabled = False
                else:
                    ok, m = vsg_abort(vsg_status['handle'], vsg)
                    msg = m
        elif 'single_cw' in request.form:
            single_cw_enabled = not single_cw_enabled
            if vsg_status['dll_loaded'] and vsg_status['device_opened']:
                if single_cw_enabled:
                    ok, m = vsg_transmit_single_cw(vsg_status['handle'], vsg)
                    msg = m
                    # If single CW is enabled, turn off composite IQ
                    composite_iq_enabled['state'] = False
                else:
                    ok, m = vsg_abort(vsg_status['handle'], vsg)
                    msg = m
        elif 'update_freq_sr' in request.form:
            try:
                data['frequency_hz'] = float(request.form['frequency_hz'])
                data['sample_rate'] = float(request.form['sample_rate'])
            except Exception:
                msg = 'Invalid frequency or sample rate.'
        else:
            # Add signal (CW or PSK)
            try:
                sig_type = request.form.get('sig_type', 'cw')
                freq_offset = float(request.form['freq_offset'])
                gain_dbm = float(request.form['gain_dbm'])
                if sig_type == 'psk':
                    order = int(request.form.get('order', 2))
                    symbol_rate = float(request.form.get('symbol_rate', 1e5))
                    data['signals'].append({'type': 'psk', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'order': order, 'symbol_rate': symbol_rate, 'enabled': True})
                else:
                    data['signals'].append({'type': 'cw', 'freq_offset': freq_offset, 'gain_dbm': gain_dbm, 'enabled': True})
            except Exception:
                msg = 'Invalid input.'
        return redirect(url_for('index'))
    plot_html = f'<iframe src="{url_for("plot_img")}" width="850" height="400" frameborder="0"></iframe>'
    return render_template_string('''
        <h2>VSG Web Prototype (CW & PSK)</h2>
        <form method="post" style="margin-bottom:1em;">
            <b>Frequency (Hz):</b> <input name="frequency_hz" type="number" step="any" value="{{frequency_hz}}" required>
            <b>Sample Rate (Hz):</b> <input name="sample_rate" type="number" step="any" value="{{sample_rate}}" required>
            <button name="update_freq_sr" value="1" type="submit">Update</button>
        </form>
        <b>Frequency:</b> {{frequency_hz/1e6}} MHz<br>
        <b>Sample Rate:</b> {{sample_rate/1e6}} MHz<br>
        <b>VSG DLL Loaded:</b> {{vsg_status['dll_loaded']}}<br>
        <b>Device Opened:</b> {{vsg_status['device_opened']}}<br>
        {% if vsg_status['error'] %}<span style="color:red;">{{vsg_status['error']}}</span><br>{% endif %}
        <form method="post">
            Signal Type:
            <select name="sig_type" id="sig_type" onchange="togglePSKFields()">
                <option value="cw">CW</option>
                <option value="psk">PSK</option>
            </select><br>
            Offset from center (Hz): <input name="freq_offset" type="number" step="any" required> <br>
            Gain (dBm): <input name="gain_dbm" type="number" step="any" required> <br>
            <div id="psk_fields" style="display:none;">
                PSK Order (2=QPSK, 4=4-PSK, etc): <input name="order" type="number" value="2" min="2" step="1"><br>
                Symbol Rate (Hz): <input name="symbol_rate" type="number" value="100000" step="any"><br>
            </div>
            <input type="submit" value="Add Signal">
        </form>
        <script>
        function togglePSKFields() {
            var type = document.getElementById('sig_type').value;
            document.getElementById('psk_fields').style.display = (type === 'psk') ? '' : 'none';
        }
        document.addEventListener('DOMContentLoaded', togglePSKFields);
        </script>
        <form method="post" style="margin-top:1em; display:inline;">
            <button name="toggle_composite" value="1" type="submit">{{ 'Disable' if composite_iq_enabled else 'Enable' }} Composite IQ Transmit</button>
            <span style="margin-left:1em;">Current: <b>{{ 'ON' if composite_iq_enabled else 'OFF' }}</b></span>
        </form>
        <form method="post" style="margin-top:1em; display:inline;">
            <button name="single_cw" value="1" type="submit">{{ 'Disable' if single_cw_enabled else 'Enable' }} Single Test CW</button>
            <span style="margin-left:1em;">Current: <b>{{ 'ON' if single_cw_enabled else 'OFF' }}</b></span>
        </form>
        <h3>Current Signals:</h3>
        <ul>
        {% for sig in signals %}
            {% if sig.type == 'cw' %}
                <li>CW: Offset {{sig.freq_offset}} Hz, Gain {{sig.gain_dbm}} dBm, {{'ENABLED' if sig.enabled else 'DISABLED'}}</li>
            {% elif sig.type == 'psk' %}
                <li>PSK: Offset {{sig.freq_offset}} Hz, Gain {{sig.gain_dbm}} dBm, Order {{sig.order}}, Symbol Rate {{sig.symbol_rate}}, {{'ENABLED' if sig.enabled else 'DISABLED'}}</li>
            {% endif %}
        {% endfor %}
        </ul>
        <div style="margin-top:2em;">Spectrum:</div>
        {{plot_html|safe}}
        <div style="color:red;">{{msg}}</div>
    ''', signals=data['signals'], frequency_hz=data['frequency_hz'], sample_rate=data['sample_rate'], composite_iq_enabled=composite_iq_enabled['state'], single_cw_enabled=single_cw_enabled, msg=msg, vsg_status=vsg_status, plot_html=plot_html)

@app.route('/plot_img')
def plot_img():
    iq = generate_composite_iq(data['signals'], data['sample_rate'])
    spectrum = np.fft.fftshift(np.fft.fft(iq))
    freqs = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0/data['sample_rate']))
    power = 20 * np.log10(np.abs(spectrum) + 1e-12)
    fig, ax = plt.subplots(figsize=(8,4))
    ax.plot(freqs/1e6, power)
    ax.set_xlabel('Frequency (MHz)')
    ax.set_ylabel('Power (dB)')
    ax.set_title('CW Composite Spectrum')
    ax.grid(True)
    buf = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buf, format='png')
    plt.close(fig)
    buf.seek(0)
    img_b64 = base64.b64encode(buf.read()).decode('ascii')
    return f'<img src="data:image/png;base64,{img_b64}"/>'

if __name__ == '__main__':
    app.run(debug=True)
