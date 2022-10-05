import logging
from cafram.utils import addLoggingLevel

# Add logging levels for the whole apps
addLoggingLevel("NOTICE", logging.INFO + 5)
addLoggingLevel("EXEC", logging.DEBUG + 5)
addLoggingLevel("TRACE", logging.DEBUG - 5)
