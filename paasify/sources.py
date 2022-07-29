
import os
import sys
import logging

#import yaml
import anyconfig
import sh
#import _jsonnet

from pprint import pprint, pformat

from paasify.common import _exec
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
            "prefix": {
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
            "prefix": "https://github.com/%s.git",
            #"prefix": "https://framagit.org/%s.git",
            
        }
        config.update(self.user_config)
        self.collection_dir = self.runtime['collections_dir']

        self.config = config
        self._init_attr_from_dict(config)
        self.path = self.get_path()
        

        self._init_git_url()

    def _init_git_url(self):        
        # Determine what is the git_url
        config = self.config
        url = config["url"]
        name = config["name"]
        prefix = config["prefix"]

        self.git_url = url if url else prefix % name


    def get_path(self):
        return os.path.join(self.collection_dir, self.name)

    def is_git(self):
        "Return true if git repo"
        test_path = os.path.join(self.path, '.git')
        return os.path.isdir(test_path)

    def is_installed(self):
        "Return true if installed"
        return os.path.isdir(self.path)


    def install(self):
        "Install from remote"

        # Check if install dir is already present
        if os.path.isdir(self.path):
            self.log.info("This source is already installed")
            return

        self.log.notice(f"Installing git source: {self.git_url}")

        # Git clone that stuff
        cli_args = [
            "clone",
            self.git_url,
            self.path
        ]
        _exec("git", cli_args, _fg=True)


    def update(self):
        "Update from remote"

        # Check if install dir is already present
        if not os.path.isdir(self.path):
            self.log.info("This source is not installed yet")
            return

        # Git clone that stuff
        self.log.info(f"Updating git repo: {self.git_url}")
        cli_args = [
            "-C", self.path ,
            "pull",
        ]
        _exec("git", cli_args, _fg=True)



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

        self.collection_dir = self.runtime['collections_dir']

        assert isinstance(self.user_config, dict), f"Source def is not a dict"

        store= []

        for source_name, source_def in self.user_config.items():
            source = Source(self, user_config=source_def, name=source_name)
            store.append(source)

        self.store = store

    def get_all(self):
        "Return the list of all sources"
        return list(self.store)

    def list_all_names(self) -> list:
        "Return a list of valid string names"
        r1 = [src.name for src in self.store ]
        r2 = [src.alias for src in self.store ]
        return r1 + r2


    def get_source(self, src_name):

        result = [src for src in self.store if src_name == src.name ] or [src for src in self.store if src_name == src.alias ]
        return result[0] if len(result) > 0 else None


    def resolve_ref_pattern(self, src_pat):
        "Return a resource from its name or alias"

        for src_name_def in self.list_all_names():

            if f"{src_name_def}:" in src_pat:
                rsplit = src_pat.split(':', 2)
                src_name = rsplit[0]
                src_stack = rsplit[1]

                return src_stack, src_name
        
        return src_pat, None



