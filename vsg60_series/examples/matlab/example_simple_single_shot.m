% This example shows how to output a waveform once using the VSG API

% Open the device and verify connection
vsg = VSG60;
fprintf('Open status: %s\n', vsg.getstatusstring());
fprintf('Serial Number: %d\n', vsg.SerialNumber);

% Configuration parameters
vsg.Frequency = 1.0e9;
vsg.SampleRate = 20.0e3;
vsg.Level = -10.0;

% Create raised cosine waveform
% Length in seconds
waveformLength = 0.01;
waveformSamples = vsg.SampleRate * waveformLength;
x = linspace(-pi, pi, waveformSamples);
waveform = (cos(x) + 1) / 2;

% Play waveform
% Waveform is output once
vsg.transmit(waveform, 'once');

