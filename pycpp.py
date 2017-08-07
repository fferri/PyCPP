import os
import sys

class Rule:
    '''
    A class to represent rules for matching beginning/end of blocks.
    '''

    def __init__(self, name, close_tag, follows=None):
        self.name = name
        self.close_tag = close_tag
        self.follows = follows

block_rules = {rule.name: rule for rule in (
    Rule('for', 'endfor'),
    Rule('while', 'endwhile'),
    Rule('if', 'endif'),
    Rule('elif', 'endif', ('if', 'elif')),
    Rule('else', 'endif', ('if', 'elif'))
)}

class Line:
    '''
    Abstraction for a line of text input, used by PyCPP.parse
    '''

    def __init__(self, line):
        from re import match, sub
        self.no = 1 + line[0]
        self.text = line[1]
        if self.text and self.text[-1] == '\\n':
            self.text = self.text[:-1]
        self.py = False
        self.tag = None
        if self.text[0:4] == '#py ':
            self.text = self.text[4:]
            self.py = True
            self.tag = sub(':$', '', self.text.split()[0])
            self.rule = block_rules.get(self.tag)

class Block:
    '''
    Abstraction for a Block (line#, tag, header, children items)
    '''

    def __init__(self, line):
        self.lineno = line.no
        self.tag = line.tag
        self.header = line.text
        self.items = []
        self.rule = block_rules.get(self.tag)

    @staticmethod
    def root():
        return type('Block', (), dict(header=None, items=[], tag='root', rule=None))


class PyCPP:
    def __init__(self, input_str='', params={}):
        self.input_str = input_str
        self.params = params
        self.include_path = []

        self.root = Block.root()

        def _joinlines(lines):
            '''
            utility for continuing lines with a trailing backslash
            '''
            nlines = []
            cont = False
            orig_lineno, buf = -1, []
            for lineno, line in lines:
                if cont:
                    if len(line) > 0 and line[-1] == '\\':
                        buf.append(line[:-1])
                    else:
                        buf.append(line)
                        nlines.append((orig_lineno, '\n'.join(buf)))
                        orig_lineno, buf = -1, []
                        cont = False
                else:
                    if line[0:4] == '#py ' and len(line) > 0 and line[-1] == '\\':
                        cont = True
                        orig_lineno, buf = lineno, [line[:-1]]
                    else:
                        nlines.append((lineno, line))
            return nlines

        lines = input_str.split('\n')
        nlines = _joinlines(enumerate(lines))

        self.root = Block.root()
        cur, prev = self.root, []
        for line in map(Line, nlines):
            if line.py:
                # begins with '#py'
                if cur.rule and line.text == cur.rule.close_tag:
                    # cur has a rule -> it is an opened block -> pop it
                    cur = prev.pop()
                    if line.text[:3] == 'end':
                        cur.items.append(Block(Line((line.no, ''))))
                elif line.rule:
                    # line rule is set -> it is the beginning of a block
                    if not line.rule.follows:
                        # if it a toplevel block, push cur into the stack
                        prev.append(cur)
                    elif cur.tag not in line.rule.follows:
                        # check for mismatch
                        raise RuntimeError('line {:d}: unexpected "{}" after "{}"'.format(line.no, line.text, cur.tag))
                    cur = Block(line)
                    prev[-1].items.append(cur)
                else:
                    # otherwise it is an arbitrary line of python code
                    line.tag = 'py'
                    cur.items.append(Block(line))
            else:
                # it is a 'standard' line
                line.tag = 'spool'
                cur.items.append(Block(line))
        if prev:
            raise RuntimeError('line {:d}: expected "{}" to close "{}"'.format(line.no, cur.rule.close_tag, cur.tag))

    def escape_string(self, delimiter, string):
        return string.replace('\\', '\\\\').replace(delimiter, '\\' + delimiter).replace('\n', '\\n')

    def escape_format_string(self, delimiter, string):
        return self.escape_string(delimiter, string).replace('{', '{{').replace('}', '}}')

    def get_python_code(self, b=None, indent=-1, spool_fn='print', r=''):
        if b is None: b = self.root
        rem = ' # line %s' % getattr(b, 'lineno', '?')
        if b.tag == 'spool':
            v = b.header.split('`')
            r += '{}{}(\'{}\\n\'.format({})){}\n'.format(indent * 4 * ' ', spool_fn, '{}'.join(self.escape_format_string("'", x) for x in v[::2]), ', '.join('({})'.format(x) for x in v[1::2]), rem)
        else:
            if b.header: r += '{}{}{}\n'.format(indent * 4 * ' ', b.header, rem)
            else: r += '\n'
            for i in b.items: r += self.get_python_code(i, indent+1, spool_fn)
        return r

    def get_output(self, b=None):
        self._output_lines = []
        pycpp = self
        exec(self.get_python_code(b, spool_fn='self.output'))
        return '\n'.join(self._output_lines)

    def output(self, txt):
        if txt[-1] == '\n': txt = txt[:-1]
        self._output_lines.append(txt)

    def print_tree(self, b=None, indent=-1):
        if b is None: b = self.root
        print('[{:10s}] {}{}'.format(b.tag, indent * 4 * ' ', b.header))
        for i in b.items:
            self.print_tree(i, indent + 1)

    def add_include_path(self, path):
        self.include_path.append(path)

    def include(self, template_file):
        def resolve_file(path):
            for incpath in self.include_path:
                fullpath = os.path.join(incpath, path)
                if os.path.exists(fullpath):
                    return fullpath
            return path

        template_file = resolve_file(template_file)
        with open(template_file, 'r') as f:
            template = f.read()
        pycpp_ = PyCPP(input_str=template, params=self.params)
        self.output(pycpp_.get_output())

if __name__ == '__main__':
    from argparse import ArgumentParser, RawTextHelpFormatter, REMAINDER
    parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
    parser.add_argument('-i', '--input-file', default='-', help='the source file to preprocess, or - for stdin (default: -)')
    parser.add_argument('-o', '--output-file', default='-', help='the output file, or - for stdout (default: -)')
    parser.add_argument('-m', '--mode', choices=['tree', 'python', 'output'], default='output', help='print output at a specific stage\ntree: print the internal data structure right after parsing\npython: print the generate python code before execution\noutput: print the output of the generated python code')
    parser.add_argument('-p', '--param', default=[], action='append', metavar='key=value', help='set a value that can be read from the template (as pycpp.params["key"])')
    parser.add_argument('-P', '--python-path', default=[], action='append', metavar='path', help='additional Python module search path')
    args = parser.parse_args()

    params = {}
    for s in args.param:
        k, v = s.split('=', 1)
        params[k] = v

    for p in args.python_path:
        sys.path.append(p)

    if args.input_file == '-':
        input_str = sys.stdin.read()
        include_path = '.'
    else:
        with open(args.input_file, 'r') as f:
            input_str = f.read()
            include_path = os.path.dirname(args.input_file)

    pycpp = PyCPP(input_str=input_str, params=params)
    pycpp.add_include_path(include_path)

    if args.mode == 'tree':
        pycpp.print_tree()
    elif args.mode == 'python':
        print(pycpp.get_python_code())
    elif args.mode == 'output':
        if args.output_file == '-':
            print(pycpp.get_output())
        else:
            with open(self.args.output_file, 'w') as f:
                f.write(pycpp.get_output())

