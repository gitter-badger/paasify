import os
from dataclasses import dataclass
from enum import Enum
from lark import Lark, Transformer


class BashVarKind(Enum):

    SIMPLE = 'simple'
    LONG = 'long'
    UNSET = 'unset'
    EMPTY = 'empty'


@dataclass
class BashVar():
    """Class that store a bash variable"""

    name: str
    mode: BashVarKind = BashVarKind.SIMPLE
    arg: str = None
    ignored: bool = False
    prefix: str = '$'

    def __repr__(self):
        return f"BashVar: {self.render_code()}"

    def __str__(self):
        return self.render_code()



    def render_code(self, prefix=None):

        prefix = prefix or self.prefix
            
        #if self.mode == 'simple':
        if self.mode == BashVarKind.SIMPLE:
            return f"{prefix}{self.name}"
        #elif self.mode == 'long':
        elif self.mode == BashVarKind.LONG:
            return "%s{%s}" % (prefix, self.name)
        elif self.mode == BashVarKind.UNSET:
        #elif self.mode == 'unset':
            return "%s{%s:-%s}" % (prefix, self.name, self.arg)
        elif self.mode == BashVarKind.EMPTY:
        #elif self.mode == 'empty':
            return "%s{%s-%s}" % (prefix, self.name, self.arg)
        else:
            # This is an error !
            raise Exception (f"Unknown mode: {self.mode}")

    def render_parsed(self, env=None):

        env = env or {}
        var_value = env.get(self.name, None)

        if self.ignored:
            return self.render_code(prefix='$')

        if var_value is None:
            #if self.mode in ['unset', 'empty']:
            if self.mode in [BashVarKind.UNSET, BashVarKind.EMPTY]:
                var_value = f"{self.arg}"
        elif var_value == '':
            if self.mode == BashVarKind.EMPTY:
                var_value = f"{self.arg}"

        var_value = var_value or ''

        assert isinstance(var_value, str), f"Got {type(var_value)}"
        return var_value
        

    def render(self, out, env=None):

        if out == "raw":
            return self.render_code()
        elif out == "parse":
            return self.render_parsed(env=env)
        else:
            raise Exception("Tadaaaa")
            


class BashVarTransformer(Transformer):
    "Bash variables DSL transformer"

    # Internal vars
    # --------------------
    var_list = []
    output_mode = 'raw'
    env = {}


    # DSL terminals
    # --------------------
    WORDS = str
    SH_COMMENT = str
    WS = str
    CNAME = str
    VAR_PREFIX = str

    # DSL rules
    # --------------------


    def start(self, items):
        lines = items[0]
        return ''.join([ self._to_string(x) for x in lines ])


    def bash_var_ignored(self, items):
        return items[0].render(self.output_mode, self.env)

    def bash_var_simple(self, items, value=None, mode=None):
        "Register a simple bash variable"
        mode = mode or BashVarKind.SIMPLE
        prefix = items[0]
        name = items[1]

        ignored = True
        if prefix != '$$':
            ignored = False

        bash_var = BashVar(name=name, mode=mode, arg=value, ignored=ignored, prefix=prefix)

        if not ignored:
            self.var_list.append(bash_var)

        return bash_var

    def bash_var_long(self, items):
        "Register a long bash variable"
        return self.bash_var_simple(items, mode=BashVarKind.LONG)

    def bash_var_complex(self, items):
        "Register a complex bash variable"

        var_prefix, var_name, var_opts = items[0], items[1], items[2]
        var_mode = var_opts['mode']
        var_value = var_opts['opts']

        var_value = ''.join([ self._to_string(x) for x in var_value ])

        bash_var = self.bash_var_simple([var_prefix, var_name], mode=var_mode, value=var_value)
        return bash_var


    def statement(self, items):
        "Statement transparent proxy"
        #pprint (items)
        return items

    def bash_var_complex_unset(self,items):
        return self._bash_var_complex_set(items, BashVarKind.UNSET)

    def bash_var_complex_empty(self,items):
        return self._bash_var_complex_set(items, BashVarKind.EMPTY)


    # Internal methods
    # --------------------

    def _to_string(self, x):
        "Return a string of an item"

        if isinstance(x, BashVar):
            r = x.render(out=self.output_mode, env=self.env)
        else:
            r = str(x)
        return r


    def _bash_var_complex_set(self,items, kind):
        "Wrap a complex set"

        return {
            "mode": kind,
            "opts": items[0]
        }

    def transform(self, tree, output_mode='raw', env=None):
        "Transform the given tree, and return the final result (override)"

        assert output_mode in ['raw', 'parse'], f"Got: {output_mode}"
        self.output_mode = output_mode
        self.env = env or os.environ
        self.var_list = []
        return self._transform_tree(tree)



