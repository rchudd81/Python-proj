import numpy as np
import sys
from scipy.signal import upfirdn, fir_filter_design, kaiserord, firwin
from scipy.signal import lfilter
import math
import ctypes
import os
from ctypes import byref, c_int, c_double

# 1. Point to the directory containing your Signal Hound .dll
dll_dir = r"C:\Users\Richard\Python-proj\vsg60_series\lib\win\vs2019\x64"
if not os.path.exists(dll_dir):
    print(f"Error: Path not found: {dll_dir}")
else:
    os.add_dll_directory(dll_dir)
# 2. Load the API
try:
    vsg = ctypes.cdll.LoadLibrary("vsg_api.dll")
except Exception as e:
    print(f"Failed to load DLL: {e}")
    exit()

# 3. Setup variables
handle = c_int(-1)
frequency_hz = 1.230e9
level_dbm = -60.0


def parse_frequency(s: str) -> float:
    s = s.strip().lower()
    multiplier = 1.0
    if s.endswith('ghz'):
        multiplier = 1e9
        s = s[:-3]
    elif s.endswith('mhz'):
        multiplier = 1e6
        s = s[:-3]
    elif s.endswith('khz'):
        multiplier = 1e3
        s = s[:-3]
    elif s.endswith('hz'):
        multiplier = 1.0
        s = s[:-2]
    try:
        return float(s) * multiplier
    except Exception:
        raise ValueError("Invalid frequency format")


def print_menu(freq, lvl, tx_enabled, sample_rate, signals):
    print('\nVSG CLI Menu')
    print('-------------')
    print(f'1) Set frequency (current: {freq/1e6:.6f} MHz)')
    print(f'2) Set level/gain (current: {lvl:.1f} dBm)')
    print(f'3) Toggle single CW transmit (currently: {"ON" if tx_enabled else "OFF"})')
    print(f'4) Set sample rate (current: {sample_rate/1e6:.3f} MHz)')
    print('5) Add signal (CW spike)')
    print('6) Add PSK signal (BPSK/QPSK/8PSK)')
    print('7) Show settings/signals')
    print('8) Edit/remove/enable/disable signal')
    print(f'9) Toggle composite IQ transmit (currently: {"ON" if tx_enabled else "OFF"})')
    print('10) Show real-time spectrum plot')
    print('q) Quit')
    print('\nCurrent Signals:')
    if signals:
        for i, sig in enumerate(signals):
            status = 'ENABLED' if sig.get('enabled', True) else 'DISABLED'
            if sig['type'] == 'cw':
                print(f'  {i+1}) CW: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, {status}')
            elif sig['type'] == 'psk':
                print(f'  {i+1}) {sig["mod_type"].upper()}: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, RRC: {sig["rolloff"]}, SymRate: {sig["symrate"]}, {status}')
    else:
        print('  No signals defined.')
def rrc_filter(num_taps, beta, sps):
    # Root Raised Cosine (RRC) filter design
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

def generate_psk(mod_type, num_symbols, sps, rolloff, symrate, sample_rate):
    # Generate random PSK symbols
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
    # Upsample
    upsampled = upfirdn([1], symbols, sps)
    # RRC filter
    num_taps = 11 * sps
    rrc = rrc_filter(num_taps, rolloff, sps)
    shaped = np.convolve(upsampled, rrc, mode='same')
    # Normalize
    shaped /= np.max(np.abs(shaped))
    return shaped.astype(np.complex64)

def generate_cw(freq_offset, gain_dbm, sample_rate, num_samples):
    t = np.arange(num_samples) / sample_rate
    amp = 10**(gain_dbm/20)
    return amp * np.exp(2j * np.pi * freq_offset * t)

def generate_composite_iq(signals, sample_rate, duration=0.01):
    num_samples = int(sample_rate * duration)
    iq = np.zeros(num_samples, dtype=np.complex64)
    for sig in signals:
        if not sig.get('enabled', True):
            continue
        if sig['type'] == 'cw':
            iq += generate_cw(sig['freq_offset'], sig['gain_dbm'], sample_rate, num_samples)
        elif sig['type'] == 'psk':
            sps = int(sample_rate / sig['symrate'])
            if sps < 2:
                sps = 2
            num_symbols = int(num_samples / sps)
            psk = generate_psk(sig['mod_type'], num_symbols, sps, sig['rolloff'], sig['symrate'], sample_rate)
            # Frequency offset
            t = np.arange(len(psk)) / sample_rate
            psk *= np.exp(2j * np.pi * sig['freq_offset'] * t)
            # Gain
            psk *= 10**(sig['gain_dbm']/20)
            # Add to composite
            if len(psk) > num_samples:
                psk = psk[:num_samples]
            elif len(psk) < num_samples:
                psk = np.pad(psk, (0, num_samples - len(psk)))
            iq += psk
    # Normalize composite
    if np.max(np.abs(iq)) > 0:
        iq /= np.max(np.abs(iq))
    return iq


