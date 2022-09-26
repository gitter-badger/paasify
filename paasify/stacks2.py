

import os
import sys

import textwrap
from pprint import pprint


from cafram.nodes import NodeList, NodeMap, NodeDict, NodeVal
from cafram.utils import serialize, flatten, json_validate, duplicates, write_file

from paasify.common import lookup_candidates # serialize, , json_validate, duplicates
from paasify.framework import PaasifyObj, PaasifyConfigVars, PaasifySimpleDict
from paasify.engines import bin2utf8
import paasify.errors as error




class PaasifyStackTag(NodeMap, PaasifyObj):

    conf_schema={
        #"$schema": "http://json-schema.org/draft-07/schema#",
        "title": "StackTag configuration",

        "oneOf":[
            {
                "type": "string",
                "oneOf": [
                    {
                        "title": "Reference sourced app",
                        "pattern": "^.*:.*$",
                    },
                    {
                        "title": "Direct or absolute app path",
                        "pattern": "^.*$",
                    },
                ],
            },
            {
                "type": "object",
                "additionalProperties": False,
                "patternProperties": {
                    '.*': {
                        "oneOf": [
                            {"type": "object"},
                            {"type": "null"},
                        ],
                    }
                },
            },

        ],
    }


    conf_ident = "{self.name}={self.vars}"

    conf_children = [
        {
            "key": "name",
            "cls": str,
        },
        {
            "key": "vars",
            #"cls": dict,
        },
    ]
    #     {
    #     "name": str,
    #     "vars": dict,
    # }

    def node_hook_transform(self, payload):

        result = {
            'name': None,
            'vars': {},
        }
        if isinstance(payload, str):
            result["name"] = payload

        elif isinstance(payload, dict):

            keys = list(payload.keys())
            if len(keys) == 1:

                for key, val in payload.items():
                    result["name"] = key
                    result["vars"] = val
            elif len(keys) == 0:
                raise Exception(f"Missing tag name: {payload}")
            else:
                result.update(payload)
            
        else:
            raise Exception(f"Not supported type: {payload}")

        return result


    def node_hook_children(self):
        "Self init object after loading of app"

        self.prj = self.get_parent()
        self.app = self.get_parents()

        #print("TAG", self, self.get_parents())
        #totooo

        # self.app_dir = os.path.join(
        #     self.prj.runtime.project_root_dir, 
        #     '.paasify', 'collections', 
        #     self.app_source, self.app_path)


    def lookup_docker_files_tag(self, dirs):
        """Lookup docker-compose files in app directory"""
        #return []

        lookup =  []
        for dir_ in dirs:
            lookup_def = {
                "path": dir_,
                "pattern": [
                    f"docker-compose.{self.name}.yml", 
                    f"docker-compose.{self.name}.yml"],
            }
            lookup.append(lookup_def)

        #pprint(lookup)

        local_cand = lookup_candidates(lookup)
        local_cand = flatten([ x['matches'] for x in local_cand ])

        return local_cand


    # def lookup_docker_files_tag(self):

    #     return [f"TAG docker-compose.{self.name}.yml"]

class PaasifyStackTags(NodeList, PaasifyObj):

    conf_schema={
        #"$schema": "http://json-schema.org/draft-07/schema#",

        "title": "Paasify Stack Tags configuration",
        "default": [],
        "oneOf":[
            {
                "type": "array",
                "items": PaasifyStackTag.conf_schema,
            },
            {
                "type": "null",
            },
        ],

    }

    conf_children = PaasifyStackTag

    def list_tags(self):
        return self._nodes


