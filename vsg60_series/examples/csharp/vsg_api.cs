using System;
using System.Runtime.InteropServices;

/*
 * The C# API class for the VSG60 series devices is a class of static members and methods which
 * are simply a 1-to-1 mapping of the C API. This makes is easy to modify and look up
 * functions in the API manual.
 */

enum VsgTimebaseState 
{
    vsgTimebaseStateInternal = 0, // default
    vsgTimebaseStateExternal = 1
};

enum VsgBool 
{
    vsgFalse = 0,
    vsgTrue = 1
};

enum VsgStatus 
{
    // Internal use only
    vsgFileIOErr = -1000,
    vsgMemErr = -999,

    vsgInvalidOperationErr = -11,

    // Indicates the auto pattern output is already active
    vsgWaveformAlreadyActiveErr = -10,
    vsgWaveformNotActiveErr = -9,

    vsgUsbXferErr = -5,
    vsgInvalidParameterErr = -4,
    vsgNullPtrErr = -3,
    vsgInvalidDeviceErr = -2,
    vsgDeviceNotFoundErr = -1,

    vsgNoError = 0,

    vsgAlreadyFlushed = 1,
    vsgSettingClamped = 2
};

class vsg_api
{
    public static int VSG_MAX_DEVICES = 8;

    public static double VSG60_MIN_FREQ = 30.0e6;
    public static double VSG60_MAX_FREQ = 6.0e9;

    public static double VSG_MIN_SAMPLE_RATE = 12.5e3;
    public static double VSG_MAX_SAMPLE_RATE = 54.0e6;

    public static double VSG_MIN_LEVEL = -120.0;
    public static double VSG_MAX_LEVEL = 10.0;

    public static double VSG_MIN_IQ_OFFSET = -1024;
    public static double VSG_MAX_IQ_OFFSET = 1024;

    public static double VSG_MIN_TRIGGER_LENGTH = 0.1e-6; // 100ns
    public static double VSG_MAX_TRIGGER_LENGTH = 1.0; // 100ms

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetDeviceList(int[] serials, ref int count);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgOpenDevice(ref int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgOpenDeviceBySerial(ref int handle, int serialNumber);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgCloseDevice(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgPreset(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgRecal(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgAbort(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetSerialNumber(int handle, ref int serial);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetFirmwareVersion(int handle, ref int version);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetCalDate(int handle, ref uint lastCalDate);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgReadTemperature(int handle, ref float temp);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetRFOutputState(int handle, VsgBool enabled);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetRFOutputState(int handle, ref VsgBool enabled);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetTimebase(int handle, VsgTimebaseState state);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetTimebase(int handle, ref VsgTimebaseState state);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetTimebaseOffset(int handle, double ppm);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetTimebaseOffset(int handle, ref double ppm);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetFrequency(int handle, double frequency);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetFrequency(int handle, ref double frequency);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetSampleRate(int handle, double sampleRate);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetSampleRate(int handle, ref double sampleRate);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetLevel(int handle, double level);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetLevel(int handle, ref double level);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetAtten(int handle, int atten);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetIQScale(int handle, ref double iqScale);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetIQOffset(int handle, short iOffset, short qOffset);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetIQOffset(int handle, ref short iOffset, ref short qOffset);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetDigitalTuning(int handle, VsgBool enabled);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetDigitalTuning(int handle, ref VsgBool enabled);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSetTriggerLength(int handle, double seconds);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetTriggerLength(int handle, ref double seconds);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSubmitIQ(int handle, float[] iq, int len);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgSubmitTrigger(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgFlush(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgFlushAndWait(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgOutputWaveform(int handle, float[] iq, int len);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgRepeatWaveform(int handle, float[] iq, int len);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgOutputCW(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgIsWaveformActive(int handle, ref VsgBool active);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern VsgStatus vsgGetUSBStatus(int handle);

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    public static extern void vsgEnablePowerSavingCpuMode(VsgBool enabled);
    
    public static string vsgGetAPIString()
    {
        IntPtr strPtr = vsgGetAPIVersion();
        return System.Runtime.InteropServices.Marshal.PtrToStringAnsi(strPtr);
    }

    public static string vsgGetStatusString(VsgStatus status)
    {
        IntPtr strPtr = vsgGetErrorString(status);
        return System.Runtime.InteropServices.Marshal.PtrToStringAnsi(strPtr);
    }

    // Call string variants above instead
    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr vsgGetAPIVersion();

    [DllImport("vsg_api.dll", CallingConvention = CallingConvention.Cdecl)]
    private static extern IntPtr vsgGetErrorString(VsgStatus status);
}
