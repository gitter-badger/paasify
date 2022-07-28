
import logging
from pprint import pprint, pformat

log = logging.getLogger(__name__)

# =====================================================================
# Class helpers
# =====================================================================

class ClassClassifier():
    "Structural Python Helper Class"

    
    # Private object
    # ---------------------

    # Objects can have names
    name = "UNNAMMED"

    # Object kind, nice name to replace raw class name, should be a string
    kind = None

    # Define class schema_def
    # To be renamed: conf_schema
    schema_def = None

    # Define default instaace config
    # To be renammed: conf_defaults
    default_user_config = {}

    # Define initial user_configuration, allow loose modes
    # To be renamed: conf_user
    user_config = {}

    # Define live object config (can map as attributes, usually taken from user_config)
    # Shoud be exportable and reinjectable as user_config, conf is just the formal one
    # To be renamed: conf
    config = {}

    # Define live runtime data
    # To be renamed: runtime
    runtime = {}

    # Define live store, for containers, can be a list or a dict, to list children
    # To be renamed: store
    store = None

    # Autyomatic objects:
    # ---------------------

    # Object personal logger
    log = None

    # Shared objects:
    # ---------------------
    # Parent object of all
    root = None

    # Parent link
    parent = None

    # Shared glob data, with multiple access
    # glob = None
    # glob_prj = 
    # glob_stack = 



    def __init__(self, parent, user_config=None, name=None, *args, **kwargs):

        # Init object classifier
        if parent:
            self.parent = parent
            self.root = parent.root
        else:
            self.parent = self
            self.root = self

        self.kind = self.kind or self.__class__.__name__
        self.name = name or self.__class__.__name__
        self.log = logging.getLogger(f"paasify.{self.kind or self.__class__.__name__}.{self.name}")

        #log, _ = get_logger(logger_name=f"paasify.{self.__class__.__name__}.{self.name}")

        
        self.runtime = getattr(parent, 'runtime', {})
        self.user_config = user_config
        self.config = dict(self.default_user_config)
        if isinstance(user_config, dict):
            # Special dict object
            self.config.update(user_config)
            self._init_attr_from_dict(self.config)
        elif user_config:
            self.config = user_config
        
        # Init objects
        if callable(getattr(self, '_init', None)):
            self._init(*args, **kwargs)


    def __repr__(self):
        return f"Instance {id(self)}: {self.__class__.__name__}:{self.name}"

    def _init_attr_from_dict(self, conf):
        "Init object attributes from dict"
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
        self.log.info ("Instance User config:")
        self.log.info (pformat (self.user_config))
        self.log.info ("Instance Config:")
        self.log.info (pformat (self.config))
        self.log.info ("Instance Runtime:")
        self.log.info (pformat (self.runtime))
        self.log.info ("Instance Store:")
        self.log.info (pformat (self.store))




        cls_dump = getattr(self, "_dump", None)
        if callable(cls_dump):
            self.log.info ("-"*20)
            cls_dump()

        self.log.info ("="*20)