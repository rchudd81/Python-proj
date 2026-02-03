/*
 * This example illustrates how to output an external trigger using the
 *   streaming functionality of the API. 
 * Several methods of emitting external triggers are presented.
 * This example is fully standalone.
 */ 

#include "vsg_api.h"

#include <cstdio>
#include <vector> 

#include <Windows.h>

struct Cplx32f { 
    float re, im; 
};

void vsg_example_ext_triggering()
{
    // Open device, get handle, check open result
    int handle;
    VsgStatus status = vsgOpenDevice(&handle);
    if(status < vsgNoError) {
        printf("Error: %s\n", vsgGetErrorString(status));
        return;
    }

    // Configure generator
    const double sampleRate = 50.0e6; // samples per second
    const double level = -10.0; // dBm
    const double freq = 1.0e9; // 1GHz

    vsgSetFrequency(handle, freq);
    vsgSetLevel(handle, level);
    vsgSetSampleRate(handle, sampleRate);

    // We need to allocate and create a waveform we want to output.

    std::vector<Cplx32f> iq(50000);
    // Insert your waveform here
    // For this example, we will output a CW signal that is 1ms long
    for(int i = 0; i < iq.size(); i++) {
        iq[i].re = 1.0;
        iq[i].im = 0.0;
    }

    // Right now the VSG60 is idle

    // We will transmit our waveform, with an external trigger marking the
    //   start of the waveform.
    vsgSubmitTrigger(handle);
    vsgSubmitIQ(handle, (float*)&iq[0], iq.size());
    // This function pushes all queued commands to the device and waits
    //   for the device to finish processing them.
    vsgFlushAndWait(handle);

    // Now lets transmit the waveform with the external trigger marking the
    //   center of the waveform
    vsgSubmitIQ(handle, (float*)&iq[0], iq.size() / 2);
    vsgSubmitTrigger(handle);
    vsgSubmitIQ(handle, (float*)&iq[iq.size() / 2], iq.size() / 2);
    vsgFlushAndWait(handle);

    // Now lets transmit our waveform 10 times back to back with a trigger
    //   marking the beginning of each repitition of the signal.
    // This should look like a CW signal 10ms long with 10 external trigger
    //   events spaced 1ms each.
    for(int i = 0; i < 10; i++) {
        vsgSubmitTrigger(handle);
        vsgSubmitIQ(handle, (float*)&iq[0], iq.size());
    }
    vsgFlushAndWait(handle);

    // Done with device
    vsgCloseDevice(handle);
}