import os
import sys

from pprint import pprint
import anyconfig

from cafram.nodes import NodeList, NodeMap, NodeDict

import paasify.errors as error
from paasify.engines import EngineDetect
from paasify.framework import PaasifyObj, PaasifySources, PaasifyConfigVars, PaasifySimpleDict
from paasify.common import list_parent_dirs, find_file_up, filter_existing_files

from paasify.stacks2 import PaasifyStackTags, PaasifyStacks


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
        {
            "key": "tags",
            "cls": PaasifyStackTags,
        },
        {
            "key": "tags_prefix",
            "cls": PaasifyStackTags,
        },
        {
            "key": "tags_suffix",
            "cls": PaasifyStackTags,
        },
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
                    "tags": PaasifyStackTags.conf_schema,
                    "tags_suffix": PaasifyStackTags.conf_schema,
                    "tags_prefix": PaasifyStackTags.conf_schema,
                },
            },
            {
                "type": "null",
            },
        ],
    }




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
            "cls": PaasifySimpleDict,
            "attr": "runtime",
            #"default": {},
        },
        {
            "key": "config",
            "cls": PaasifyProjectConfig,
            #"attr": "config",
            "hook": "post_config",
        },
        {
            "key": "sources",
            "cls": PaasifySources,
        },
        {
            "key": "stacks",
            "cls": PaasifyStacks,
        },
    ]



    conf_schema = {
        "$defs": {
            "Stacks": PaasifyStacks.conf_schema,
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
    namespace = None


    def post_config(self):

        # pprint (self.__dict__)
        # pprint (self.config)

        if not self.namespace:
            #namespace = self.config['namespace'] or self._runtime["project_root_dir"]
            namespace = self.config.namespace or self.runtime.project_root_dir
            self.namespace = os.path.basename(namespace)

        #self.engine = EngineDetect().detect(self.runtime.engine)

    def cmd_stack_cmd(self, cmd, stacks=None):


        for stack in self.stacks.get_children():
            fun = getattr(stack, cmd)
            self.log.debug (f"Execute: {fun}")
            fun()



    @classmethod
    def get_project_path(self, path, filenames=None):
        "Find the closest paasify config file"

        #if not path.startswith('/'):


        filenames = filenames or self.filenames
        #filenames = self._node_root.config.filenames

        paths = list_parent_dirs(path)
        result = find_file_up(filenames, paths )

        if len(result) > 0:
            result = result[0]

        return result


    @classmethod
    def discover(self, conf=None, path=None, filenames=None):

        conf = conf or {}
        path = path or os.getcwd()
        filenames = filenames or ["paasify.yml", "paasify.yaml"]
        print ("CURRENT PATH", path)
        
        # Find for project candidates
        if os.path.isdir(path):
            _path = self.get_project_path(path, filenames=filenames)
            if len(_path) == 0:
                # TOFIX: Not the good logger
                # self.log.warning("Please specify project path via `-c` flag or `PAASIFY_APP_WORKING_DIR` variable")
                raise error.ProjectNotFound(f"Could not find any {' or '.join(filenames)} files in path: {path}")
            path = _path

        if not os.path.isfile(path):
            raise error.ProjectNotFound(f"Not a configuration file, got something else: {path}")

        

        # Create project config
        private_dir = os.path.join(os.path.dirname(path), '.paasify' )
        conf = {
            "_runtime": {
                "project_root_path": path,
                "project_root_file": os.path.basename(path),
                "project_root_dir": os.path.dirname(path),
                "project_private_dir": private_dir,
                "project_collection_dir": os.path.join(private_dir, 'collections' ),

                "engine": None,
            },
        }
        conf.update(anyconfig.load(path))

        return conf

        #self.deserialize(prj_config)

        # if result is None:
        #     result2 = get_project_path()

        # pprint (path)
        # print ("find: config file: ", path)
        # pprint (prj_config)
        # raise Exception("WIPPPP")

    # def load_file(self, path=None):
    #     path = path or os.getcwd()

    #     if not os.path.isfile(path):
    #         path = self.get_project_path(path)

    #     print ("LOADING22222 project ...", path)

