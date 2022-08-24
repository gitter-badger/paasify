import io
import os
import sys

import logging
import json
from pprint import pprint
from pathlib import Path

import re
import sh
import ruamel.yaml

import paasify.errors as error


# =====================================================================
# Init
# =====================================================================

# Usage of get_logger:
# # In main app:
#   from paasify.common import get_logger
#   log, log_level = get_logger(logger_name="paasify")
# # In other libs:
#   import logging
#   log = logging.getLogger(__name__)

log = logging.getLogger(__name__)


# Setup YAML object
yaml = ruamel.yaml.YAML()
yaml.version = (1, 1)
yaml.default_flow_style = False
#yaml.indent(mapping=3, sequence=2, offset=0)
yaml.allow_duplicate_keys = True
yaml.explicit_start = True


# =====================================================================
# Logging helpers
# =====================================================================

# Source: https://stackoverflow.com/questions/2183233/how-to-add-a-custom-loglevel-to-pythons-logging-facility/35804945#35804945
def addLoggingLevel(levelName, levelNum, methodName=None):
    """
    Comprehensively adds a new logging level to the `logging` module and the
    currently configured logging class.

    `levelName` becomes an attribute of the `logging` module with the value
    `levelNum`. `methodName` becomes a convenience method for both `logging`
    itself and the class returned by `logging.getLoggerClass()` (usually just
    `logging.Logger`). If `methodName` is not specified, `levelName.lower()` is
    used.

    To avoid accidental clobberings of existing attributes, this method will
    raise an `AttributePaasifyError` if the level name is already an attribute of the
    `logging` module or if the method name is already present 

    Example
    -------
    >>> addLoggingLevel('TRACE', logging.DEBUG - 5)
    >>> logging.getLogger(__name__).setLevel("TRACE")
    >>> logging.getLogger(__name__).trace('that worked')
    >>> logging.trace('so did this')
    >>> logging.TRACE
    5

    """
    if not methodName:
        methodName = levelName.lower()

    if hasattr(logging, levelName):
       raise AttributePaasifyError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributePaasifyError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributePaasifyError('{} already defined in logger class'.format(methodName))

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):

        if self.isEnabledFor(levelNum):
            # Monkey patch for level below 10, dunno why this not work
            lvl = levelNum if levelNum >= 10 else 10
            self._log(lvl, message, args, **kwargs)

    def logToRoot(message, *args, **kwargs):
        logging.log(levelNum, message, *args, **kwargs)

    logging.addLevelName(levelNum, levelName)
    setattr(logging, levelName, levelNum)
    setattr(logging.getLoggerClass(), methodName, logForLevel)
    setattr(logging, methodName, logToRoot)


class MultiLineFormatter(logging.Formatter):
    """Multi-line formatter."""
    def get_header_length(self, record):
        """Get the header length of a given record."""
        return len(super().format(logging.LogRecord(
            name=record.name,
            level=record.levelno,
            pathname=record.pathname,
            lineno=record.lineno,
            msg='', args=(), exc_info=None
        )))

    def format(self, record):
        """Format a record with added indentation."""
        indent = ' ' * self.get_header_length(record)
        head, *trailing = super().format(record).splitlines(True)
        return head + ''.join(indent + line for line in trailing)


def get_logger(logger_name=None, create_file=False, verbose=None):
    """Create CmdApp logger"""

    # Take default app name
    logger_name = logger_name or __name__

    # Manage logging level
    if not verbose:
        loglevel = logging.getLogger().getEffectiveLevel()
    else:
        try:
            loglevel = {
                0: logging.ERROR,
                1: logging.WARN,
                2: logging.INFO,
                3: logging.DEBUG,
            }[verbose]
        except KeyPaasifyError:
            loglevel = logging.DEBUG

    # Create logger for prd_ci
    log = logging.getLogger(logger_name)
    log.setLevel(level=loglevel)

    # Formatters
    format1 = "%(levelname)8s: %(message)s"
    format4 = "%(name)-32s%(levelname)8s: %(message)s"
    format2 = "%(asctime)s.%(msecs)03d|%(name)-16s%(levelname)8s: %(message)s"
    format3 = (
       "%(asctime)s.%(msecs)03d"
       + " (%(process)d/%(thread)d) "
       + "%(pathname)s:%(lineno)d:%(funcName)s"
       + ": "
       + "%(levelname)s: %(message)s"
    )
    tformat1 = "%H:%M:%S"
    #tformat2 = "%Y-%m-%d %H:%M:%S"
    #formatter = logging.Formatter(format4, tformat1)
    formatter = MultiLineFormatter(format1, tformat1)
    

    # Create console handler for logger.
    stream = logging.StreamHandler()
    stream.setLevel(level=logging.DEBUG)
    stream.setFormatter(formatter)
    log.addHandler(stream)

    # Create file handler for logger.
    if isinstance(create_file, str):
        handler = logging.FileHandler(create_file)
        handler.setLevel(level=logging.DEBUG)
        handler.setFormatter(formatter)
        log.addHandler(handler)

    #print (f"Fetch logger name: {logger_name} (level={loglevel})")

    # Return objects
    return log, loglevel


