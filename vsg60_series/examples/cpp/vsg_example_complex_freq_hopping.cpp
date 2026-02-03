/** [complexGenExample] */

/*
 * This example illustrates how to use the streaming function of the API
 *  to generate a complex frqeuency hopping CW signal.
 * This example is fully standalone.
 */ 

#include "vsg_api.h"

#include <cstdio>
#include <vector> 

#include <Windows.h>

struct Cplx32f { 
    float re, im; 
};

static double RandBetween(double f1, double f2)
{
    double r = (double)rand() / (double)RAND_MAX;
    return f1 + r * (f2 - f1);
}

void vsg_example_complex_freq_hopping()
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

    vsgSetLevel(handle, level);
    vsgSetSampleRate(handle, sampleRate);

    // Each frequency switch takes 200us
    // We will output an 800us CW at each frequency for a hop period of 1ms
    std::vector<Cplx32f> iq(800.0e-6 * sampleRate);

    for(int i = 0; i < iq.size(); i++) {
        iq[i].re = 1.0;
        iq[i].im = 0.0;
    }

    // Number of 1ms hops to perform
    int hops = 1000;

    while(hops-- > 0) {
        vsgSetFrequency(handle, RandBetween(990.0e6, 1010.0e6));
        vsgSubmitIQ(handle, (float*)&iq[0], iq.size());
    }

    vsgFlushAndWait(handle);

    // Done with device
    vsgCloseDevice(handle);
}

/** [complexGenExample] */
