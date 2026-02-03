#include "vsg_api.h"

#include <cstdio>

void vsg_example_open_device()
{
    // Open device, get handle, check open result
    int handle;
    VsgStatus status = vsgOpenDevice(&handle);
    if(status < vsgNoError) {
        printf("Error: %s\n", vsgGetErrorString(status));
        return;
    }

    // Get basic information about device
    int serial, fwVersion;
    vsgGetSerialNumber(handle, &serial);
    vsgGetFirmwareVersion(handle, &fwVersion);
    printf("VSG60 Serial Number %d, Firmware Version %d\n", serial, fwVersion);

    // Done with device
    vsgCloseDevice(handle);
}