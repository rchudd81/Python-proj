classdef VSG60
    % The VSG60 object allows you to interface, configure, and generate
    %  waveforms using the Signal Hound VSG60 device. This object makes it
    %  easy to transmit custom real and complex waveforms using the VSG60
    %  device.
    
    properties
        % Can be read to determine if the device has been successfully
        %  initialized.
        IsOpen = false;
        % Valid to read if the device was opened successfully.
        SerialNumber = -1
        % Center frequency of the output
        Frequency = 1.0e9
        % Sample rate 
        SampleRate = 50.0e6
        % Output power in dBm
        Level = 0.0
        % Last status reported by the API
        LastStatus = 0;
    end
    
    properties (Access = private)
        % API handle to device
        DeviceHandle = -1
    end
    
    methods
        % Constructor
        function obj = VSG60()
            % Establish connection with a VSG60
            
            if not(libisloaded('vsg_api'))
                loadlibrary('vsg_api', 'vsg_api.h');
                % Test the library is loaded before continuing
                if(not(libisloaded('vsg_api')))
                    return;
                end
            else 
                % Libary is already loaded. As a precaution, close all
                % possible handles It's possible the last execution ended
                % without properly closing the device, so just free all
                % resources and potentially opened devices. If at some
                % point you want to target multiple devices with this
                % class, you will need to either remove this logic or write
                % more targetted logic, i.e. close only the device you are
                % interested in, or maybe, look to see if a device is
                % already open and just return that?
                for i = (0 : 7)
                    calllib('vsg_api', 'vsgCloseDevice', i);
                end               
            end
            
            % Open device
            handleptr = libpointer('int32Ptr', -1);
            obj.LastStatus = calllib('vsg_api', 'vsgOpenDevice', handleptr);
            if(obj.LastStatus < 0)
                obj.DeviceHandle = -1;
                return;
            else
                obj.DeviceHandle = handleptr.value;
            end
            
            % Get serial number
            serialptr = libpointer('int32Ptr', -1);
            
            obj.LastStatus = calllib('vsg_api', 'vsgGetSerialNumber', obj.DeviceHandle, serialptr);
            if(obj.LastStatus >= 0)
                obj.SerialNumber = serialptr.value;
            end
        end
        
        % Destructor
        function delete(obj)
           calllib('vsg_api', 'vsgCloseDevice', obj.DeviceHandle); 
        end
        
        % Main transmit function
        function transmit(obj, waveform, mode)
            % Output a provided waveform
            % Waveform: Waveform to output, can either be a
            %  vector of real values or an vector of complex values.
            %  If an array of reals is provided, the imaginary channel 
            %  is assumed to be zero.
            % Should not be a matrix.
            % Can be either a row vector or column vector.
            % Mode: Specify whether to transmit the waveform once or
            %  on repeat. If no argument is provided, 'once' is assumed.
            %  Valid values are 'once' and 'repeat'
            if(nargin < 3) 
                mode = 'once';
            end
            
            if(iscolumn(waveform)) 
               waveform = waveform.'; 
            end
            
            if(length(waveform) < 1) 
                return;
            end
            
            % If real, then add zero imaginary component
            if(isreal(waveform)) 
                waveform = complex(waveform, zeros(1, length(waveform)));
            end
                
            % Create flattened array to store interleaved
            %  singlePtr array the API is expecting.
            count = length(waveform);
            tmp = reshape([real(waveform); imag(waveform)], 1,[]);
            iqptr = libpointer('singlePtr', tmp);
            
            calllib('vsg_api', 'vsgSetFrequency', obj.DeviceHandle, obj.Frequency);
            calllib('vsg_api', 'vsgSetLevel', obj.DeviceHandle, obj.Level);
            calllib('vsg_api', 'vsgSetSampleRate', obj.DeviceHandle, obj.SampleRate);        
            
            if(strcmp(mode, 'repeat'))
                obj.LastStatus = calllib('vsg_api', ...
                    'vsgRepeatWaveform', obj.DeviceHandle, iqptr, count);
            else 
                obj.LastStatus = calllib('vsg_api', ...
                    'vsgOutputWaveform', obj.DeviceHandle, iqptr, count);                
            end
        end
        
        % Stop waveform output
        function stop(obj)
            % End any active signal generation
            % If not generating, this function has no effect
           calllib('vsg_api', 'vsgAbort', obj.DeviceHandle); 
        end

        % Error info
        function str = getstatusstring(obj)
            % Returns a string [1xN] char.
            % Can be called after any class function to determing the success
            % of the function.
            str = calllib('vsg_api', 'vsgGetErrorString', obj.LastStatus);
        end
    end % methods
end

