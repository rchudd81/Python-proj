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


def print_menu(freq, lvl, tx_enabled):
    print('\nVSG CLI Menu')
    print('-------------')
    print(f'1) Set frequency (current: {freq/1e6:.6f} MHz)')
    print(f'2) Set level/gain (current: {lvl:.1f} dBm)')
    print(f'3) Toggle transmit (currently: {"ON" if tx_enabled else "OFF"})')
    print('4) Show settings')
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
        print_menu(frequency_hz, level_dbm, tx_enabled)
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
            print(f'Frequency: {frequency_hz/1e6:.6f} MHz')
            print(f'Level: {level_dbm:.1f} dBm')
            print(f'Transmit: {"ON" if tx_enabled else "OFF"}')
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

