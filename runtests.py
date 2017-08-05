from glob import iglob
from sys import argv, exit

verbose=False

for c in argv[1:]:
    exec(c)

def runtest(name, expected_exc=None, expected_output=None):
    filename = list(iglob('tests/test*%s*' % name))
    if len(filename) < 1:
        raise RuntimeError('test not found: %s' % name)
    if len(filename) > 1:
        print('warning: %s matches multiple tests. running %s...' % (name, filename[0]))
    with open(filename[0], 'r') as f:
        input_str = f.read()
    import pycpp
    try:
        p = pycpp.PyCPP(input_str)
        p.params['v']='nunn'
        output = p.get_output()
        if verbose:
            print(output)
        if expected_exc is not None:
            print('error: test %s failed (was expected to fail with %s)' % (name, expected_exc))
            exit(1)
        if expected_output is not None:
            if output != expected_output:
                print('error: test %s failed (does not match expected output)' % name)
                exit(1)
    except Exception as e:
        if verbose:
            print('EXCEPTION: ', e)
        if expected_exc is None:
            print('error: test %s failed (was not expected to fail with %s)' % (name, type(e)))
            exit(1)
        if type(e) != expected_exc:
            print('error: test %s failed (failed with %s but was expected to fail with %s)' % (name, type(e), expected_exc))
            exit(1)

runtest('001')
runtest('002')
runtest('003')
runtest('004', RuntimeError)
runtest('005', NameError)
runtest('006')
