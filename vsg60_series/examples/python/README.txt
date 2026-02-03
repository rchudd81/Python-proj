Contact Information: support@signalhound.com

Prerequisites:
Python 3 is required to use the Python interface functions. The API has been
tested with Python 3.6.1 on Windows.

The VSG60 software must be fully installed before using the Python
interface functions. Additionally, ensure the VSG60 is stable and
functioning in the software before using the Python interface.

The NumPy C-Types Foreign Function Interface package is required to use the Python interface
functions, due to the need for fast array processing. The easiest way is to
install the SciPy stack, available here: https://www.scipy.org/install.html.
Alternatively, the necessary individual packages could be installed.

For our tests we used the 64-bit version of Anaconda for Windows.

Purpose:
This project enables the user to generate signals from the VSG60 through a
number of convenience functions written in Python. These functions serve as
a binding to our VSG API, and perform the majority of C shared library interfacing necessary to communicate
with the generator.

Setup:

# Windows
Place the vsg_api.py and vsg_api.dllfiles into the bbdevice/ folder.

To call the functions from outside the bbdevice/ directory you may need to add the
bbdevice folder to the Python search path and to the system path. This can be done
by editing PATH and PYTHONPATH in: Control Panel > System and Security > System
> Advanced system settings > Advanced > Environment Variables > System variables.

# Linux
Place the vsg_api.py and vsg_api.so files into the vsgdevice/ folder.

Edit the line in vsg_api.py from

    vsglib = CDLL("vsgdevice/vsg_api.dll")
        to
    vsglib = CDLL("vsgdevice/vsg_api.so").

---

To run the example scripts, navigate to the folder containing the example
.py files. Each example file is standalone and provides example code for calling the
provided Python functions for the BB60C.

Usage:
The functions under the "Functions" heading are callable from external scripts.
They are functionally equivalent to their C counterparts, except memory management
is handled by the API instead of the user.
