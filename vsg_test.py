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
frequency = c_double(1.0e9)  # 1 GHz
amplitude = c_double(-10.0)  # -10 dBm

# 4. Detect and Open Device
print("Attempting to find VSG60 device...")
status = vsg.vsgOpenDevice(byref(handle))

if status == 0:  # vsgNoError
    print(f"Success! Device opened with handle: {handle.value}")
    
    # 5. Configure CW Tone
    # Set the frequency and amplitude
    vsg.vsgSetFrequency(handle, frequency)
    vsg.vsgSetLevel(handle, amplitude)
    
    # Generate the CW tone
    print(f"Generating CW tone at 1 GHz, -10 dBm...")
    vsg.vsgOutputCW(handle)
    
    input("Press Enter to stop the tone and close the device...")
    
    # 6. Clean up
    vsg.vsgAbort(handle)
    vsg.vsgCloseDevice(handle)
    print("Device closed.")
else:
    print(f"Could not find or open device. Error code: {status}")
    