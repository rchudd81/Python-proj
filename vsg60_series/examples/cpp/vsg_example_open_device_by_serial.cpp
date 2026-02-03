#include "vsg_api.h"

#include <cstdio>

void vsg_example_open_device_by_serial()
{
    int serials[8];
    int deviceCount = 8;
    vsgGetDeviceList(serials, &deviceCount);

    // Open the first device in the list, get handle, check open result
    int handle;
    VsgStatus status = vsgOpenDeviceBySerial(&handle, serials[0]);
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