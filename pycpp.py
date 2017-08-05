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
    def __init__(self, args=None):
        self.params = {}
        if args:
            self.args = args
        else:
            from argparse import ArgumentParser, RawTextHelpFormatter, REMAINDER
            parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
            parser.add_argument('-i', '--input-file', default='-', help='the source file to preprocess, or - for stdin (default: -)')
            parser.add_argument('-o', '--output-file', default='-', help='the output file, or - for stdout (default: -)')
            parser.add_argument('-m', '--mode', choices=['tree', 'python', 'output'], default='output', help='print output at a specific stage\ntree: print the internal data structure right after parsing\npython: print the generate python code before execution\noutput: print the output of the generated python code')
            parser.add_argument('-p', '--param', default=[], action='append', metavar='key=value', help='set a value that can be read from the template (as pycpp.params["key"])')
            parser.add_argument('-P', '--python-path', default=[], action='append', metavar='path', help='additional Python module search path')
            self.args = parser.parse_args()
            for s in self.args.param:
                k, v = s.split('=', 1)
                self.params[k] = v
            import sys
            for p in self.args.python_path:
                sys.path.append(p)
        self.root = Block.root()

    def parse(self, f):
        def _joinlines(lines, pre='', lineno0=0):
            if lines == []: return []
            line0, lines = lines[0], lines[1:]
            lineno, line = line0
            if len(line) > 0 and line[-1] == '\\':
                return _joinlines(lines, pre+line[:-1]+'\n', lineno0 if pre else lineno)
            else:
                return [(lineno0 if pre else lineno, pre+line)] + _joinlines(lines, '', lineno)

        lines = _joinlines([(lineno, line.rstrip('\n')) for lineno, line in enumerate(f.readlines())])

        self.root = Block.root()
        cur, prev = self.root, []
        for line in map(Line, lines):
            if line.py:
                # begins with '#py'
                if cur.rule and line.text == cur.rule.close_tag:
                    # cur has a rule -> it is an opened block -> pop it
                    cur = prev.pop()
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

    def spool(self, b, indent=-1, r='', spool_fn='pycpp.output'):
        rem = ' # line %s' % getattr(b, 'lineno', '?')
        if b.tag == 'spool':
            v = b.header.split('`')
            r += '{}{}(\'{}\\n\'.format({})){}\n'.format(indent * 4 * ' ', spool_fn, '{}'.join(self.escape_format_string("'", x) for x in v[::2]), ', '.join('({})'.format(x) for x in v[1::2]), rem)
        else:
            if b.header: r += '{}{}{}\n'.format(indent * 4 * ' ', b.header, rem)
            for i in b.items: r += self.spool(i, indent+1)
            if b.header: r += '\n'
        return r

    def print_tree(self, b=None, indent=-1):
        if b is None: b = self.root
        print('[{:10s}] {}{}'.format(b.tag, indent * 4 * ' ', b.header))
        for i in b.items:
            self.print_tree(i, indent + 1)

    def output(self, txt):
        self._output += txt

    def run(self):
        if self.args.input_file == '-':
            from sys import stdin
            self.parse(stdin)
        else:
            with open(self.args.input_file, 'r') as f:
                self.parse(f)
        if self.args.mode == 'tree':
            self.print_tree()
        elif self.args.mode == 'python':
            print(self.spool(self.root))
        elif self.args.mode == 'output':
            self._output = ''
            exec(self.spool(self.root))
            if self.args.output_file == '-':
                print(self._output)
            else:
                with open(self.args.output_file, 'w') as f:
                    f.write(self._output)
            self._output = ''

pycpp = PyCPP()
pycpp.run()
