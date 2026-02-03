/*
 * This example illustrates generating a CW signal at a specific freq and level.
 * This example is fully standalone.
 */ 

#include "vsg_api.h"

#include <cstdio>
#include <Windows.h>

struct Cplx32f { 
    float re, im; 
};

void vsg_example_basic_generation_1()
{
    // Open device, get handle, check open result
    int handle;
    VsgStatus status = vsgOpenDevice(&handle);
    if(status < vsgNoError) {
        printf("Error: %s\n", vsgGetErrorString(status));
        return;
    }

    // Configure generator
    const double freq = 1.0e9; // Hz
    const double sampleRate = 50.0e6; // samples per second
    const double level = -10.0; // dBm

    vsgSetFrequency(handle, freq);
    vsgSetLevel(handle, level);
    vsgSetSampleRate(handle, sampleRate);

    // Output CW, single I/Q value of {1,0}
    // This is equivalent to calling vsgOutputCW
    Cplx32f iq = {1.0, 0.0};
    vsgRepeatWaveform(handle, (float*)&iq, 1);

    // Will transmit until you close the device or abort
    Sleep(5000);

    // Stop waveform
    vsgAbort(handle);

    // Done with device
    vsgCloseDevice(handle);
}