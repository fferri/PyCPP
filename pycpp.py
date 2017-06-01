class Rule:
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
    def __init__(self, line):
        from re import match, sub
        self.no = 1 + line[0]
        self.text = line[1].rstrip()
        self.py = False
        m = match(r'^#py\s+(([^\s]+)(.*)?)', self.text)
        if m:
            self.text = m.group(1)
            self.py = True
            self.tag = sub(':$', '', m.group(2))
            self.rule = block_rules.get(self.tag)

class Block:
    def __init__(self, line):
        self.tag = line.tag
        self.header = line.text
        self.items = []
        self.rule = block_rules.get(self.tag)

class PyCPP:
    def __init__(self, args=None):
        self.options = {}
        if args:
            self.args = args
        else:
            from argparse import ArgumentParser, RawTextHelpFormatter, REMAINDER
            parser = ArgumentParser(formatter_class=RawTextHelpFormatter)
            parser.add_argument('file', default='-', nargs='?', help='the source file to preprocess, or - for stdin')
            parser.add_argument('--mode', choices=['tree', 'python', 'output'], default='output', help='print output at a specific stage\ntree: print the internal data structure right after parsing\npython: print the generate python code before execution\noutput: print the output of the generated python code')
            parser.add_argument('--option', action='append', metavar='key=value', help='set a value that can be read from the template (as pycpp.options["key"])')
            self.args = parser.parse_args()
            for s in self.args.option:
                k, v = s.split('=', 1)
                self.options[k] = v
        self.root = self.empty_root()

    def empty_root(self):
        return type('Block', (), dict(header=None, items=[], tag='root', rule=None))

    def parse(self, f):
        self.root = self.empty_root()
        cur, prev = self.root, []
        for line in map(Line, enumerate(f)):
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

    def spool(self, b, indent=-1, r='', spool_fn='pycpp.output'):
        if b.tag == 'spool':
            v = b.header.split('`')
            r += '{}{}(\'{}\\n\'.format({}))\n'.format(indent * 4 * ' ', spool_fn, '{}'.join(x.replace('\\', '\\\\').replace('\'', '\\\'').replace('\n', '\\n').replace('{', '{{').replace('}', '}}') for x in v[::2]), ', '.join('({})'.format(x) for x in v[1::2]))
        else:
            if b.header: r += '{}{}\n'.format(indent * 4 * ' ', b.header)
            for i in b.items: r += self.spool(i, indent+1)
        return r

    def print_tree(self, b=None, indent=-1):
        if b is None: b = self.root
        print('[{:10s}] {}{}'.format(b.tag, indent * 4 * ' ', b.header))
        for i in b.items:
            self.print_tree(i, indent + 1)

    def output(self, txt):
        self._output += txt

    def run(self):
        if self.args.file == '-':
            from sys import stdin
            self.parse(stdin)
        else:
            with open(self.args.file, 'r') as f:
                self.parse(f)
        if self.args.mode == 'tree':
            self.print_tree()
        elif self.args.mode == 'python':
            print(self.spool(self.root))
        elif self.args.mode == 'output':
            self._output = ''
            exec(self.spool(self.root))
            print(self._output)
            self._output = ''

pycpp = PyCPP()
pycpp.run()
