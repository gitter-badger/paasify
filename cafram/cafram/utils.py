"""
Cafram utils
"""

# pylint: disable=line-too-long
# pylint: disable=invalid-name

import io
import os

import logging
import json
import re
from io import StringIO

# from pprint import pprint
# from pathlib import Path

import ruamel.yaml
import jsonschema
from jsonschema import Draft202012Validator, validators
import sh


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
# yaml.indent(mapping=3, sequence=2, offset=0)
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
    raise an `AttributeError` if the level name is already an attribute of the
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
        raise AttributeError(f"{levelName} already defined in logging module")
    if hasattr(logging, methodName):
        raise AttributeError(f"{methodName} already defined in logging module")
    if hasattr(logging.getLoggerClass(), methodName):
        raise AttributeError(f"{methodName} already defined in logger class")

    # This method was inspired by the answers to Stack Overflow post
    # http://stackoverflow.com/q/2183233/2988730, especially
    # http://stackoverflow.com/a/13638084/2988730
    def logForLevel(self, message, *args, **kwargs):

        if self.isEnabledFor(levelNum):
            # Monkey patch for level below 10, dunno why this not work
            lvl = levelNum
            if levelNum < 10:  # Why this ? :`(
                lvl = 10
                message = f"({levelName}) {message}"
            # pylint: disable=protected-access
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
        return len(
            super().format(
                logging.LogRecord(
                    name=record.name,
                    level=record.levelno,
                    pathname=record.pathname,
                    lineno=record.lineno,
                    msg="",
                    args=(),
                    exc_info=None,
                )
            )
        )

    def format(self, record):
        """Format a record with added indentation."""
        indent = " " * self.get_header_length(record)
        head, *trailing = super().format(record).splitlines(True)
        return head + "".join(indent + line for line in trailing)


def get_logger(logger_name=None, create_file=False, verbose=None):
    """Create CmdApp logger"""

    # Take default app name
    logger_name = logger_name or __name__

    # Manage logging level
    if not verbose:
        loglevel = logging.getLogger().getEffectiveLevel()
    else:
        try:
            # pylint: disable=protected-access
            loglevels = list(logging._nameToLevel)
            loglevel = loglevels[verbose]
        except IndexError:
            loglevel = len(loglevels) - 1

    # Create logger for prd_ci
    _log = logging.getLogger(logger_name)
    _log.setLevel(level=loglevel)

    # Formatters
    format1 = "%(levelname)8s: %(message)s"
    # pylint: disable=unused-variable
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
    # tformat2 = "%Y-%m-%d %H:%M:%S"
    # formatter = logging.Formatter(format4, tformat1)
    formatter = MultiLineFormatter(format1, tformat1)

    # Create console handler for logger.
    stream = logging.StreamHandler()
    # stream.setLevel(level=logging.DEBUG)
    stream.setFormatter(formatter)
    _log.addHandler(stream)

    # Create file handler for logger.
    if isinstance(create_file, str):
        handler = logging.FileHandler(create_file)
        handler.setLevel(level=logging.DEBUG)
        handler.setFormatter(formatter)
        _log.addHandler(handler)

    # print (f"Fetch logger name: {logger_name} (level={loglevel})")

    # Return objects
    return _log


# =====================================================================
# Misc functions
# =====================================================================

# pylint: disable=redefined-builtin
def truncate(data, max=72, txt=" ..."):
    "Truncate a text to max lenght and replace by txt"
    data = str(data)
    if max < 0:
        return data
    if len(data) > max:
        return data[: max + len(txt)] + txt
    return data


def merge_dicts(dict1, dict2):
    """Given two dictionaries, merge them into a new dict as a shallow copy.

    Compatibility for Python 3.5 and above"""
    # Source: https://stackoverflow.com/a/26853961/2352890
    result = dict1.copy()
    result.update(dict2)
    return result


# TODO: Add tests on this one
def to_domain(string, sep=".", alt="-"):
    "Transform any string to valid domain name"

    domain = string.split(sep)
    result = []
    for part in domain:
        part = re.sub("[^a-zA-Z0-9]", alt, part)
        part.strip(alt)
        result.append(part)

    return ".".join(result)


# TODO: Add tests on this one
def first(array):
    "Return the first element of a list or None"
    # return next(iter(array))
    array = list(array) or []
    result = None
    if len(array) > 0:
        result = array[0]
    return result


