Signal Hound VSG60 API for 64-bit Linux systems

Email/Support: support@signalhound.com

-- Description --
The VSG60 API is now available for 64-bit Linux. 
You can use the API to control the Signal Hound VSG60 vector signal generator.
The API will function identical to the Windows version, and as such, share examples and documentation. 
The CentOS 7 version has been reported to work on CentOS 8.3.

-- Compilation Notes -- 
The API is compiled on Ubuntu 18.04 using g++ 7.4.0 as a shared object library.
Installation instructions may reflect this.
The API depends on the libusb-1.0 USB drivers. Installation instructions can be found below.

-- Libusb 1.0 requirement -- 
You will need libusb-1.0 installed in the system path. 
Determine if libusb-1.0 is installed on your system with
  'locate libusb-1.0.so'
You can install libusb-1.0 with
  'sudo apt-get install libusb-1.0-0' 
or
  download and install from www.libusb.org

-- Device Permissions --
To run an application utilizing libusb, you need to be have
root permissions. You can either run your application as root or change permissions for the device.

-- Changing Device Permissions --
If you do not want to run your application with root permissions, 
you will need to change permissions for the Signal Hound VSG60 devices. 
You will need to copy the sh_usb.rules file in the /etc/udev/rules.d/ directory. 
Once you have done this, you will need to unplug and plug in the device for the rules to take effect. 
You should then be able to interface the device without root permissions.

-- Installation --
The VSG60 API is a 64 bit shared library. The library can be found in the lib/ folder.
The best way to develop to the sm_api is to place the included libraries in the /usr/local/lib directory. 
Steps to perform this are below.

To install the shared library on your system from the lib folder, type

    sudo cp libvsg_api.* /usr/local/lib
    sudo ldconfig -v -n /usr/local/lib
    sudo ln -sf /usr/local/lib/libvsg_api.so.1 /usr/local/lib/libvsg_api.so
 
This should create the necessary symlinks to the main library and place them in the library directory.

The shared library can now be linked in with g++ by
    g++ sources -o output_exe -Wl, -rpath /usr/local/lib -lvsg_api