class BashVarParser():

    EBNF = r"""
    // Terminals
    SH_COMMENT: /#[^\n]*/



    LCASE_LETTER: "a".."z"
    UCASE_LETTER: "A".."Z"
    DIGIT: "0".."9"

    LETTER: UCASE_LETTER | LCASE_LETTER
    CNAME: ("_"|LETTER) ("_"|LETTER|DIGIT)*

    // This is mother fucking buggy :(
    //WORDS : /\w+/            // VALIDATED
    //WORDS : /[\w:"'=!?@#%&*()\/\.\[\]^,`-]+/     // VALIDATED BUT BUGGY
    WORDS : /[^$ ]+?/    // SEEEMS TO WORK, but damn slow
    

    // MANY OTHER TESTS
    //WORDS : /\S/
    //WORDS : /^[^$].+/
    //WORDS : /[^$].+/
    //WORDS : /(?!\$).+/
    //WORDS: /[^\W]+/
    //WORDS: /\S+?/
    //WORDS : /[^\n]+/
    //WORDS : /[^ ]+/
    //WORDS : /[^\s]+/
    

    //VAR_PREFIX : /[\S]?\$/    // VALIDATED
    //VAR_PREFIX : /[^$]?\$/     // TESTING
    //VAR_PREFIX : /\${1,2}/
    VAR_PREFIX : "$$" | "$"

    //WS_INLINE: (" "|/\t/)+
    WS: /[ \t\f\r\n]/+

    // Document parser
    start : statement
    statement: ( bash_var | SH_COMMENT | WS | WORDS )*

    // Bash vars
    ?bash_var.100: bash_var_simple | bash_var_long | bash_var_complex
    bash_var_simple: VAR_PREFIX CNAME
    bash_var_long: VAR_PREFIX "{" CNAME "}"
    bash_var_complex: VAR_PREFIX "{" CNAME (bash_var_complex_empty | bash_var_complex_unset) "}"

    // bash_var_complex: "${" CNAME bash_var_complex_def? "}"
    // ?bash_var_complex_def: bash_var_complex_empty | bash_var_complex_unset

    bash_var_complex_empty: "-" statement
    bash_var_complex_unset: ":-" statement

    """

    def __init__(self, payload=None, env=None):
        
        parser="lalr"
        parser="earley"
        self.parser = Lark(self.EBNF, start='start', parser=parser, debug=True) #, lexer="dynamic") #, ambiguity='explicit')
        self.transformer = BashVarTransformer()

        self.payload = None
        self.tree = None
        self.env = env or {}
        self.var_list = []

        if payload:
            self.load(payload)


    def load(self, payload):
        tree = self.parser.parse(payload)
        self.transformer.transform(tree)

        self.payload = payload
        self.tree = tree
        self.var_list = self.transformer.var_list

        return tree


    def show_internals(self):

        if not self.tree:
            raise Exception("You need to parse something first !")

        return self.tree.pretty()


    def render(self, mode='parse', env=None):

        if not self.tree:
            raise Exception("You need to parse something first !")

        env = env or self.env
        return self.transformer.transform(self.tree, output_mode = mode, env=env)


