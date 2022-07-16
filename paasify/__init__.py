
import logging
from paasify.common import addLoggingLevel

# Add logging levels for the whole apps
addLoggingLevel('TRACE', logging.DEBUG - 5)
addLoggingLevel('EXEC', logging.DEBUG + 5)
addLoggingLevel('NOTICE', logging.INFO + 5)
