#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#
# SPDX-License-Identifier: GPL-3.0
#
# GNU Radio Python Flow Graph
# Title: Not titled yet
# GNU Radio version: 3.10.12.0

from gnuradio import blocks
import pmt
from gnuradio import gr
from gnuradio.filter import firdes
from gnuradio.fft import window
import sys
import signal
from argparse import ArgumentParser
from gnuradio.eng_arg import eng_float, intx
from gnuradio import eng_notation
from gnuradio import soapy
import threading




class vsg_file_playback(gr.top_block):

    def __init__(self):
        gr.top_block.__init__(self, "Not titled yet", catch_exceptions=True)
        self.flowgraph_started = threading.Event()

        ##################################################
        # Variables
        ##################################################
        self.samp_rate = samp_rate = 32000

        ##################################################
        # Blocks
        ##################################################

        self.soapy_custom_sink_0 = None
        dev = 'driver=' + 'vsg'
        stream_args = ''
        tune_args = ['']
        settings = ['']
        self.soapy_custom_sink_0 = soapy.sink(dev, "fc32",
                                1, '',
                                stream_args, tune_args, settings)
        self.soapy_custom_sink_0.set_sample_rate(0, samp_rate)
        self.soapy_custom_sink_0.set_bandwidth(0, 0)
        self.soapy_custom_sink_0.set_antenna(0, 'TX')
        self.soapy_custom_sink_0.set_frequency(0, 1e9)
        self.soapy_custom_sink_0.set_frequency_correction(0, 0)
        self.soapy_custom_sink_0.set_gain(0, 10)
        self.soapy_custom_sink_0.set_dc_offset(0, 0)
        self.soapy_custom_sink_0.set_iq_balance(0, 0)
        self.blocks_file_source_0 = blocks.file_source(gr.sizeof_gr_complex*1, 'C:\\Users\\Richard\\SatEMU\\TransEMU\\my-sdr-tools\\iq\\psk_BPSK_0Hz_1200sym_ro0.35.sdriq', True, 0, 0)
        self.blocks_file_source_0.set_begin_tag(pmt.PMT_NIL)


        ##################################################
        # Connections
        ##################################################
        self.connect((self.blocks_file_source_0, 0), (self.soapy_custom_sink_0, 0))


    def get_samp_rate(self):
        return self.samp_rate

    def set_samp_rate(self, samp_rate):
        self.samp_rate = samp_rate




def main(top_block_cls=vsg_file_playback, options=None):
    tb = top_block_cls()

    def sig_handler(sig=None, frame=None):
        tb.stop()
        tb.wait()

        sys.exit(0)

    signal.signal(signal.SIGINT, sig_handler)
    signal.signal(signal.SIGTERM, sig_handler)

    tb.start()
    tb.flowgraph_started.set()

    try:
        input('Press Enter to quit: ')
    except EOFError:
        pass
    tb.stop()
    tb.wait()


if __name__ == '__main__':
    main()
