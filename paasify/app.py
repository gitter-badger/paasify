
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
            "tags_config": {
                "title": "Default tag configuration",
                "description": "Apply default tag configuration to your project",
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    '.*': {
                        "title": "Tag configuration",
                        "description": "Allow 3 config patterns",
                                
                        "oneOf": [
                            {
                                "title": "Simple tag configuration",
                                "description": "Define the tag settings in a dedicated object",
                                "type": "object"
                                },
                            {
                                "title": "Multi tag configuration",
                                "description": "Define the tag settings in a list of dedicated objects",
                                "type": "array"
                                },
                            {
                                "title": "Disable default configuration override",
                                "description": "Like it was commented",
                                "type": "null"
                                },
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
            raise Exception (f"Can't find 'paasify.yml' project")
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
            raise Exception(f"Failed to validate paasify.yml")

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
        
        #log.notice(f"Stack processes:")
        print(f"{'Project' :<32}   {'Name' :<40} {'Service' :<16} {'State' :<10} Ports")

        for stack in stacks:
            #log.notice(f"Stack processes: {stack.name}")
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
        self.log.info ("Main informations:")
        for k, v in self.runtime.items():
            if k not in ['project_config']:
                self.log.info (f"  {k: >20}: {str(v)}")

        self.log.info ("Paasify config:")
        self.log.info (pformat (self.runtime['project_config']))
      
        # Show current stack
        curr_stack = self.runtime["stack"]
        if not curr_stack:
            self.log.info ("Paasify stack context: None")
        else:
            self.log.info (f"Paasify stack context: {curr_stack}")
            stack = self.stacks.get_stacks_by_name(curr_stack)

            if len(stack) != 1:
                for x in self.root.stacks.store:
                    pprint (x.__dict__)
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













# =====================================================================
# Project management
# =====================================================================

# class ProjectConfig(ClassClassifier):
#     """
#     Class to hold config data
#     """

#     def _init(self):

#         self._init_attr_from_dict(self.user_config)

#     def __getattr__(self, name):
#         return None

#     def items(self):
#         """
#         Allow for config to be walkable
#         """

#         for k in self.keys:
#             yield (k, getattr(self, k))


class Project_OLD(ClassClassifier): # TO BE RENAMED APP !!!!

    # schema_project_def = {
    #     "$schema": "http://json-schema.org/draft-07/schema#",
    #     "type": "object",
    #     "title": "Paasify Project settings",
    #     "additionalProperties": False,
    #     "properties": {
    #         "namespace": {
    #             "type": "string",
    #         },
    #         "env": StackEnv.schema_def,
    #         "tags": {
    #             "type": "array",
    #             "items": StackTag.schema_def,
    #         },
    #         "tags_prefix": {
    #             "type": "array",
    #             "items": StackTag.schema_def,
    #         },
    #         "tags_suffix": {
    #             "type": "array",
    #             "items": StackTag.schema_def,
    #         },
    #         "tags_config": {
    #             "type": "object",
    #             "additionalProperties": False,
    #             "patternProperties": {
    #                 '.*': {
    #                     "oneOf": [
    #                         {"type": "object"},
    #                         {"type": "array"},
    #                         {"type": "null"},
    #                     ],
    #                 }
    #             },
    #         },
    #     }
    # }

    # schema_def={
    #     "$defs": {
    #         "Stacks": StackManager.schema_def,
    #         "Project": schema_project_def,
    #         "Sources": SourcesManager.schema_def,
    #     },
    #     "$schema": "http://json-schema.org/draft-07/schema#",
    #     "type": "object",
    #     "title": "Paasify Project configuration",
    #     "additionalProperties": False,
    #     "properties": {
    #         "project": {
    #             "$ref": "#/$defs/Project",
    #         },
    #         "sources": {
    #             "type": "object",
    #         },
    #         "stacks": {
    #             "$ref": "#/$defs/Stacks",
    #         },
            
    #     }
    # }

    #name = "Paasify"
    
    # default_user_config = {
    #         "config_path": "paasify.yml",
    #         "collections_dir": f"{Path.home()}/.config/paasify/collections",
    #     }

    # default_project_config = {
    #         "project": {
    #             "namespace": None,
    #             "env": [],
    #             "tags": [],
    #             "tags_suffix": [],
    #             "tags_prefix": [],
    #         },
    #         "sources": {},
    #         "stacks": []
    #     }

    def __init__(self, **kwargs):

        super().__init__(None, user_config=kwargs)


    # def __init__(self, user_config=None, logguer_name=None, *args, **kwargs):

    #     self.root = self
    #     self.parent = self
    #     self.name = "PaasifyProject"
    #     self.log = logging.getLogger(f"paasify.{self.__class__.__name__}.{self.name}")

    #     self._init(*args, **kwargs)

    #     self.log.trace("Application started!")


    def require_init(self):
        self._init2()



    def _init2(self): #, **kwarg_config):
        """
        Generate application context
        """

        #pprint (self.schema_def)

        
    
        config_path = self.user_config["config_path"]
        if config_path and os.access(config_path, os.R_OK):
            config_path = config_path
        else:

            # Get context and parents
            cwd = os.getcwd()
            search_dir = config_path or cwd

        search_paths = list_parent_dirs(search_dir)

        # project_root_configs = find_file_up( 
        #     ['paasify.yml', 'paasify.yaml'], search_paths )
            
        
        

        # # Process nested projects
        # project_level = len(project_root_configs)
        # if project_level == 0:
        #     raise Exception("Can't find 'paassify.yml' config in current or parent dirs")
        # elif project_level == 1:
        #     self.log.debug("Context: Root project")
        # else:
        #     self.log.debug(f"Context: Subproject of level: {project_level}")
        # project_config_path = project_root_configs[0]
        # project_dir = os.path.dirname(project_config_path)

        # # Detect default stack context
        # subdir = None
        # if project_dir in cwd:
        #     strip_count = len(project_dir)+1
        #     subdir = cwd[strip_count:]
        #     stack = subdir.split(os.sep)[0] or None
        #     self.log.debug (f"Auto detect stack because of sub: {stack}")


        # # Load anyconfig
        # project_config = dict(self.default_project_config)
        # project_config.update(anyconfig.load(project_config_path))
        # rc, rc_msg = anyconfig.validate(project_config, self.schema_def)
        # if not rc:
        #     self.log.warn(f"Failed to validate paasify.yml, please check details with: -v")
        #     self.log.info(f"Code: {rc}, {rc_msg}")
        #     sys.exit(1)
        #     #pprint (rc_msg)
        #     raise Exception(f"Failed to validate paasify.yml")


        # prj_namespace = project_config['project'].get('namespace', None) or os.path.basename(project_dir)

        # Generate new config
        runtime_config = {
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
            'stack': stack,


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
        runtime.update(runtime_config)
        #self.config = runtime
        
        # self.project_config = project_config

        # # Init public sub-objects
        # self.runtime = runtime   # Replace with ProjectConfig !!!
        # self.project = ProjectConfig(self, user_config=project_config.get('project', {}))
        # self.sources = SourcesManager(self, user_config=project_config.get('sources', {}))
        # self.stacks = StackManager(self, user_config=project_config.get('stacks', []))

        # self.log.info ("This must not be empty ")
        # pprint(self.stacks.dump_stacks())
        # sys.exit()
        

    # def cmd_info(self):
    #     self.log.info ("Main informations:")
    #     for k, v in self.runtime.items():
    #         if k not in ['project_config']:
    #             self.log.info (f"  {k: >20}: {str(v)}")

    #     self.log.info ("Paasify config:")
    #     self.log.info (pformat (self.project_config))

        
    #     # Show current stack

    #     curr_stack = self.runtime["stack"]
    #     if not curr_stack:
    #         self.log.info ("Paasify stack context: None")
    #     else:
    #         self.log.info (f"Paasify stack context: {curr_stack}")
    #         stack = self.stacks.get_stacks_by_name(curr_stack)

    #         if len(stack) != 1:
    #             #pprint ()
    #             for x in self.root.stacks.store:
    #                 pprint (x.__dict__)
    #             raise Exception(f"Failed to find stack: {stack}")
    #         stack = stack[0]

    #        # pprint (stack.)

    #         stack.dump()
            

    # def cmd_build(self, stack=None):

    #     print ("Require build")
    #     self.require_init()

    #     stack_name = stack or self.runtime['stack']
    #     stacks = self.stacks.get_one_or_all(stack_name)

    #     print ("Require build: Done")
        

    #     for stack in stacks:
    #         stack.docker_assemble()


    # def cmd_up(self, stack=None):

    #     stack_name = stack or self.runtime['stack']
    #     stacks = self.stacks.get_one_or_all(stack_name)
        
    #     for stack in stacks:
    #         stack.docker_up()


    # def cmd_down(self, stack=None):

    #     stack_name = stack or self.runtime['stack']
    #     stacks = self.stacks.get_one_or_all(stack_name)
        
    #     for stack in stacks:
    #         stack.docker_down()

    # # Monitoring commands

    # def cmd_ps(self, stack=None):

    #     stack_name = stack or self.runtime['stack']
    #     stacks = self.stacks.get_one_or_all(stack_name)
        
    #     for stack in stacks:
    #         stack.docker_ps()

    # def cmd_logs(self, stack=None, follow=False):

    #     stack_name = stack or self.runtime['stack']
    #     stacks = self.stacks.get_one_or_all(stack_name)
        
    #     if follow and len(stacks) > 1:
    #         raise Exception (f"Impossible to log follow on many stacks.")

    #     for stack in stacks:
    #         stack.docker_logs(follow=follow)


    # def cmd_stacks_list(self):

    #     stacks = self.stacks.get_all_stacks()

    #     self.log.notice(f"List of stacks:")
    #     for stack in stacks:
    #         self.log.notice(f"- {stack.name}")

    # def cmd_config_schema(self, format='json'):

    #     if format == 'json':
    #         return json.dumps(self.schema_def, indent=4, sort_keys=True)

    #     elif format == 'yaml':
    #         return yaml.dump(self.schema_def)
