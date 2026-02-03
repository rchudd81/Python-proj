Contact Information: aj@signalhound.com

Documentation:
Once the folders are in the MATLAB search path type
'doc VSG60'
for a full description of the classes methods and properties.

Prerequisites:
The VSG60 software and driver must be fully installed before using the MATLAB
interface functions. Additionally, ensure the VSG60 is stable and
functioning before using the MATLAB interface.

Purpose:
This API enables the user to use the VSG60 to generate waveforms created
in MATLAB. These functions serve as a binding to our VSG60 API, and perform
the majority of C DLL interfacing necessary to communicate with the receiver.

Setup:
Place the vsg_api.dll and vsg_api.h files in the /vsg60_device/ folder.
You will need to grab the DLL and header files from the SDK.

Examples:
To call the functions from outside the /vsg_device/ directory you will need
to add the vsg_device folder to the MATLAB search path. You can do this by either
using the "Set Path" button on the MATLAB ribbon bar, or finding the /vsg_device/
directory in the folder explorer and right clicking and selecting "Add to Path".

To run the test/examples scripts, ensure the /vsg_device/ folder has been added to the
MATLAB search path. Navigate to the folder containing the example**.m files.
Each example file is standalone.