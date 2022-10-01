import os
import sys

from pprint import pprint
import anyconfig

from cafram.nodes import NodeList, NodeMap, NodeDict

import paasify.errors as error
from paasify.engines import EngineDetect
from paasify.framework import PaasifyObj, PaasifySources, PaasifyConfigVars, PaasifySimpleDict
from paasify.common import list_parent_dirs, find_file_up, filter_existing_files

from paasify.stacks2 import PaasifyStackTagManager, PaasifyStackManager


class PaasifyProjectConfig(NodeMap, PaasifyObj):

    conf_default = {
        "namespace": None,
        "vars": {},
        "tags": [],
        "tags_suffix": [],
        "tags_prefix": [],
    }

    conf_children = [
        {
            "key": "namespace",
        },
        {
            "key": "vars",
            "cls": PaasifyConfigVars,
        },
        # {
        #     "key": "tags",
        #     "cls": list,
        #     #"cls": PaasifyStackTagManager,
        # },
        # {
        #     "key": "tags_prefix",
        #     "cls": list,
        #     #"cls": PaasifyStackTagManager,
        # },
        # {
        #     "key": "tags_suffix",
        #     "cls": list,
        #    # "cls": PaasifyStackTagManager,
        # },
    ]


    conf_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Project settings",
        "default": conf_default,

        "oneOf": [
            {
                "type": "object",
                "additionalProperties": True,
                "properties": {
                    "namespace": {
                        
                        "title": "Project namespace",
                        "description": "Name of the project namespace. If not set, defaulted to directory name",
                        "oneOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ],
                    },
                    "vars": PaasifyConfigVars.conf_schema,
                    "tags": PaasifyStackTagManager.conf_schema,
                    "tags_suffix": PaasifyStackTagManager.conf_schema,
                    "tags_prefix": PaasifyStackTagManager.conf_schema,
                },
            },
            {
                "type": "null",
            },
        ],
    }


class PaasifyProjectRuntime(NodeMap, PaasifyObj):

    def node_hook_transform(self, payload):

        self.log.warning ("Build ProjectRuntime")

        # Build default runtime
        root_path = payload.get("root_path") or os.getcwd()
        config_file = payload.get("config_file")
        private_dir = os.path.join(root_path, '.paasify' )
        namespace = payload.get("namespace") or os.path.basename(root_path)

        collection_dir = os.path.join(private_dir, 'collections' )
        jsonnet_dir = os.path.join(private_dir, 'plugins' )

        _payload = {
            "root_path": root_path,
            "config_file": config_file,

            "project_root_dir": os.path.dirname(root_path),
            "project_private_dir": private_dir,
            "project_collection_dir": collection_dir,
            "project_jsonnet_dir": jsonnet_dir,

            "namespace": namespace,
            "engine": None,
        }

        # Update runtime
        _payload.update(payload)

        return _payload

        # # Determine namespace
        # if not self.namespace:
        #     #namespace = self.config['namespace'] or self._runtime["project_root_dir"]
        #     namespace = self.config.namespace or self.runtime.project_root_dir
        #     self.namespace = os.path.basename(namespace)



class PaasifyProject(NodeMap,PaasifyObj):


    
    conf_default = {
        "_runtime": {},
        "config": {},
        "sources": {},
        "stacks": [],
    }

    conf_children = [
        {
            "key": "_runtime",
            "cls": PaasifyProjectRuntime,
            "attr": "runtime",
            #"default": {},
        },
        {
            "key": "config",
            "cls": PaasifyProjectConfig,
            #"attr": "config",
            "hook": "_post_config",
        },
        {
            "key": "sources",
            "cls": PaasifySources,
        },
        {
            "key": "stacks",
            "cls": PaasifyStackManager,
        },
    ]



    conf_schema = {
        "$defs": {
            "Stacks": PaasifyStackManager.conf_schema,
            "Project": PaasifyProjectConfig.conf_schema,
            #"Sources": SourcesManager.conf_schema,
        },
        #"$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify",
        "description": "Main paasify project settings",
        "additionalProperties": False,
        # "required": [
        #     "stacks"
        # ],

        "default": conf_default,
        "properties": {
            "config": {
                "$ref": "#/$defs/Project",
            },
            "sources": {
                "type": "object",
            },
            "stacks": {
                "$ref": "#/$defs/Stacks",
            },
            
        }
    }

    ident = "PaasifyProject"
    filenames = ['paasify.yml', 'paasify.yaml']
    engine_cls = None


    def _post_config(self):
        "Ensure the settings are correctly set"
        # Availalable for modifications, only for remaining childrens!:
        # self._node_conf_parsed
        # self._nodes

        # Create engine
        if not self.engine_cls:
            engine_name = self.runtime.engine or None
            self.engine_cls = EngineDetect().detect(engine=engine_name)


    # Internal methods
    # ==================

    @property
    def namespace(self):
        "Return project namespace"

        result = self.config.namespace or self.runtime.namespace
        assert isinstance(result, str)

        return result

    # Internal methods
    # ==================

    @classmethod
    def get_project_path(cls, path, filenames=None):
        "Find the closest paasify config file"

        #if not path.startswith('/'):


        filenames = filenames or cls.filenames
        #filenames = self._node_root.config.filenames

        paths = list_parent_dirs(path)
        result = find_file_up(filenames, paths )

        if len(result) > 0:
            result = result[0]

        return result


    @classmethod
    #def discover(self, conf=None, path=None, filenames=None):
    def discover_project(cls, parent=None, path=None, filenames=None, runtime=None):
        """Discover project

        Generate a project instance with payload as
        payload into the config that will
        be found in path with filename filenames
        
        """
        conf = {}
        config_file = path or os.getcwd()
        filenames = filenames or ["paasify.yml", "paasify.yaml"]
        
        # Find for project candidates
        if os.path.isdir(config_file):
            _path = cls.get_project_path(config_file, filenames=filenames)
            if len(_path) == 0:
                # TOFIX: Not the good logger
                # cls.log.warning("Please specify project path via `-c` flag or `PAASIFY_APP_WORKING_DIR` variable")
                raise error.ProjectNotFound(f"Could not find any {' or '.join(filenames)} files in path: {path}")
            config_file = _path

        if not os.path.isfile(config_file):
            raise error.ProjectNotFound(f"Not a configuration file, got something else: {path}")

        return cls.load_from_file(config_file, runtime=runtime, parent=parent)
    
    @classmethod
    #def discover(self, conf=None, path=None, filenames=None):
    def load_from_file(cls, config_file, parent=None, runtime=None):
        "Load project from config file"

        runtime = runtime or {}

        # Create project config
        _payload = {}
        _runtime = {
            "config_file": config_file,
            "root_path": os.path.dirname(config_file),
        }
        _runtime.update(runtime)
        if config_file:
            _payload.update(anyconfig.load(config_file))
        _payload["_runtime"] = _runtime

        pprint (_payload)
        assert "WIPPP"

        prj = PaasifyProject(parent=parent, payload=_payload)

        return prj



    def cmd_stack_cmd(self, cmd, stacks=None):


        for stack in self.stacks.get_children():
            fun = getattr(stack, cmd)
            self.log.debug (f"Execute: {fun}")
            fun()