class PaasifyStackApp (NodeMap, PaasifyObj):
    
    conf_default = {
        "app": None,
        "app_source": None,
        "app_path": None,
        "app_name": None,
    }

    def node_hook_transform(self, payload):

        if isinstance(payload, str):
            payload = {
                "app": payload
            }

        app_def = payload.get("app")
        app_path = payload.get("app_path")
        app_source = payload.get("app_source")
        app_name = payload.get("app_name")

        app_split = app_def.split(':', 2)

        if len(app_split) == 2:
            app_source = app_source or app_split[0] or 'default'
            app_path = app_path or app_split[1]
        else:
            # Get from default namespace
            app_name = app_source or app_split[0] or 'default'
            app_source = "default"
            app_path = app_name
        app_def = f"{app_source}:{app_path}"

        if not app_name:
            app_name = '_'.join([ part for part in os.path.split(app_path) if part])

        result = {
            "app": app_def,
            "app_path": app_path,
            "app_source": app_source,
            "app_name": app_name,
        }

        return result

    def node_hook_children(self):
        "Self init object after loading of app"

        self.prj = self.get_parents()[2]
        self.app_dir = os.path.join(
            self.prj.runtime.project_root_dir, 
            '.paasify', 'collections', 
            self.app_source, self.app_path)


    def lookup_docker_files_app(self):
        """Lookup docker-compose files in app directory"""

        lookup = [{
            "path": self.app_dir,
            "pattern": ["docker-compose.yml", "docker-compose.yml"],
        }]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([ x['matches'] for x in local_cand ])

        return local_cand




class PaasifyStack(NodeMap, PaasifyObj):

    conf_ident = "{self.path}"

    conf_default = {
        "path": None,
        "name": None,
        "app": None,
        "tags": [],
        "vars": [],
        "_runtime": {},
        #"TEST": "DEFAULT BUUUG",
    }

    conf_children = [
        # {
        #     "key": "name",
        #     "cls": str,
        # },
        # {
        #     "key": "path",
        #     "cls": str,
        # },
        {
            "key": "_runtime",
            "cls": PaasifySimpleDict,
            "attr": "runtime",
            "default": {},
        },
        {
            "key": "app",
            "cls": PaasifyStackApp,
            "action": "unset",
            #"hook": "init_stack",

        },
        {
            "key": "tags",
            "cls": PaasifyStackTags,
        },
        {
            "key": "vars",
            "cls": PaasifyConfigVars,
        },
        # {
        #     "key": "TEST",
        #     "cls": NodeVal,
        #     "default": "My STirng Value",
        # },
    ]

    conf_schema={
        #"$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Stack configuration",
        "additionalProperties": False,
        "default": conf_default,
        "properties": {
            "name": {
                "type": "string",
            },
            "path": {
                "type": "string",
            },
            "app": {
                "type": "string",
            },
            "tags": PaasifyStackTags.conf_schema,
            "tags_prefix": PaasifyStackTags.conf_schema,
            "tags_suffix": PaasifyStackTags.conf_schema,
            "vars": PaasifyConfigVars.conf_schema,
        },
    }

    # conf_struct = {
    #     "name": str,
    #     "path": str,
    #     #"path": None,
    #     "app": PaasifyStackApp,
    #     "tags": PaasifyStackTags,
    #     "vars": PaasifyConfigVars,
    # }

    # CaFram functions
    # ---------------------

    def node_hook_transform(self, payload):

        if isinstance(payload, str):
            if ':' in payload:
                payload = {
                    "app": payload
                }
            else:
                payload = {
                    "path": payload,
                    #"name": payload,
                }
        
        return payload

    def node_hook_children(self):
        "Self init object after loading of app"


        # Config update
        self.name = self.get_name()
        self.path = self.get_path()
        assert self.name, f"Bug here, should not be empty"

        # Internal attributes
        self.prj = self.get_parents()[1]
        self.prj_dir = self.prj.runtime.project_root_dir
        self.namespace = self.prj.config.namespace or os.path.basename( self.prj_dir)  

        assert os.path.isdir(self.prj_dir)

        #pprint (self.prj.runtime.get_value())
        #self.runtime.deserialize(self.prj.runtime.get_value())
        #self.runtime = dict(self.prj.runtime.get_value())

        #pprint(self.prj.__dict__)



    # Local functions
    # ---------------------

    def get_path(self):
        "Return stack relative path"

        result = self.path or self.name
        if self.app:
            #pprint (self.app)
            result =  result or self.app.app_name        

        return result

    def get_name(self):
        "Return stack name"

        result = self.name or self.get_path().replace(os.path.sep, '_')
        if self.app:
            result = result or self.app.app_name

        return result

    # Local functions
    # ---------------------

    def lookup_docker_files(self):
        "Return all docker-files candidates: local, app and tags"

        # Get local docker compose
        lookup = [{
            "path": self.prj_dir,
            # TOFIX: Use project config setting !
            "pattern": ["docker-compose.yml", "docker-compose.yml"],
        }]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([ x['matches'] for x in local_cand ])

        # Get app cand
        app_cand = []
        if self.app:
            app_cand = self.app.lookup_docker_files_app()

       
        # Get tags candidates
        tags_cand = []
        for tag in self.tags:
            cand = tag.lookup_docker_files_tag(dirs=[self.prj_dir, self.app.app_dir, self.prj.runtime.project_collection_dir])
            tags_cand.append(cand)


        result = []
        result.append(local_cand)
        result.append(app_cand)
        result.append(tags_cand)
        result = flatten(result)

        return result


    def gen_conveniant_vars(self):
        "Generate default available variables"
        
        app_dir = self.path
        result = {
            "app_network_name": self.namespace,
            "app_image": "TOTO",

            "app_dir": app_dir,
            "app_dir_conf": './' + os.path.join(app_dir, 'conf'),
            "app_dir_data": './' + os.path.join(app_dir, 'data'),
            "app_dir_logs": './' + os.path.join(app_dir, 'logs'),
        }
        return result

    def assemble(self):
        "Generate docker-compose.run.yml and parse it with jsonnet"

        print (f"Build the stack: {self}")

        
        # Parse vars and find docker-compose files
        globvars = self.prj.config.vars
        localvars = self.vars

        vars_base = self.gen_conveniant_vars()
        vars_global = globvars.parse_vars(current=vars_base)
        vars_run = localvars.parse_vars(current=vars_global)

        docker_files = self.lookup_docker_files()

        # Report to user
        self.log.info("Docker vars:")
        for key, val in vars_run.items():
            self.log.info (f"  {key}: {val}")

        self.log.info("Docker files:")
        for dfile in docker_files:
            self.log.info (f"  Insert: {dfile}")
        
        # Build docker file
        engine = self.prj.engine(parent=self)
        try:
            out = engine.assemble(docker_files, env=vars_run)
        except Exception as err:
            err = bin2utf8(err)
            self.log.critical(err.txterr)
            #sys.exit(1)
            raise err
            raise error.DockerBuildConfig(f"Impossible to build docker-compose files: ") from err

        #write_file (dfile, out)

        self.prj.dump()
        pprint (self.prj.get_value())


        #engine
        print ("  Parse jsonnet")








