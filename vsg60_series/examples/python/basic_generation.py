# -*- coding: utf-8 -*-

# This example generates a basic CW signal.

from vsgdevice.vsg_api import *
from time import sleep

def generate_iq():
    # Open device
    handle = vsg_open_device()["handle"]

    # Configure generator
    freq = 1.0e9 # Hz
    sample_rate = 50.0e6 # samples per second
    level = -20.0 # dBm

    vsg_set_frequency(handle, freq)
    vsg_set_level(handle, level)
    vsg_set_sample_rate(handle, sample_rate)

    # Output CW, single I/Q value of {1,0}
    # This is equivalent to calling vsgOutputCW
    iq = numpy.zeros(2).astype(numpy.float32)
    iq[0] = 1
    vsg_repeat_waveform(handle, iq, 1)

    # Will transmit until you close the device or abort
    sleep(5)

    # Stop waveform
    vsg_abort(handle)

    # Done with device
    vsg_close_device(handle)

if __name__ == "__main__":
    generate_iq()
