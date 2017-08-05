#include <iostream>

#py x = { \
    'a': 100, \
    'b': 200 \
}

using namespace std;

int main(int argc, char **argv)
{
#py for k, v in x.items():
    int `k` = `v`;
#py endfor
    return 0;
}

