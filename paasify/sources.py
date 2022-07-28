
import os
import sys
import logging

#import yaml
import anyconfig
#import sh
#import _jsonnet

from pprint import pprint, pformat

#from paasify.common import *
from paasify.class_model import ClassClassifier


log = logging.getLogger(__name__)


# =====================================================================
# Source management
# =====================================================================


class Source(ClassClassifier):
    """ A Source instance
    """

    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
        
        "title": "Paasify Source configuration",
        "additionalProperties": False,
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
            },
            "path": {
                "type": "string",
            },
            "alias": {
                "type": "string",
            }
        },
    }


    def _init(self):

        self.obj_prj = self.parent.obj_prj

        config = {
            "name": self.name,
            "url": None,
            "alias": None,
        }
        config.update(self.user_config)

        self.config = config
        self._init_attr_from_dict(config)
        self.path = self.get_path()
        

    def get_path(self):
        return os.path.join(self.runtime['collections_dir'], self.name)





class SourcesManager(ClassClassifier):


    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
        
        "title": "Paasify Source configuration",
        "additionalProperties": False,
        "type": "object",
        "patternProperties": {
            '.*': {
                "type": Source.schema_def,
            }
        },

    }

    def _init(self):

        self.obj_prj = self.parent

        assert isinstance(self.user_config, dict), f"Source def is not a dict"

        store= []

        for source_name, source_def in self.user_config.items():
            source = Source(self, user_config=source_def, name=source_name)
            store.append(source)

        self.store = store

    def list_all_names(self):
        r1 = [src.name for src in self.store ]
        r2 = [src.alias for src in self.store ]
        return r1 + r2


    def get_source(self, src_name):

        result = [src for src in self.store if src_name == src.name ] or [src for src in self.store if src_name == src.alias ]
        return result[0] if len(result) > 0 else None


    def resolve_ref_pattern(self, src_pat):
        "Return a resource from its name or alias"

        for src_name_def in self.root.sources.list_all_names():

            if src_name_def in src_pat:
                split_len = len(src_name_def)
                source_name = src_pat[:split_len]
                source_path = src_pat[split_len:]
                return source_name, source_path
                break