def apply_frequency(handle, freq_hz):
    try:
        vsg.vsgSetFrequency(handle, c_double(freq_hz))
        print(f'Frequency set to {freq_hz/1e6:.6f} MHz')
    except Exception as e:
        print(f'Failed to set frequency: {e}')


def apply_level(handle, level_dbm):
    try:
        vsg.vsgSetLevel(handle, c_double(level_dbm))
        print(f'Level set to {level_dbm:.1f} dBm')
    except Exception as e:
        print(f'Failed to set level: {e}')





def main():
    global frequency_hz, level_dbm

    sample_rate = 10e6  # Default 10 MHz
    signals = []  # Each signal: dict with type ('cw' or 'psk'), plus relevant params

    # --- Always launch plot window at program start if not running ---
    import os, sys, time
    LOCKFILE = os.path.join(os.path.dirname(__file__), 'vsg_plot.lock')
    def is_plot_running():
        return os.path.exists(LOCKFILE)
    def create_lock():
        with open(LOCKFILE, 'w') as f:
            f.write('running')
    if not is_plot_running():
        import subprocess
        subprocess.Popen([
            sys.executable,
            os.path.join(os.path.dirname(__file__), 'vsg_plot.py')
        ])
        create_lock()
        print('Plot window not running. Launched new plot window.')
        time.sleep(3.0)

    # 4. Detect and Open Device
    print("Attempting to find VSG60 device...")
    status = vsg.vsgOpenDevice(byref(handle))

    if status != 0:
        print(f"Could not find or open device. Error code: {status}")
        return
    print(f"Success! Device opened with handle: {handle.value}")

    # Apply initial settings
    apply_frequency(handle, frequency_hz)
    apply_level(handle, level_dbm)

    tx_enabled = False

    while True:
        print_menu(frequency_hz, level_dbm, tx_enabled, sample_rate, signals)
        choice = input('Select option: ').strip().lower()
        if choice == '1':
            while True:
                val = input('Enter frequency (e.g. 1.23GHz, 1230MHz, 1230000000Hz): ').strip()
                try:
                    frequency_hz = parse_frequency(val)
                    apply_frequency(handle, frequency_hz)
                    break
                except ValueError:
                    print('Invalid frequency format. Please try again.')
        elif choice == '2':
            while True:
                val = input('Enter level in dBm (e.g. -60.0): ').strip().replace(',', '.')
                try:
                    level_dbm = float(val)
                    apply_level(handle, level_dbm)
                    break
                except Exception:
                    print('Invalid level value. Please enter a valid number.')
        elif choice == '3':
            if not tx_enabled:
                try:
                    vsg.vsgOutputCW(handle)
                    tx_enabled = True
                    print('Single CW transmit enabled (CW output started).')
                except Exception as e:
                    print(f'Failed to enable single CW transmit: {e}')
                # No spectrum plot update here
                try:
                    vsg.vsgAbort(handle)
                    tx_enabled = False
                    print('Single CW transmit disabled (output stopped).')
                except Exception as e:
                    print(f'Failed to disable single CW transmit: {e}')
        elif choice == '4':
            while True:
                val = input('Enter sample rate (e.g. 10e6 for 10 MHz): ').strip().replace(',', '.')
                try:
                    sample_rate = float(val)
                    if sample_rate > 0:
                        print(f'Sample rate set to {sample_rate/1e6:.3f} MHz')
                        break
                    else:
                        print('Sample rate must be positive.')
                except Exception:
                    print('Invalid sample rate value. Please enter a valid number.')
        elif choice == '5':
            print('Add a CW spike (signal)')
            while True:
                try:
                    rel_freq = input('Enter signal offset from center (Hz, e.g. 0, 1e6, -2e6): ').strip().replace(',', '.')
                    rel_freq = float(rel_freq)
                    if abs(rel_freq) > sample_rate/2:
                        print('Offset must be within +/- half the sample rate.')
                        continue
                    break
                except Exception:
                    print('Invalid frequency offset. Please enter a valid number.')
            while True:
                try:
                    gain = input('Enter signal gain (dBm, e.g. -30): ').strip().replace(',', '.')
                    gain = float(gain)
                    break
                except Exception:
                    print('Invalid gain. Please enter a valid number.')
            signals.append({'type': 'cw', 'freq_offset': rel_freq, 'gain_dbm': gain, 'enabled': True})
            print(f'Added CW signal: offset {rel_freq/1e6:.3f} MHz, gain {gain:.1f} dBm, enabled')
            # No spectrum plot update here
        elif choice == '6':
            print('Add a PSK signal (BPSK/QPSK/8PSK)')
            try:
                rel_freq = input('Enter signal offset from center (Hz, e.g. 0, 1e6, -2e6): ').strip()
                rel_freq = float(rel_freq)
                if abs(rel_freq) > sample_rate/2:
                    print('Offset must be within +/- half the sample rate.')
                    return
                gain = input('Enter signal gain (dBm, e.g. -30): ').strip()
                gain = float(gain)
                while True:
                    mod_type = input('Enter PSK type (bpsk, qpsk, 8psk): ').strip().lower()
                    if mod_type in ['bpsk', 'qpsk', '8psk']:
                        break
                    else:
                        print('Invalid PSK type. Please enter one of: bpsk, qpsk, 8psk')
                # RRC roll-off input with re-prompt
                while True:
                    rolloff_str = input('Enter RRC roll-off (0.2, 0.25, 0.3, 0.35): ').strip().replace(',', '.')
                    try:
                        rolloff = float(rolloff_str)
                        if rolloff in [0.2, 0.25, 0.3, 0.35]:
                            break
                        else:
                            print('Invalid roll-off value. Please enter one of: 0.2, 0.25, 0.3, 0.35')
                    except Exception:
                        print('Invalid roll-off value. Please enter a valid number.')
                # Symbol rate input with re-prompt
                while True:
                    symrate_str = input('Enter symbol rate (symbols/sec, e.g. 1e6): ').strip().replace(',', '.')
                    try:
                        symrate = float(symrate_str)
                        if symrate > 0:
                            break
                        else:
                            print('Symbol rate must be positive.')
                    except Exception:
                        print('Invalid symbol rate. Please enter a valid number.')
                signals.append({'type': 'psk', 'mod_type': mod_type, 'freq_offset': rel_freq, 'gain_dbm': gain, 'rolloff': rolloff, 'symrate': symrate, 'enabled': True})
                print(f'Added {mod_type.upper()} signal: offset {rel_freq/1e6:.3f} MHz, gain {gain:.1f} dBm, rolloff {rolloff}, symrate {symrate}, enabled')
                # No spectrum plot update here
            except Exception:
                print('Invalid input for PSK signal.')
        elif choice == '7':
            print(f'Frequency: {frequency_hz/1e6:.6f} MHz')
            print(f'Level: {level_dbm:.1f} dBm')
            print(f'Sample Rate: {sample_rate/1e6:.3f} MHz')
            print(f'Transmit: {"ON" if tx_enabled else "OFF"}')
            if signals:
                print('Signals:')
                for i, sig in enumerate(signals):
                    status = 'ENABLED' if sig.get('enabled', True) else 'DISABLED'
                    if sig['type'] == 'cw':
                        print(f'  {i+1}) CW: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, {status}')
                    elif sig['type'] == 'psk':
                        print(f'  {i+1}) {sig["mod_type"].upper()}: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, RRC: {sig["rolloff"]}, SymRate: {sig["symrate"]}, {status}')
            else:
                print('No signals defined.')
        elif choice == '8':
            if not signals:
                print('No signals to edit.')
                continue
            print('Select signal to edit:')
            for i, sig in enumerate(signals):
                status = 'ENABLED' if sig.get('enabled', True) else 'DISABLED'
                if sig['type'] == 'cw':
                    desc = f'CW: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, {status}'
                elif sig['type'] == 'psk':
                    desc = f'{sig["mod_type"].upper()}: Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, RRC: {sig["rolloff"]}, SymRate: {sig["symrate"]}, {status}'
                print(f'  {i+1}) {desc}')
            while True:
                try:
                    idx = int(input('Enter signal number: ')) - 1
                    if idx < 0 or idx >= len(signals):
                        print('Invalid signal number. Please try again.')
                        continue
                    break
                except Exception:
                    print('Invalid input. Please enter a valid number.')
            sig = signals[idx]
            print('Edit options:')
            print('  1) Edit frequency offset')
            print('  2) Edit gain')
            if sig['type'] == 'psk':
                print('  3) Edit RRC roll-off')
                print('  4) Edit symbol rate')
                print('  5) Enable/disable')
                print('  6) Remove signal')
                print('  q) Cancel')
            else:
                print('  3) Enable/disable')
                print('  4) Remove signal')
                print('  q) Cancel')
            opt = input('Select option: ').strip().lower()
            changed = False
            if opt == '1':
                while True:
                    val = input('Enter new offset from center (Hz): ').strip().replace(',', '.')
                    try:
                        new_offset = float(val)
                        if abs(new_offset) > sample_rate/2:
                            print('Offset must be within +/- half the sample rate.')
                        else:
                            sig['freq_offset'] = new_offset
                            print('Offset updated.')
                            changed = True
                            break
                    except Exception:
                        print('Invalid offset. Please enter a valid number.')
            elif opt == '2':
                while True:
                    val = input('Enter new gain (dBm): ').strip().replace(',', '.')
                    try:
                        sig['gain_dbm'] = float(val)
                        print('Gain updated.')
                        changed = True
                        break
                    except Exception:
                        print('Invalid gain. Please enter a valid number.')
            elif sig['type'] == 'psk' and opt == '3':
                while True:
                    val = input('Enter new RRC roll-off (0.2, 0.25, 0.3, 0.35): ').strip().replace(',', '.')
                    try:
                        rolloff = float(val)
                        if rolloff in [0.2, 0.25, 0.3, 0.35]:
                            sig['rolloff'] = rolloff
                            print('RRC roll-off updated.')
                            changed = True
                            break
                        else:
                            print('Invalid roll-off value. Please enter one of: 0.2, 0.25, 0.3, 0.35')
                    except Exception:
                        print('Invalid roll-off. Please enter a valid number.')
            elif sig['type'] == 'psk' and opt == '4':
                while True:
                    val = input('Enter new symbol rate (symbols/sec): ').strip().replace(',', '.')
                    try:
                        symrate = float(val)
                        if symrate > 0:
                            sig['symrate'] = symrate
                            print('Symbol rate updated.')
                            changed = True
                            break
                        else:
                            print('Symbol rate must be positive.')
                    except Exception:
                        print('Invalid symbol rate. Please enter a valid number.')
            elif (sig['type'] == 'psk' and opt == '5') or (sig['type'] == 'cw' and opt == '3'):
                sig['enabled'] = not sig.get('enabled', True)
                print('Signal is now ' + ('ENABLED' if sig['enabled'] else 'DISABLED'))
                changed = True
            elif (sig['type'] == 'psk' and opt == '6') or (sig['type'] == 'cw' and opt == '4'):
                signals.pop(idx)
                print('Signal removed.')
                changed = True
            elif opt == 'q':
                print('Edit cancelled.')
            else:
                print('Unknown edit option.')
            # No spectrum plot update here

        elif choice == '9':
            # Toggle composite IQ transmit
            if not tx_enabled:
                print('Generating and transmitting composite IQ (CW + PSK, loops)...')
                import os
                import sys
                vsg_api_path = os.path.join(os.path.dirname(__file__), 'vsg60_series', 'examples', 'python', 'vsgdevice')
                if vsg_api_path not in sys.path:
                    sys.path.insert(0, vsg_api_path)
                try:
                    import vsg_api
                except ImportError:
                    print('vsg_api not found. Please ensure vsg_api.py is accessible.')
                    continue
                iq = generate_composite_iq(signals, sample_rate)
                # Interleave I/Q for VSG: [I0, Q0, I1, Q1, ...]
                iq_interleaved = np.empty(2 * len(iq), dtype=np.float32)
                iq_interleaved[0::2] = np.real(iq)
                iq_interleaved[1::2] = np.imag(iq)
                # Download and play (loop)
                status = vsg_api.vsg_repeat_waveform(handle, iq_interleaved, len(iq))
                if status['status'] == 0:
                    tx_enabled = True
                    print('Composite IQ transmit enabled and looping.')
                else:
                    print(f'VSG error: {status}')
            else:
                try:
                    vsg.vsgAbort(handle)
                    tx_enabled = False
                    print('Composite IQ transmit disabled (output stopped).')
                except Exception as e:
                    print(f'Failed to disable composite IQ transmit: {e}')
            # Always update spectrum plot after toggling transmit
            # No spectrum plot update here
        elif choice == '10':
            print('Plotting spectrum of current composite IQ...')
            try:
                iq = generate_composite_iq(signals, sample_rate)
                print(f'DEBUG: IQ max={np.max(np.abs(iq))}, min={np.min(np.abs(iq))}')
                # Compute FFT and save to file
                spectrum = np.fft.fftshift(np.fft.fft(iq))
                print(f'DEBUG: Spectrum max={np.max(np.abs(spectrum))}, min={np.min(np.abs(spectrum))}')
                freqs = np.fft.fftshift(np.fft.fftfreq(len(iq), d=1.0/sample_rate))
                np.savez('spectrum_data.npz', spectrum=spectrum, freqs=freqs, sample_rate=sample_rate)
                # Launch plot window with file argument
                import subprocess, sys, os
                subprocess.Popen([
                    sys.executable,
                    os.path.join(os.path.dirname(__file__), 'vsg_plot.py'),
                    'spectrum_data.npz'
                ])
                print('Launched spectrum plot window.')
            except Exception as e:
                print(f'Failed to plot spectrum: {e}')

        elif choice == 'q':
            break
        else:
            print('Unknown option.')

    # Cleanup
    try:
        if tx_enabled:
            vsg.vsgAbort(handle)
    except Exception:
        pass
    vsg.vsgCloseDevice(handle)
    print('Device closed.')


if __name__ == '__main__':
    main()