class PaasifyStacks(NodeList,PaasifyObj):

    conf_schema={
        #"$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Stack configuration",
        "type": "array",
        "default": [],
        #"items": PaasifyStack.schema_def,
    }

    conf_children = PaasifyStack

    # def _init(self, *args, **kwargs):

        
    def conf_post_build(self):

        stack_paths = self.list_stack_by('path')
        stack_names = self.list_stack_by('name')

        dup = duplicates(stack_paths)
        if len(dup) > 0:
            raise error.ProjectInvalidConfig(f"Cannot have duplicate paths: {dup}")
  
        #return payload





    def list_stacks(self):
        return self.get_children()

    def list_stack_by_ident(self):
        return [x.ident for x in self.get_children()]

    def list_stack_by(self, attr='ident'):
        return [getattr(x, attr) for x in self.get_children()]


    def cmd_stack_assemble(self, stacks=None):

        stacks = stacks or self._nodes
        for stack in stacks:
            print (stack)

            #stack.assemble()

    def cmd_stack_up(self, stacks=None):

        stacks = stacks or self._nodes
        for stack in stacks:
            stack.up()

    def cmd_stack_down(self, stacks=None):

        stacks = stacks or self._nodes
        for stack in stacks:
            stack.down()


    def cmd_stack_recreate(self, stacks=None):

        self.cmd_stack_down(stacks=stacks)
        self.cmd_stack_assemble(stacks=stacks)
        self.cmd_stack_up(stacks=stacks)
        

    def cmd_stack_apply(self, stacks=None):

        self.cmd_stack_assemble(stacks=stacks)
        self.cmd_stack_up(stacks=stacks)