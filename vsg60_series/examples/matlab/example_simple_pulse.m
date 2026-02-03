% This example illustrates transmitting a pulsed waveform with the
%  VSG API.

% Open the device and verify connection
vsg = VSG60;
fprintf('Open status: %s\n', vsg.getstatusstring());
fprintf('Serial Number: %d\n', vsg.SerialNumber);

% Configuration parameters
vsg.Frequency = 1.0e9;
vsg.SampleRate = 50.0e6;
vsg.Level = -10.0;

% Pulse parameters
pWidth = 1.0e-6;
pPeriod = 10.0e-6;

% Create pulsed waveform
% Real channel only
waveform = ones(1, pWidth * vsg.SampleRate);
waveform = [waveform, zeros(1, (pPeriod-pWidth) * vsg.SampleRate)];

% Set up waveform on repeat
vsg.transmit(waveform, 'repeat');
% Wait 1 second
pause(1);
% Stop transmit
vsg.stop();
