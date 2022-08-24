# Pshiiit' Knackie ! Library


import logging
import json
import io
import textwrap

from pprint import pprint, pformat

from paasify.common import serialize, flatten


log = logging.getLogger(__name__)

# =====================================================================
# Class helpers
# =====================================================================


class Base():

    # Public attributes
    # ---------------------

    # Current library name
    _app = "paasify"

    # Objects can have names
    name = "UNNAMMED"

    # Object kind, nice name to replace raw class name, should be a string
    kind = None

    # Define live runtime data
    # To be renamed: runtime
    runtime = {}

    # Optional attributes
    # ---------------------

    # Define class schema_def
    # To be renamed: conf_schema
    schema_def = None

    # Object shortcut to logger
    log = log


    def __init__(self, **kwargs):
        #print ("init base")
        self.kind = kwargs.get("kind") or self.kind or self.__class__.__name__
        self.name = kwargs.get("name") or self.kind or self.__class__.__name__
        self.runtime = kwargs.get("runtime") or {}

    def __str__(self):
        return f"{self.__class__.__name__}:{self.name}"

    def __repr__(self):
        return f"Instance {id(self)}: {self.__class__.__name__}:{self.name}"

    def dump2(self, format='json', filter=None):

        print (f"\nDump of {self._app}.{self.kind}.{self.name} {id(self)}")
        print ("===============================")

        # print ("  Runtime config:")
        # print (serialize(list(self.runtime.keys())))


class Log(Base):

    log = None

    def __init__(self, *args, **kwargs):
        super(Log, self).__init__(*args, **kwargs)
        #print ("init log")
        
        log = kwargs.get("log")
        if log is None:
            log_name = f"{self._app}.{self.kind}.{self.name}"
        elif isinstance(log, str):
            log_name = f"{self._app}.{log}"
            log = None
        elif log.__class__.__name__ == 'Logger':
            pass
        else:
            raise Exception ("Log not allowed here")

        if not log:
            log = logging.getLogger(log_name)

        self.log = log


class Family(Base):

    root = None
    parent = None
    children = []

    def __init__(self, *args, **kwargs):
        super(Family, self).__init__(*args, **kwargs)

        # Init family
        #print ("init family")
        parent = kwargs.get("parent") or self.parent
        
        # Register parent
        if parent and parent != self:
            self.parent = parent
            self.root = parent.root
        else:
            self.parent = self
            self.root = self

        # Register children
        self.children = []
        if self.has_parents():
            self.parent.children.append(self)

    def get_children_tree(self):
        
        result = []
        children = self.children or []
        for child in children:
            children = child.get_children_tree()
            result.append({ str(child): children or None })

        return result

    # def get_children_tree_V1(self):
        
    #     result = []
    #     children = self.children or []
    #     for child in children:
    #         children = child.get_children_tree()
    #         result.append(children)

    #     return { self.name: result or None}

    def has_parents(self):
        return True if self.parent and self.parent != self else False

    def get_parent(self):
        return self.parent or None

    def get_parents(self):
        "Return all parent of the object"

        parents = []
        current = self
        parent = self.parent or None
        while parent is not None and parent != current:
            if not parent in parents:
                parents.append(parent)
                current = parent
                parent = getattr(current, "parent")

        return parents

    # def get_parents(self):
    #     "Return all parent of the object"

    #     parents = []
    #     parent = getattr(self, "parent") or None
    #     while parent is not None and parent != self:
    #         #print (parent, "VS", self)
    #         parent = parent.get_parent()
    #         if parent:
    #             #pprint (parent)
    #             parents.append(parent)

    #     return parents

    # def get_parents2(self):
    #     "Return all parent of the object"

    #     parent = self.parent
    #     while parent is not None and parent != self:
    #         return flatten([self, parent.get_parents2()])

    #     return [self]

    def dump2(self, **kwargs):
        super(Family, self).dump2(**kwargs)

        print ("  Parents:")
        print ("  -----------------")
        parents = self.get_parents()
        parents.reverse()
        parents = serialize(parents, fmt='yaml')
        print (textwrap.indent(parents, '  '))

        print ("  Children:")
        print ("  -----------------")
        children = serialize(self.get_children_tree(), fmt='yaml')
        print (textwrap.indent(children, '  '))




