using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading;
using System.Threading.Tasks;

class vsg_example
{
    // Small function which illustrates using the C# API to
    // generate a basic signal with the VSG60 series device
    public void Run()
    {
        // Open device, get handle, check open result
        int handle = -1;
        VsgStatus status = vsg_api.vsgOpenDevice(ref handle);
        if (status < VsgStatus.vsgNoError)
        {
            Console.WriteLine("Error: " + vsg_api.vsgGetStatusString(status));
            return;
        }

        // Print off information about device
        int serialNumber = 0;
        vsg_api.vsgGetSerialNumber(handle, ref serialNumber);
        Console.WriteLine("Serial: " + serialNumber);

        int firmware = 0;
        vsg_api.vsgGetFirmwareVersion(handle, ref firmware);
        Console.WriteLine("Firmware Version: " + firmware);

        // Configure generator
        const double freq = 1.0e9; // Hz
        const double sampleRate = 50.0e6; // samples per second
        const double level = -20.0; // dBm

        vsg_api.vsgSetFrequency(handle, freq);
        vsg_api.vsgSetLevel(handle, level);
        vsg_api.vsgSetSampleRate(handle, sampleRate);

        // Output CW, single I/Q value of {1,0}
        // This is equivalent to calling vsgOutputCW
        //Cplx32f iq = { 1.0, 0.0 };
        Console.WriteLine("Generating signal..");
        float[] iq = { 1, 0 };
        vsg_api.vsgRepeatWaveform(handle, iq, 1);

        // Will transmit until you close the device or abort
        Thread.Sleep(5000);

        // Stop waveform
        vsg_api.vsgAbort(handle);

        // Done with device
        vsg_api.vsgCloseDevice(handle);
    }
}
