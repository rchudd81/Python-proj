import sys, os
ROOT = os.path.dirname(__file__)
EXAMPLES_PY = os.path.join(ROOT, 'vsg60_series','examples','python')
if EXAMPLES_PY not in sys.path:
    sys.path.insert(0, EXAMPLES_PY)
print('sys.path[0]=', sys.path[0])
print('DLL search dirs before:', os.environ.get('PATH','')[:200])
DLL_DIR = os.path.join(ROOT, 'vsg60_series', 'lib', 'win', 'vs2019', 'x64')
print('DLL_DIR exists:', os.path.exists(DLL_DIR), DLL_DIR)
try:
    os.add_dll_directory(DLL_DIR)
    print('added dll dir')
except Exception as e:
    print('could not add dll dir', e)

try:
    import vsgdevice.vsg_api as v
    print('import OK')
except Exception as e:
    import traceback
    traceback.print_exc()
    print('IMPORT FAILED:', e)
