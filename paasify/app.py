
# from pydantic import BaseModel
import os
import sys
import re
import logging
import json
import yaml

from dataclasses import dataclass, astuple, asdict
from pathlib import Path
from copy import copy

import anyconfig

from paasify.common import *
from paasify.sources import SourcesManager
from paasify.stacks import StackManager, StackTag, StackEnv
from paasify.class_model import ClassClassifier

from pprint import pprint, pformat

log = logging.getLogger(__name__)


# =====================================================================
# Project management
# =====================================================================

class ProjectConfig(ClassClassifier):
    """
    Class to hold config data
    """

    def _init(self):

        self._init_attr_from_dict(self.user_config)

    def __getattr__(self, name):
        return None

    def items(self):
        """
        Allow for config to be walkable
        """

        for k in self.keys:
            yield (k, getattr(self, k))


class Project(ClassClassifier):

    schema_project_def = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Project settings",
        "additionalProperties": False,
        "properties": {
            "namespace": {
                "type": "string",
            },
            "env": StackEnv.schema_def,
            "tags": {
                "type": "array",
                "items": StackTag.schema_def,
            },
            "tags_prefix": {
                "type": "array",
                "items": StackTag.schema_def,
            },
            "tags_suffix": {
                "type": "array",
                "items": StackTag.schema_def,
            },
            "tags_config": {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    '.*': {
                        "oneOf": [
                            {"type": "object"},
                            {"type": "array"},
                            {"type": "null"},
                        ],
                    }
                },
            },
        }
    }

    schema_def={
        "$defs": {
            "Stacks": StackManager.schema_def,
            "Project": schema_project_def,
        },
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Project configuration",
        "additionalProperties": False,
        "properties": {
            "project": {
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

    #name = "Paasify"
    
    default_user_config = {
            "project": {
                "namespace": None,
                "env": [],
                "tags": [],
                "tags_suffix": [],
                "tags_prefix": [],
            },
            "sources": {},
            "stacks": []
        }


    def __init__(self, user_config=None, logguer_name=None, *args, **kwargs):

        self.root = self
        self.parent = self
        self.name = "PaasifyProject"
        self.log = logging.getLogger(f"paasify.{self.__class__.__name__}.{self.name}")

        self._init(*args, **kwargs)

        self.log.trace("Application started!")


    def _init(self, **kwarg_config):
        """
        Generate application context
        """

        #pprint (self.schema_def)
    
        config_path = kwarg_config.get("config_path", None)
        if config_path and os.access(config_path, os.R_OK):
            config_path = config_path

        # Get context and parents
        cwd = os.getcwd()
        search_dir = config_path or cwd
        project_root_configs = find_file_up( 
            ['paasify.yml', 'paasify.yaml'],
            list_parent_dirs(search_dir)
            )

        # Process nested projects
        project_level = len(project_root_configs)
        if project_level == 0:
            raise Exception("Can't find 'paassify.yml' config in current or parent dirs")
        elif project_level == 1:
            self.log.debug("Context: Root project")
        else:
            self.log.debug(f"Context: Subproject of level: {project_level}")
        project_config_path = project_root_configs[0]
        project_dir = os.path.dirname(project_config_path)

        # Detect default stack context
        subdir = None
        if project_dir in cwd:
            strip_count = len(project_dir)+1
            subdir = cwd[strip_count:]
            current_stack = subdir.split(os.sep)[0] or None
            self.log.debug (f"Auto detect stack because of sub: {current_stack}")


        # Load anyconfig
        project_config = dict(self.default_user_config)
        project_config.update(anyconfig.load(project_config_path))
        rc, rc_msg = anyconfig.validate(project_config, self.schema_def)
        if not rc:
            self.log.warn(f"Failed to validate paasify.yml, please check details with: -v")
            self.log.info(f"Code: {rc}, {rc_msg}")
            sys.exit(1)
            #pprint (rc_msg)
            raise Exception(f"Failed to validate paasify.yml")


        prj_namespace = project_config['project'].get('namespace', None) or os.path.basename(project_dir)

        # Generate new config
        new_config = {
            'cwd': cwd,
            'level': project_level,
            'config_path': project_config_path,
            'project_dir': project_dir,
            #'collections_dir': f"{Path.home()}/.config/paasify/collections",
            'collections_dir': os.path.join(project_dir, '.collections'),
            'plugins_dir': os.path.join(project_dir, '.plugins'),
            # Not a good idea: 'plugins_dir': f"{Path.home()}/.config/paasify/plugins",

            'parent_configs_paths': project_root_configs[1:],
            'top_project_dir': os.path.dirname(project_root_configs[-1]),

            'subdir': subdir,
            'current_stack': current_stack,


            # Should not be here I think ...
            'docker_compose_output': 'docker-compose.run.yml',
            'tags_prefix': project_config['project'].get('tags_prefix', []),
            'tags_suffix': project_config['project'].get('tags_suffix', []),
            'tags': project_config['project'].get('tags', []),
            'namespace': prj_namespace,
            'tags_auto' : [
                'user',
                prj_namespace,
            ],
        }

        # Prepare result
        runtime = kwarg_config or {}
        runtime.update(new_config)
        #self.config = runtime
        
        self.project_config = project_config

        # Init public sub-objects
        self.runtime = runtime   # Replace with ProjectConfig !!!
        self.project = ProjectConfig(self, user_config=project_config.get('project', {}))
        self.sources = SourcesManager(self, user_config=project_config.get('sources', {}))
        self.stacks = StackManager(self, user_config=project_config.get('stacks', []))

        # self.log.info ("This must not be empty ")
        # pprint(self.stacks.dump_stacks())
        # sys.exit()
        

    def cmd_info(self):
        self.log.info ("Main informations:")
        for k, v in self.runtime.items():
            if k not in ['project_config']:
                self.log.info (f"  {k: >20}: {str(v)}")

        self.log.info ("Paasify config:")
        self.log.info (pformat (self.project_config))

        
        # Show current stack

        curr_stack = self.runtime["current_stack"]
        if not curr_stack:
            self.log.info ("Paasify stack context: None")
        else:
            self.log.info (f"Paasify stack context: {curr_stack}")
            stack = self.stacks.get_stacks_by_name(curr_stack)

            if len(stack) != 1:
                #pprint ()
                for x in self.root.stacks.store:
                    pprint (x.__dict__)
                raise Exception(f"Failed to find stack: {stack}")
            stack = stack[0]

           # pprint (stack.)

            stack.dump()
            

    def cmd_build(self, stack=None):

        stack_name = stack or self.runtime['current_stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        

        for stack in stacks:
            stack.docker_assemble()


    def cmd_up(self, stack=None):

        stack_name = stack or self.runtime['current_stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in stacks:
            stack.docker_up()


    def cmd_down(self, stack=None):

        stack_name = stack or self.runtime['current_stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in stacks:
            stack.docker_down()

    # Monitoring commands

    def cmd_ps(self, stack=None):

        stack_name = stack or self.runtime['current_stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in stacks:
            stack.docker_ps()

    def cmd_logs(self, stack=None, follow=False):

        stack_name = stack or self.runtime['current_stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        if follow and len(stacks) > 1:
            raise Exception (f"Impossible to log follow on many stacks.")

        for stack in stacks:
            stack.docker_logs(follow=follow)


    def cmd_stacks_list(self):

        stacks = self.stacks.get_all_stacks()

        self.log.notice(f"List of stacks:")
        for stack in stacks:
            self.log.notice(f"- {stack.name}")

    def cmd_config_schema(self, format='json'):

        if format == 'json':
            return json.dumps(self.schema_def, indent=4, sort_keys=True)

        elif format == 'yaml':
            return yaml.dump(self.schema_def)
