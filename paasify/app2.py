import os
import sys

from pprint import pprint

import anyconfig

from cafram.utils import to_yaml, to_json, _exec, write_file, serialize, flatten, json_validate
from cafram.nodes import NodeList, NodeMap, NodeDict, NodeMapEnv


import paasify.errors as error
from paasify.framework import (
    PaasifyObj,
)
from paasify.common import list_parent_dirs, find_file_up, filter_existing_files
from paasify.common import OutputFormat

from paasify.projects import PaasifyProject


# from paasify.common import _exec, list_parent_dirs, find_file_up, filter_existing_files, write_file
# from paasify.class_model import *
# from paasify.common import serialize, flatten, json_validate


class PaasifyAppConfig(NodeMapEnv, PaasifyObj):

    conf_env_prefix = "PAASIFY_APP"

    conf_default = {
        "default_source": "default",
        "cwd": os.getcwd(),
        "working_dir": os.getcwd(),
        "engine": None,
        "filenames": ["paasify.yml", "paasify.yaml"],
    }

    conf_schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Project settings",
        "additionalProperties": False,
        "properties": {
            "default_source": {
                "title": "",
                "description": "",
                "type": "string",
            },
            "cwd": {
                "title": "",
                "description": "",
                "type": "string",
            },
            "working_dir": {
                "title": "",
                "description": "",
                "type": "string",
            },
            "engine": {
                "title": "Docker backend engine",
                "oneOf": [
                    {
                        "description": "Docker engine",
                        "type": "string",
                    },
                    {
                        "description": "Automatic",
                        "type": "null",
                    },
                ],
            },
            "filenames": {
                "oneOf": [
                    {
                        "title": "List of file to lookup",
                        "description": "List of string file names to lookup paasify.yaml files",
                        "type": "array",
                        "items": {
                            "type": "string",
                        },
                    },
                ],
            },
        },
    }


class PaasifyApp(NodeMap, PaasifyObj):

    ident = "Paasify"

    conf_default = {
        "config": {},
        "project": {},
    }

    conf_children = [
        {
            "key": "config",
            "cls": PaasifyAppConfig,
        },
        {
            "key": "project",
            "cls": PaasifyProject,
            "action": "unset",
        },
    ]

    conf_schema = {
        "$defs": {
            "AppConfig": PaasifyAppConfig.conf_schema,
            "AppProject": PaasifyProject.conf_schema,
        },
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify App",
        "description": "Paasify app implementation",
        "additionalProperties": False,
        # "required": [
        #     "stacks"
        # ],
        "default": {},
        "properties": {
            "project": {
                "title": "Project configuration",
                "oneOf": [
                    {
                        "$ref": "#/$defs/AppProject",
                        "description": "Instanciate project",
                        "type": "object",
                    },
                    {
                        "description": "Do not instanciate project",
                        "type": "null",
                    },
                ],
            },
            "config": {
                "$ref": "#/$defs/AppConfig",
            },
        },
    }

    def info(self, autoload=None):
        """Report app config"""

        print("Paasify App Info:")
        print("==================")
        print(f"  cwd: {self.config.cwd}")
        print(f"  project lookup dir: {self.config.working_dir}")

        # Autoload default project
        msg = ""
        if autoload is None or autoload == True:
            try:
                if not self.project:
                    self.log.notice("Info is autoloading project")
                    self.load_project()
            except error.ProjectNotFound as err:
                msg = err
                if autoload is True:
                    raise error.ProjectNotFound(err)
                pass

        print("\nPaasify Project Info:")
        print("==================")

        if self.project:
            # Report with active project if available
            for k, v in self.project.runtime.get_value(lvl=-1).items():
                print(f"  {k}: {v}")
        else:
            print(f"  {msg}")

    def cmd_config_schema(self, format=None, target=None):
        """Returns the configuration json schema

        Args:
            format (_type_, optional): _description_. Defaults to None.

        Returns:
            _type_: _description_
        """

        if target == "app":
            out = self.conf_schema
        elif target == "project":
            out = PaasifyProject.conf_schema
        elif target == "test":
            from paasify.stacks2 import PaasifyStackManager
            out = PaasifyStackManager.conf_schema
            #raise NotImplemented()
        else:
            out = PaasifyProject.conf_schema

        if format == OutputFormat.yaml:
            out = to_yaml(out)
        elif format == OutputFormat.json:
            out = to_json(out, nice=True)

        return out

    def load_project(self, path=None):
        "Return closest project"

        if self.project is not None:
            return self.project

        # Auto discover project path
        prj = PaasifyProject.discover_project(
            parent=None,
            path=path or self.config.working_dir,
            filenames=self.config.filenames,
            runtime=dict(self.config.get_value()),
        )
        self.add_child("project", prj)

        # self.show_childs()
        # sys.exit(1)

        return prj
