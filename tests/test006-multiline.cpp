#include <iostream>

// the next line will not be continued by pycpp because doesn't start with #py
#define TYPE \
    int

#py x = { \
    'a': 100, \
    'b': 200 \
}

#py def f(x):\
    y = 0\
    while x:\
        y += x\
        x = int(x/2)\
    return y

using namespace std;

int main(int argc, char **argv)
{
#py for k, v in x.items():
    int `k` = `half(v)`;
#py endfor
    return 0;
}

