The vsg_api.cs source file contains the vsg_api class, which acts as an interface to the VSG API.
The methods provided in the vsg_api class have one-to-one mappings to the C functions provided by our C++ header file.
This makes it easy to port an existing project to/from C++, and also makes it easy to look up the functions in the API manual.

The vsg_example.cs source file contains a method which exercises the vsg_api class.
Import both files into an empty C# console application to get a jump-start on your project.
When you are building a C# application, you must be sure to place the proper 32/64-bit DLL files into your build directory.
e.g. If your C# CPU build type is 32-bit, put the 32-bit DLL files in your specified build directory.
If the DLL bit size does not match your project you will receive this error...

"An unhandled exception of type 'System.BadImageFormatException' occurred in csharp_vsg_api.exe"
"Additional information: An attempt was made to load a program with an incorrect format. (Exception from HRESULT: 0x8007000B)"