# TODO: add tests
def from_yaml(string):
    "Transform YAML string to python dict"
    return yaml.load(string)


# TODO: add tests
def to_yaml(obj, headers=False):
    "Transform obj to YAML"
    options = {}
    string_stream = StringIO()

    if isinstance(obj, str):
        obj = json.loads(obj)

    yaml.dump(obj, string_stream, **options)
    output_str = string_stream.getvalue()
    string_stream.close()
    if not headers:
        output_str = output_str.split("\n", 2)[2]
    return output_str


# TODO: add tests
def to_json(obj, nice=True):
    "Transform JSON string to python dict"
    if nice:
        return json.dumps(obj, indent=2)
    return json.dumps(obj)


# TODO: add tests
def from_json(string):
    "Transform JSON string to python dict"
    return json.loads(string)


# TODO: add tests
def to_dict(obj):
    """Transform JSON obj/string to python dict

    Useful to transofmr nested dicts as well"""
    if not isinstance(obj, str):
        obj = json.dumps(obj)
    return json.loads(obj)


def serialize(obj, fmt="json"):
    "Serialize anything, output json like compatible (destructive)"

    # pylint: disable=unnecessary-lambda
    obj = json.dumps(obj, default=lambda o: str(o), indent=2)

    if fmt in ["yaml", "yml"]:
        # Serialize object in json first
        obj = json.loads(obj)

        # Convert json to yaml
        string_stream = io.StringIO()
        yaml.dump(obj, string_stream)
        output_str = string_stream.getvalue()
        string_stream.close()

        # Remove 2 first lines of output
        obj = output_str.split("\n", 2)[2]

    return obj


def duplicates(_list):
    """Check if given list contains duplicates"""
    known = set()
    dup = set()
    for item in _list:
        if item in known:
            dup.add(item)
        else:
            known.add(item)

    if len(dup) > 0:
        return list(dup)
    return []


def read_file(file):
    "Read file content"
    with open(file, encoding="utf-8") as _file:
        return "".join(_file.readlines())


def write_file(file, content):
    "Write content to file"

    file_folder = os.path.dirname(file)
    if not os.path.exists(file_folder):
        os.makedirs(file_folder)

    with open(file, "w", encoding="utf-8") as _file:
        _file.write(content)


def flatten(array):
    "Flatten any arrays nested arrays"
    if array == []:
        return array
    if isinstance(array[0], list):
        return flatten(array[0]) + flatten(array[1:])
    return array[:1] + flatten(array[1:])


# =====================================================================
# JSON Schema framework
# =====================================================================


def _extend_with_default(validator_class):
    validate_properties = validator_class.VALIDATORS["properties"]

    def set_defaults(validator, properties, instance, schema):
        for prop, subschema in properties.items():
            if "default" in subschema:
                instance.setdefault(prop, subschema["default"])

        for error in validate_properties(
            validator,
            properties,
            instance,
            schema,
        ):
            yield error

    return validators.extend(
        validator_class,
        {"properties": set_defaults},
    )


DefaultValidatingValidator = _extend_with_default(Draft202012Validator)


def json_validate_defaults(schema, payload):
    "Validate dict against schema and set defaults"
    DefaultValidatingValidator(schema).validate(payload)
    return payload


def json_validate(schema, payload):
    "Validate dict against schema"
    jsonschema.validate(payload, schema)
    return payload


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
        # "_in": sys.stdin,
        # "_out": sys.stdout,
    }
    sh_opts = kwargs or sh_opts

    # Bake command
    cmd = sh.Command(command)
    cmd = cmd.bake(*cli_args)

    # Log command
    if logger:
        cmd_line = [f"{key}='{val}'" for key, val in sh_opts.get("_env", {}).items()]
        # pylint: disable=protected-access
        cmd_line = (
            cmd_line
            + [cmd.__name__]
            + [x.decode("utf-8") for x in cmd._partial_baked_args]
        )
        cmd_line = " ".join(cmd_line)
        logger.exec(cmd_line)  # Support exec level !!!

    # Execute command via sh
    try:
        output = cmd(**sh_opts)
        return output

    except sh.ErrorReturnCode as err:
        # log.error(f"Error while running command: {command} {' '.join(cli_args)}")
        # log.critical (f"Command failed with message:\n{err.stderr.decode('utf-8')}")

        # pprint (err.__dict__)
        # raise error.ShellCommandFailed(err)
        # sys.exit(1)
        raise err
