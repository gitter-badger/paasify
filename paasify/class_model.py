
import logging
from pprint import pprint, pformat

log = logging.getLogger(__name__)

# =====================================================================
# Class helpers
# =====================================================================

class ClassClassifier():

    default_user_config = {}

    # Objects can have names
    name = "UNNAMMED"

    # Define initial user_configuration
    user_config = {}

    # Define live shared runtime data
    runtime = {}

    # Define live object config (can map as attributes)
    config = {}

    # Define live store, for containers
    store = None

    # Define class schema_def
    schema_def = None


    def __init__(self, parent, user_config=None, name=None, *args, **kwargs):

        # Init object classifier
        if parent:
            self.parent = parent
            self.root = parent.root
        else:
            self.parent = self
            self.root = self
        self.name = name or self.__class__.__name__
        self.log = logging.getLogger(f"paasify.{self.__class__.__name__}.{self.name}")

        #log, _ = get_logger(logger_name=f"paasify.{self.__class__.__name__}.{self.name}")


        self.runtime = getattr(parent, 'runtime', {})
        self.user_config = user_config
        self._init_attr_from_dict(self.default_user_config)

        # Init objects
        self._init(*args, **kwargs)


    def __repr__(self):
        return f"Instance {id(self)}: {self.__class__.__name__}:{self.name}"

    def _init_attr_from_dict(self, conf):
        "Init object attribute from dict"
        keys = []

        for k, v in conf.items():
            setattr(self, k, v)
            keys.append(k)

        self.keys = keys


    def get_root_parent(self):
        # print (f"Getting parent of ... {self}")

        if not hasattr(self, 'parent'):
            raise Exception(f"Bug, missing parent attribute for {self}!")
        elif self.parent == self:
            return self

        parent = self.parent
        if hasattr(parent, 'get_root_parent'):
            return parent.get_root_parent()
        else:
            return parent

    def dump(self):
        self.log.info (f"\nDump of object: {self.name} ({self.__class__}, {id(self)})")
        self.log.info ("="*20)


        
        #print ("Shared Runtime:")
        #pprint (self.runtime)

        #print ("-"*20)
        self.log.info ("User config:")
        self.log.info (pformat (self.user_config))
        self.log.info ("Instance Store:")
        self.log.info (pformat (self.store))
        self.log.info ("Instance Config:")
        self.log.info (pformat (self.config))



        cls_dump = getattr(self, "_dump", None)
        if callable(cls_dump):
            self.log.info ("-"*20)
            cls_dump()

        self.log.info ("="*20)