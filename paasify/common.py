import os
import logging
log = logging.getLogger(__name__)


# Usage of get_logger:
# # In main app:
#   from paasify.common import get_logger
#   log, log_level = get_logger(logger_name="paasify")
# # In other libs:
#   import logging
#   log = logging.getLogger(__name__)



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
       raise AttributeError('{} already defined in logging module'.format(levelName))
    if hasattr(logging, methodName):
       raise AttributeError('{} already defined in logging module'.format(methodName))
    if hasattr(logging.getLoggerClass(), methodName):
       raise AttributeError('{} already defined in logger class'.format(methodName))

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
        except KeyError:
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
    # tformat2 = "%Y-%m-%d %H:%M:%S"
    #formatter = logging.Formatter(format4, tformat1)
    formatter = MultiLineFormatter(format4, tformat1)
    

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


#log, log_level = get_logger(logger_name=__name__)


def list_parent_dirs(path):
    """
    Return a list of the parents paths
    """

    result = [path]
    val = path
    while val != os.sep:
        val = os.path.split(val)[0]
        result.append(val)
        #print (f"LAST VAL= |{val}|")
        
    return result


def find_file_up(names, paths):
    """
    Find every files names in names list in
    every listed paths
    """

    result = []
    for path in paths:
        for name in names:
            file_path = os.path.join(path, name)
            if os.access(file_path, os.R_OK):
                result.append(file_path)

    return result

from pprint import pprint
def filter_existing_files(root_path, candidates):
    pprint (candidates)
    return [os.path.join(root_path, cand) for cand in candidates if os.path.isfile( os.path.join(root_path, cand) ) ]
