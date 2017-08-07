#include <iostream>

#py d = dict(\
    foo=('int', 2),\
    bar=('float', 3),\
    baz=('double', 1)\
)

#py for k,v in d.items():
#py pycpp.params['name'] = k
#py pycpp.params['type'] = v[0]
#py pycpp.params['num_args'] = v[1]
#py pycpp.include('tmpl')
#py endfor
