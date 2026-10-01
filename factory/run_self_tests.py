#!/usr/bin/env python3
"""Run the v3 standard-library regression suite, offline."""
import unittest
import inspect
import sys
import tempfile
from pathlib import Path
if __name__=='__main__':
    if not __debug__:
        raise SystemExit('Refusing optimized Python: fixture assertions must execute.')
    directory=Path(__file__).parent/'tests'
    suite=unittest.defaultTestLoader.discover(str(directory),pattern='test_*.py')
    # Discovery previously skipped all five function-style tests silently.
    for path in sorted(directory.glob('test_*.py')):
        module=sys.modules[path.stem]
        for name,fn in inspect.getmembers(module,inspect.isfunction):
            if name.startswith('test_') and fn.__module__==module.__name__:
                parameters=list(inspect.signature(fn).parameters)
                if parameters not in ([],['tmp_path']):
                    raise SystemExit('Unsupported function fixture: '+name)
                def invoke(fn=fn,parameters=parameters):
                    if parameters:
                        with tempfile.TemporaryDirectory() as temporary:
                            fn(Path(temporary))
                    else: fn()
                suite.addTest(unittest.FunctionTestCase(invoke,description=module.__name__+'.'+name))
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    raise SystemExit(0 if result.wasSuccessful() else 1)
