
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

from paasify.common import _exec, list_parent_dirs, find_file_up
import paasify.errors as error

from paasify.sources import SourcesManager
from paasify.stacks import StackManager, StackTag, StackEnv
from paasify.class_model import ClassClassifier

from pprint import pprint, pformat

log = logging.getLogger(__name__)


class ProjectConfig(ClassClassifier):
    """
    Class to hold config data
    """

    def __getattr__(self, name):

        return self.config.get(name, None)

    def items(self):
        """
        Allow for config to be walkable
        """

        for k in self.keys:
            yield (k, getattr(self, k))




class Project(ClassClassifier):
    "Project instance"
    
    schema_project_def = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Project settings",
        "additionalProperties": False,
        "properties": {
            "namespace": {
                "title": "Project namespace",
                "description": "Name of the project namespace. If not set, defaulted to directory name",
                "type": "string",
            },
            "env": StackEnv.schema_def,
            "tags": {
                "title": "Global tags",
                "description": "List of tags to apply globally",
                "type": "array",
                "items": StackTag.schema_def,
            },
            "tags_prefix": {
                "title": "Global prefix tags",
                "description": "List of tags to apply globally",
                "type": "array",
                "items": StackTag.schema_def,
            },
            "tags_suffix": {
                "title": "Global suffix tags",
                "description": "List of tags to apply globally",
                "type": "array",
                "items": StackTag.schema_def,
            },
        }
    }

    schema_def={
        "$defs": {
            "Stacks": StackManager.schema_def,
            "Project": schema_project_def,
            "Sources": SourcesManager.schema_def,
        },
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify",
        "description": "Main paasify project settings",
        "additionalProperties": False,
        "required": [
            "stacks"
        ],
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


    default_user_config = {
            "config_file_path": "paasify.yml",
            "stack": None,
            "stack_autodetect": True,
        }

    default_project_config = {
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



    def _init(self, *args, **kwargs):
            

        # Process nested projects
        # project_level = len(project_root_configs)
        # if project_level == 0:
        #     raise Exception("Can't find 'paassify.yml' config in current or parent dirs")
        # elif project_level == 1:
        #     self.log.debug("Context: Root project")
        # else:
        #     self.log.debug(f"Context: Subproject of level: {project_level}")

        # Detect base settings
        prj_config_path = self.user_config["config_file_path"]
        if not prj_config_path:
            raise error.ProjectNotFound (f"Can't find 'paasify.yml' project")
        prj_dir = os.path.dirname(prj_config_path)
        prj_namespace = os.path.basename(prj_dir)
        collections_dir = os.path.join(prj_dir, '.paasify/collections')
        plugins_dir = os.path.join(prj_dir, '.paasify/plugins')
        

        # Load project config
        project_config = dict(self.default_project_config)
        project_config.update(anyconfig.load(prj_config_path))
        rc, rc_msg = anyconfig.validate(project_config, self.schema_def)
        if not rc:
            self.log.warn(f"Failed to validate paasify.yml, please check details with: -v")
            self.log.info(f"Code: {rc}, {rc_msg}")
            sys.exit(1)
            #pprint (rc_msg)
            raise error.ProjectInvalidConfig(f"Failed to validate paasify.yml")

        # Inject project config
        namespace = project_config['project'].get('namespace', None) or prj_namespace
        collections_dir = project_config['project'].get('collections_dir', None) or collections_dir

        # Init runtime
        self.runtime["namespace"] = namespace
        self.runtime["top_project_dir"] = prj_dir
        self.runtime["prj_dir"] = prj_dir
        self.runtime["collections_dir"] = collections_dir
        self.runtime["plugins_dir"] = plugins_dir
        self.runtime["docker_compose_output"] = "docker-compose.run.yml"

        # Init public sub-objects
        self.runtime["project_config"] = project_config   # Replace with ProjectConfig !!!
        self.project = ProjectConfig(self, user_config=project_config.get('project', {}))
        self.sources = SourcesManager(self, user_config=project_config.get('sources', {}))
        self.stacks = StackManager(self, user_config=project_config.get('stacks', []))

        # Detect current stack context
        cwd = self.parent.runtime["cwd"]
        stack = self.config["stack"]
        stack_autodetect = self.config["stack_autodetect"]

        if stack is None and stack_autodetect == True:
            if prj_dir in cwd:
                strip_count = len(prj_dir)+1
                subdir = cwd[strip_count:]
                stack = subdir.split(os.sep)[0] or None
                self.log.debug (f"Auto detect stack because of sub: {stack}")

        self.runtime["stack"] = stack


    def cmd_build(self, stack=None):

        stack_name = stack or self.runtime['stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in stacks:
            log.notice(f"Building stack {stack.name}")
            stack.obj_source.install()
            stack.docker_assemble()


    def cmd_up(self, stack=None):

        stack_name = stack or self.runtime['stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in stacks:
            log.notice(f"Starting stack {stack.name}")
            stack.docker_up()


    def cmd_down(self, stack=None):

        stack_name = stack or self.runtime['stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        for stack in reversed(stacks):
            log.notice(f"Stopping stack {stack.name}")
            stack.docker_down()

    # Monitoring commands

    def cmd_ps(self, stack=None):

        stack_name = stack or self.runtime['stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        print(f"{'Project' :<32}   {'Name' :<40} {'Service' :<16} {'State' :<10} Ports")
        for stack in stacks:
            stack.docker_ps()

    def cmd_logs(self, stack=None, follow=False):

        stack_name = stack or self.runtime['stack']
        stacks = self.stacks.get_one_or_all(stack_name)
        
        if follow and len(stacks) > 1:
            raise Exception (f"Impossible to log follow on many stacks.")

        for stack in stacks:
            log.notice(f"Stack logs: {stack.name}")
            stack.docker_logs(follow=follow)


    def cmd_stacks_list(self):

        stacks = self.stacks.get_all_stacks()

        self.log.notice(f"List of stacks:")
        for stack in stacks:
            self.log.notice(f"- {stack.name}")


    # Source commands
    def cmd_src_list(self):
        sources = self.sources.get_all()

        print(f"{'Name' :<32}   {'Installed' :<14} {'git' :<14} {'URL' :<10}")
        for src in sources:
            is_installed = 'True' if src.is_installed() else 'False'
            is_git = 'True' if src.is_git() else 'False'
            print (f"  {src.name :<32} {is_installed :<14} {is_git :<14} {src.git_url :<10} ")

    def cmd_src_install(self):

        sources = self.sources.get_all()
        for src in sources:
            log.notice(f"Installing source: {src.name}")
            src.install()
            
    def cmd_src_update(self):

        sources = self.sources.get_all()
        for src in sources:
            log.notice(f"Updating source: {src.name}")
            src.update()
            
    def cmd_src_tree(self):

        path = self.sources.collection_dir
        cli_args = [
            '-a',
            '-I', '.git',
            '-L', '3',
            path
        ]
        _exec('tree', cli_args, _fg=True)
        
    def cmd_info(self):
        self.log.notice ("Main informations:")
        for k, v in self.runtime.items():
            if k not in ['project_config']:
                self.log.notice (f"  {k: >24}: {str(v)}")

        self.log.info ("Paasify config:")
        self.log.info (json.dumps(self.runtime['project_config'], indent=4, sort_keys=True))
      
        # Show stack list
        self.log.notice(f"Stack list:")
        for stack in self.stacks.get_all_stacks():
            tag_list = ','.join([x.name for x in stack.tags])
            self.log.notice(f"  {stack.name: >24}: {tag_list}")

        # Show current stack
        curr_stack = self.runtime["stack"]
        if not curr_stack:
            self.log.notice ("Paasify stack context: None")
        else:
            self.log.notice (f"Paasify stack context: {curr_stack}")
            stack = self.stacks.get_stacks_by_name(curr_stack)

            if len(stack) != 1:
                for x in self.root.stacks.store:
                    self.log.notice (json.dumps(x.__dict__, indent=4, sort_keys=True))
                raise Exception(f"Failed to find stack: {stack}")
            stack = stack[0]
            
            stack.dump()


class App(ClassClassifier):
    "Application instance"



    def __init__(self, **kwargs):

        super().__init__(None, user_config=kwargs)


    def _init(self, *args, **kwargs):

        self.runtime["cwd"] = os.getcwd()


    def get_project_path(self):
        "Find the closest paasify config file"

        cwd = self.runtime["cwd"]
        paths = list_parent_dirs(cwd)
        result = find_file_up( 
            ['paasify.yml', 'paasify.yaml'], paths )

        if len(result) > 0:
            result = result[0]

        return result


    def get_project(self):
        "Return closest project"

        # Find closest paasify.yml

        prj_path = self.get_project_path()
        user_config = {
            "config_file_path": prj_path,
        }

        return Project(self, user_config=user_config)


    def cmd_config_schema(self, format='json'):

        if format == 'json':
            return json.dumps(Project.schema_def, indent=4, sort_keys=True)

        elif format == 'yaml':
            return yaml.dump(Project.schema_def)