# =====================================================================
# Misc functions
# =====================================================================

def list_parent_dirs(path):
    """
    Return a list of the parents paths
    """
    result = [path]
    val = path
    while val != os.sep:
        val = os.path.split(val)[0]
        result.append(val)        
    return result


def find_file_up(names, paths):
    """
    Find every files names in names list in
    every listed paths
    """
    assert isinstance(names, list), f"Names must be array, not: {type(names)}"
    assert isinstance(paths, list), f"Paths must be array, not: {type(names)}"

    result = []
    for path in paths:
        for name in names:
            file_path = os.path.join(path, name)
            if os.access(file_path, os.R_OK):
                result.append(file_path)

    return result


def filter_existing_files(root_path, candidates):
    return [os.path.join(root_path, cand) for cand in candidates if os.path.isfile( os.path.join(root_path, cand) ) ]


def lookup_candidates(lookup_config):
    "List all available candidates of files for given folders"

    result = []
    for lookup in lookup_config:
        if lookup["path"]:
            cand = filter_existing_files(
                lookup["path"],
                lookup["pattern"])

            lookup["matches"] = cand
            result.append(lookup)
        
    return result

    
def cast_docker_compose(var):
    "Convert any types to strings"

    if var is None:
        return ''
    elif isinstance(var, (bool)):
        return 'true' if var else 'false'
    elif isinstance(var, (str, int)):
        return str(var)
    elif isinstance(var, list):
        return ','.join(var)
    elif isinstance(var, dict):
        return ','.join([ f"{key}={str(val)}" for key, val in var.items() ])
    else:
        raise Exception(f"Impossible to cast value: {var}")


def merge_env_vars(obj):
    "Transform all keys of a dict starting by _ to their equivalent wihtout _"

    override_keys = [ key.lstrip('_') for key in obj.keys() if key.startswith('_') ]
    for key in override_keys:
        old_key = '_' + key
        obj[key] = obj[old_key]
        obj.pop(old_key)
    
    return obj, override_keys


def serialize(obj, fmt='json'):
    "Serialize anything, output json like compatible (destructive)"
    
    if fmt in ['yaml', 'yml']:
        # Serialize object in json first
        obj = json.dumps(obj, default=lambda o: str(o), indent=2)
        obj = json.loads(obj)

        # Convert json to yaml
        string_stream = io.StringIO()
        yaml.dump(obj, string_stream)
        output_str = string_stream.getvalue()
        string_stream.close()

        # Remove 2 first lines of output
        output_str = output_str.split("\n", 2)[2]
        return output_str
    else:
        obj = json.dumps(obj, default=lambda o: str(o), indent=2)
        return obj


def read_file(file):
    "Read file content"
    with open(file) as f:
        return ''.join(f.readlines())


def write_file(file, content):
    "Write content to file"

    file_folder = os.path.dirname(file)
    if not os.path.exists(file_folder):
        os.makedirs(file_folder)

    with open(file, 'w') as f:
        f.write(content)


def flatten(S):
    "Flatten any arrays nested arrays"
    if S == []:
        return S
    if isinstance(S[0], list):
        return flatten(S[0]) + flatten(S[1:])
    return S[:1] + flatten(S[1:])


# =====================================================================
# Command Execution framework
# =====================================================================

