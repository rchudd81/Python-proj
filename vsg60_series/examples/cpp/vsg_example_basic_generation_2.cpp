/** [basicGenExample] */

/*
 * This example illustrates generating a pulse signal at a specific freq and level.
 * This example is fully standalone.
 */ 

#include "vsg_api.h"

#include <cstdio>
#include <vector> 

#include <Windows.h>

struct Cplx32f { 
    float re, im; 
};

void vsg_example_basic_generation_2()
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

    // Create pulse with specific width and period, then continually loop the pulsed signal
    const Cplx32f cplxOne = {1.0, 0.0}, cplxZero = {0.0, 0.0};
    std::vector<Cplx32f> iq; // The I/Q waveform

    const double pulseWidth = 1.0e-6; // 1us
    const double pulsePeriod = 10.0e-6; // 10us
    const int pulseOnSamples = pulseWidth * sampleRate;
    const int pulseOffSamples = (pulsePeriod - pulseWidth) * sampleRate;

    for(int i = 0; i < pulseOnSamples; i++) {
        iq.push_back(cplxOne);
    }
    for(int i = 0; i < pulseOffSamples; i++) {
        iq.push_back(cplxZero);
    }

    vsgRepeatWaveform(handle, (float*)&iq[0], iq.size());

    // Will transmit until you close the device or abort
    Sleep(5000);

    // Stop waveform
    vsgAbort(handle);

    // Done with device
    vsgCloseDevice(handle);
}

/** [basicGenExample] */
