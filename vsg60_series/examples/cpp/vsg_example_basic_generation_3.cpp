/*
 * This example illustrates generating an offset CW tone and playing the waveform once
 * This example is fully standalone.
 */ 

#include "vsg_api.h"

#include <cstdio>
#include <vector> 

#include <Windows.h>

struct Cplx32f { 
    float re, im; 
};

void vsg_example_basic_generation_3()
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
    const double sampleRate = 1.0e6; // samples per second
    const double level = -10.0; // dBm

    vsgSetFrequency(handle, freq);
    vsgSetLevel(handle, level);
    vsgSetSampleRate(handle, sampleRate);

    // Create N second offset CW
    const double waveformLength = 5;
    const double offsetFreq = 0.123;
    std::vector<Cplx32f> iq(waveformLength * sampleRate); // The I/Q waveform

    for(int i = 0; i < iq.size(); i++) {
        iq[i].re = cos(i * offsetFreq * 6.2831853);
        iq[i].im = sin(i * offsetFreq * 6.2831853);
    }

    printf("Tone at %.6fMHz\n", (freq + sampleRate * offsetFreq) / 1.0e6);

    // Generate waveform once, will block until complete
    vsgOutputWaveform(handle, (float*)&iq[0], iq.size());

    // Done with device
    vsgCloseDevice(handle);
}