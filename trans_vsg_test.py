import os
import ctypes
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


def print_menu(freq, lvl, tx_enabled, sample_rate):
    print('\nVSG CLI Menu')
    print('-------------')
    print(f'1) Set frequency (current: {freq/1e6:.6f} MHz)')
    print(f'2) Set level/gain (current: {lvl:.1f} dBm)')
    print(f'3) Toggle transmit (currently: {"ON" if tx_enabled else "OFF"})')
    print(f'4) Set sample rate (current: {sample_rate/1e6:.3f} MHz)')
    print('5) Add signal (CW spike)')
    print('6) Show settings/signals')
    print('7) Edit/remove/enable/disable signal')
    print('q) Quit')


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
    signals = []  # Each signal: dict with 'freq_offset', 'gain_dbm', 'enabled'

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
        print_menu(frequency_hz, level_dbm, tx_enabled, sample_rate)
        choice = input('Select option: ').strip().lower()
        if choice == '1':
            val = input('Enter frequency (e.g. 1.23GHz, 1230MHz, 1230000000Hz): ').strip()
            try:
                frequency_hz = parse_frequency(val)
                apply_frequency(handle, frequency_hz)
            except ValueError:
                print('Invalid frequency format.')
        elif choice == '2':
            val = input('Enter level in dBm (e.g. -60.0): ').strip()
            try:
                level_dbm = float(val)
                apply_level(handle, level_dbm)
            except Exception:
                print('Invalid level value.')
        elif choice == '3':
            if not tx_enabled:
                try:
                    vsg.vsgOutputCW(handle)
                    tx_enabled = True
                    print('Transmit enabled (CW output started).')
                except Exception as e:
                    print(f'Failed to enable transmit: {e}')
            else:
                try:
                    vsg.vsgAbort(handle)
                    tx_enabled = False
                    print('Transmit disabled (output stopped).')
                except Exception as e:
                    print(f'Failed to disable transmit: {e}')
        elif choice == '4':
            val = input('Enter sample rate (e.g. 10e6 for 10 MHz): ').strip()
            try:
                sample_rate = float(val)
                print(f'Sample rate set to {sample_rate/1e6:.3f} MHz')
            except Exception:
                print('Invalid sample rate value.')
        elif choice == '5':
            print('Add a CW spike (signal)')
            try:
                rel_freq = input('Enter signal offset from center (Hz, e.g. 0, 1e6, -2e6): ').strip()
                rel_freq = float(rel_freq)
                if abs(rel_freq) > sample_rate/2:
                    print('Offset must be within +/- half the sample rate.')
                    continue
                gain = input('Enter signal gain (dBm, e.g. -30): ').strip()
                gain = float(gain)
                signals.append({'freq_offset': rel_freq, 'gain_dbm': gain, 'enabled': True})
                print(f'Added signal: offset {rel_freq/1e6:.3f} MHz, gain {gain:.1f} dBm, enabled')
            except Exception:
                print('Invalid input for signal.')
        elif choice == '6':
            print(f'Frequency: {frequency_hz/1e6:.6f} MHz')
            print(f'Level: {level_dbm:.1f} dBm')
            print(f'Sample Rate: {sample_rate/1e6:.3f} MHz')
            print(f'Transmit: {"ON" if tx_enabled else "OFF"}')
            if signals:
                print('Signals:')
                for i, sig in enumerate(signals):
                    status = 'ENABLED' if sig.get('enabled', True) else 'DISABLED'
                    print(f'  {i+1}) Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, {status}')
            else:
                print('No signals defined.')
        elif choice == '7':
            if not signals:
                print('No signals to edit.')
                continue
            print('Select signal to edit:')
            for i, sig in enumerate(signals):
                status = 'ENABLED' if sig.get('enabled', True) else 'DISABLED'
                print(f'  {i+1}) Offset: {sig["freq_offset"]/1e6:.3f} MHz, Gain: {sig["gain_dbm"]:.1f} dBm, {status}')
            try:
                idx = int(input('Enter signal number: ')) - 1
                if idx < 0 or idx >= len(signals):
                    print('Invalid signal number.')
                    continue
                sig = signals[idx]
                print('Edit options:')
                print('  1) Edit frequency offset')
                print('  2) Edit gain')
                print('  3) Enable/disable')
                print('  4) Remove signal')
                print('  q) Cancel')
                opt = input('Select option: ').strip().lower()
                if opt == '1':
                    val = input('Enter new offset from center (Hz): ').strip()
                    try:
                        new_offset = float(val)
                        if abs(new_offset) > sample_rate/2:
                            print('Offset must be within +/- half the sample rate.')
                        else:
                            sig['freq_offset'] = new_offset
                            print('Offset updated.')
                    except Exception:
                        print('Invalid offset.')
                elif opt == '2':
                    val = input('Enter new gain (dBm): ').strip()
                    try:
                        sig['gain_dbm'] = float(val)
                        print('Gain updated.')
                    except Exception:
                        print('Invalid gain.')
                elif opt == '3':
                    sig['enabled'] = not sig.get('enabled', True)
                    print('Signal is now ' + ('ENABLED' if sig['enabled'] else 'DISABLED'))
                elif opt == '4':
                    signals.pop(idx)
                    print('Signal removed.')
                elif opt == 'q':
                    print('Edit cancelled.')
                else:
                    print('Unknown edit option.')
            except Exception:
                print('Invalid input.')
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

