% This example illustrates transmitting a CW signal using 
%  the VSG api

% Open the device and verify connection
vsg = VSG60;
fprintf('Open status: %s\n', vsg.getstatusstring());
fprintf('Serial Number: %d\n', vsg.SerialNumber);

% Configuration parameters
vsg.Frequency = 1.0e9;
vsg.SampleRate = 50.0e6;
vsg.Level = -10.0;

% Output complex {1,0} for 1 second
% This generates a CW
iq = complex(1, 0);
% Since we are providing a single sample, set to repeat to continually
%  transmit this sample
vsg.transmit(iq, 'repeat');
% Wait 1 second
pause(1);
% Stop transmit
vsg.stop();