def _exec(command, cli_args=None, logger=None, **kwargs):
    "Execute any command"

    # Check arguments
    cli_args = cli_args or []
    assert isinstance(cli_args, list), f"_exec require a list, not: {type(cli_args)}"

    # Prepare context
    sh_opts = {
        '_in': sys.stdin,
        '_out': sys.stdout,
    }
    sh_opts = kwargs or sh_opts

    # Bake command
    cmd = sh.Command(command)
    cmd = cmd.bake(*cli_args)

    # Log command
    if logger:
        cmd_line = [cmd.__name__ ] + [ x.decode('utf-8') for x in cmd._partial_baked_args]
        cmd_line = ' '.join(cmd_line)
        logger.exec (cmd_line)     # Support exec level !!!

    # Execute command via sh
    try:
        output = cmd(**sh_opts)
        return output

    except sh.ErrorReturnCode as err:
        #log.error(f"Error while running command: {command} {' '.join(cli_args)}")
        #log.critical (f"Command failed with message:\n{err.stderr.decode('utf-8')}")
        
        #pprint (err.__dict__)
        #raise error.ShellCommandFailed(err)
        #sys.exit(1)
        raise err


# =====================================================================
# Beta libs (DEPRECATED)
# =====================================================================

def parse_vars(match):

    #print (type(match))

    match = match.groupdict()

    #pprint (match)
    name = match.get("name1", None) or match.get("name2", None)

    # Detect assignment method
    mode = match['mode']
    if mode == '-':
        mode = 'unset_alt'
    elif mode == ':-':
        mode = 'empty_alt'
    elif mode == '?':
        mode = 'unset_err'
    elif mode == ':?':
        mode = 'empty_err'
    else:
        mode = 'simple'

    r = {
        'name': name,
        'mode': mode,
        'arg': match['arg'] or None
    }
    return r



# Broken
# SHELL_REGEX =r'[^$]((\$(?P<name1>[0-9A-Z_]+))|(\${(?P<name2>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>(?R)))}))'


# Test complex only v1
#SHELL_REGEX =r'[^$](\${(?P<name2>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>.*))?})'


# Test complex only v2
#SHELL_REGEX =r'[^$](\${(?P<name2>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>.*(?R)?.*))?})'



#### WIPPP

# OKK simple: v1 SHELL_REGEX =r'[^$]((\${(?P<name1>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>[^}]*))})|(\$(?P<name2>[0-9A-Z_]+)))'
SHELL_REGEX =r'[^$]((\${(?P<name1>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>.*))})|(\$(?P<name2>[0-9A-Z_]+)))'


# V2 testing
SHELL_REGEX =r'[^$]((\${(?P<name1>[0-9A-Z_]+)((?P<mode>:?[?-]?)(?P<arg>.*))})|(\$(?P<name2>[0-9A-Z_]+)))'



SHELL_REGEX = re.compile(SHELL_REGEX) #, flags=regex.DEBUG)

def extract_shell_vars(file):
    "Extract all shell variables call in a file"

    print (f"FILE MATCH: {file}")

    # Open file
    with open(file) as f:
        lines = f.readlines()

    content = ''.join(lines)


    ### LEXER APPROACH
    import shlex
    lexer = shlex.shlex(content)
    print (shlex.split(content))
    # for token in lexer:
    #     print ( repr(token))
        

    sdfsdfsdf

    #### REGEX APPROACH

    # Parse shell vars, first round
    result = []
    for match in re.finditer(SHELL_REGEX, content):

        r = parse_vars(match)
        print ("  NEW MATCH 1: ", r)
        result.append(r)


    # PArse shell vars second round
    found = True
    while found == True:

        cand = [ x['arg'] for x in result if isinstance(x['arg'], str)]
        cand = '\n'.join(cand)

        #print (cand)
        found = False
        for match in re.finditer(SHELL_REGEX, cand):
            
            
            r = parse_vars(match)
            #print ("  NEW MATCH", match.groupdict())
            print ("  NEW MATCH 2: ", r)
            var_name = r['name']
            if len([ x for x in result if x['name'] == var_name ]) == 0:
                found = True
                result.append(r)


        # TEMP
        #found = False
        
    print ("FINAL RESULT ============================")
    pprint (result)
    return result