class Serial(Base):

    conf_schema = {}
    conf_default = {}
    conf_raw = {}
    conf = {}

    def __init__(self, *args, **kwargs):
        super(Serial, self).__init__(*args, **kwargs)

        # Init family
        #print ("init Serial")
        self.conf_raw = kwargs.get("conf_raw", None) or {}
        self.conf = kwargs.get("conf", None) or {}

        assert not (self.conf_raw and self.conf), f"You can't provide both 'conf' and 'conf_raw'"

        # Compat !
        self.user_config = self.conf_raw
        self.config = self.conf
        self.conf_default = getattr(self, "default_user_config", None) or {}


    def dump2(self, **kwargs):

        super(Serial, self).dump2(**kwargs)

        print ("  Serial:")
        print ("  -----------------")
        print ("  Raw config:")
        data = serialize(self.conf_raw, fmt="yaml")
        print (textwrap.indent(data, '    '))
        print ("  Actual config:")
        data = serialize(self.conf, fmt="yaml")
        print (textwrap.indent(data, '    '))




# Extended classes

# class StoreDictManager(Base):
#     pass
# class StoreDictItem(Base):
#     pass


class StoreListItem(Serial,Base):
    pass


class StoreListManager(Serial,Family,Base):

    #store = []

    def __init__(self, *args, **kwargs):
        super(StoreListManager, self).__init__(*args, **kwargs)
        self._store = kwargs.get("store", None) or []

    # get_item_by_keys
    def get_items_by_name(self, name=None):
        "Return "
        result = [item for item in self._store if item.name == name]
        return result

    def get_items(self, name):
        return self._store

    def get_items_names(self, name):
        result = [item.name for item in self._store ]
        return result

    def dump2(self, **kwargs):

        super(StoreListManager, self).dump2(**kwargs)

        print (f"  Store list: ({len(self._store)} items)")
        print ("  -----------------")
        data = serialize(self._store, fmt="yaml")
        print (textwrap.indent(data, '    '))


class StoreObjItem():

    def _init_attr_from_dict(self, conf):
        "Init object attributes from dict"
        keys = []

        for k, v in conf.items():
            setattr(self, k, v)
            keys.append(k)

        self.keys = keys


    def __getitem__(self, name):
        return self.conf.get(name, None)

    def __getattr__(self, name):
        return self.conf.get(name, None)


    # Is it still required ?
    # def items(self):
    #     """
    #     Allow for config to be walkable
    #     """
    #     for k in self.keys:
    #         yield (k, getattr(self, k))




##############

class PaasifyObj(Family,Serial,Log,Base):
    pass

class StackManager(PaasifyObj, StoreListItem):
    pass



class ClassClassifier(Family,Serial,Log):
    "Structural Python Helper Class"

    
    # Private object
    # ---------------------


    # # Define default instaace config
    # # To be renammed: conf_defaults
    # default_user_config = {}

    # # Define initial user_configuration, allow loose modes
    # # To be renamed: conf_user
    # user_config = {}

    # # Define live object config (can map as attributes, usually taken from user_config)
    # # Shoud be exportable and reinjectable as user_config, conf is just the formal one
    # # To be renamed: conf
    # config = {}



    # Define live store, for containers, can be a list or a dict, to list children
    # To be renamed: store
    store = None


    def __init__(self, parent, user_config=None, name=None, *args, **kwargs):

        kwargs['runtime'] = getattr(parent, 'runtime', {})
        kwargs['conf_raw'] = user_config
        #kwargs['conf'] = dict(self.default_user_config)

        super(ClassClassifier, self).__init__(parent=parent, name=name, *args, **kwargs)
        #print ("init FINAL", self.name, self.kind)


        #self.runtime = getattr(parent, 'runtime', {})
        #self.user_config = user_config
        #config = dict(self.default_user_config)

        # Create config (COMPAT)
        config = dict(self.conf_default)
        if isinstance(user_config, dict):
            # Special dict object
            config.update(user_config)
            # Nonsense : self._init_attr_from_dict(config)
            self._init_attr_from_dict(config)
        elif user_config:
            config = user_config
        self.config = config
        
        #self.dump2()

        
        # Init objects
        if callable(getattr(self, '_init', None)):
            self._init(*args, **kwargs)

        self.dump2()
        # print ("PARENTS 1")
        # pprint(self.get_parents())
        # print ("PARENTS 2")
        # pprint(self.get_parents2())
        # print ("CHILDREN")
        # pprint(self.children)


    # TO BE DEPRECATED
    def _init_attr_from_dict(self, conf):
        "Init object attributes from dict"
        keys = []

        for k, v in conf.items():
            setattr(self, k, v)
            keys.append(k)

        self.keys = keys



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