

import os
import sys

import textwrap
import _jsonnet
import json
from pprint import pprint
import anyconfig


from cafram.nodes import NodeList, NodeMap, NodeDict, NodeVal
from cafram.utils import from_yaml, first, serialize, flatten, json_validate, duplicates, write_file

from paasify.common import lookup_candidates # serialize, , json_validate, duplicates
from paasify.framework import PaasifyObj, PaasifyConfigVars, PaasifySimpleDict
from paasify.engines import bin2utf8
from paasify.stack_tags import PaasifyStackTagManager, PaasifyStackTag
import paasify.errors as error




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
        self.collection_dir = os.path.join(
            self.prj.runtime.project_collection_dir, 
            self.app_source)
        self.app_dir = os.path.join(self.collection_dir, self.app_path)
        self.tags_dir = os.path.join(self.collection_dir, '.paasify', 'plugins')




    def lookup_docker_files_app(self):
        """Lookup docker-compose files in app directory"""

        lookup = [{
            "path": self.app_dir,
            "pattern": ["docker-compose.yml", "docker-compose.yml"],
        }]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([ x['matches'] for x in local_cand ])

        return local_cand

    def lookup_jsonnet_files_app(self):
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
        "tags_suffix": [],
        "tags_prefix": [],
        "vars": [],
        #"_runtime": {},
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
            "key": "app",
            "cls": PaasifyStackApp,
            "action": "unset",
            #"hook": "init_stack",

        },
        {
            "key": "tags",
            #"cls": PaasifyStackTagManager,
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
            "tags": PaasifyStackTagManager.conf_schema,
            "tags_prefix": PaasifyStackTagManager.conf_schema,
            "tags_suffix": PaasifyStackTagManager.conf_schema,
            "vars": PaasifyConfigVars.conf_schema,
        },
    }

    # conf_struct = {
    #     "name": str,
    #     "path": str,
    #     #"path": None,
    #     "app": PaasifyStackApp,
    #     "tags": PaasifyStackTagManager,
    #     "vars": PaasifyConfigVars,
    # }

    # CaFram functions
    # ---------------------

    def node_hook_transform(self, payload):

        # Internal attributes
        self.prj = self.get_parent().get_parent()
        assert self.prj.__class__.__name__ == 'PaasifyProject', f"Expected PaasifyProject, got: {self.prj}"

        # Ensure payload is a dict
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
        self.stack_name = self.get_name()
        self.name = self.stack_name   # Legacy code
        self.path = self.get_path()   # legacy code
        assert self.stack_name, f"Bug here, should not be empty"


        self.prj_dir = self.prj.runtime.root_path
        self.stack_dir = os.path.join(self.prj.runtime.root_path, self.stack_name)
        self.namespace = self.prj.config.namespace or os.path.basename( self.stack_name)  

        assert os.path.isdir(self.prj_dir)


        # Create engine instance
        prj_name = f"{os.path.basename(self.prj_dir)}_{self.get_name()}"
        payload = {
            "project_dir": self.prj_dir,
            "project_name": prj_name,
            "docker_file": os.path.join(self.prj_dir, "docker-compose.run.yml"),
        }
        self.engine = self.prj.engine_cls(parent=self, payload=payload)

        # Build tag list
        tag_list = self.tags_prefix or self.prj.config.tags_prefix + \
            self.tags or self.prj.config.tags + \
            self.tags_suffix or self.prj.config.tags_suffix        
        self.tag_manager = PaasifyStackTagManager(parent=self, ident="StackTagMgr", payload=tag_list)


    # Local functions
    # ---------------------

    def get_path(self):
        "Return stack relative path"

        result = self.path or self.name
        if self.app:
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


    def resolve_docker_file(self):
        "Return all docker-files candidates: local, app and tags"

        # Search in:
        # <local>/docker-compose.yml
        # <app>/docker-compose.yml
        # <local>/docker-compose.<tags>.yml
        # <app>/docker-compose.<tags>.yml

        # Get local docker compose
        lookup = [{
                "path": self.stack_dir,
                "pattern": ["docker-compose.yml", "docker-compose.yml"],
            }
        ]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([ x['matches'] for x in local_cand ])

        # Get app cand as fallback
        if len(local_cand) < 1 and self.app:
            local_cand = self.app.lookup_docker_files_app()

        # Filter result
        if len(local_cand) > 0:
            return local_cand[0]
        else:
            raise Exception ("Docker compose main file not found")

    def resolve_all_tags(self):
        "Resolve all tags"

        results = []

        # Generate base
        base = {
            "tag": None,
            "jsonnet_file":  None,
            "docker_file": self.resolve_docker_file(),
        }
        results.append(base)

        # Generate directory lookup for tags
        dirs = [
            self.stack_dir,
            self.prj.runtime.project_jsonnet_dir,
        ]
        if self.app:
            dirs.append(self.app.app_dir)
            dirs.append(self.app.tags_dir)

        # Actually find best candidates
        for tag in self.tag_manager.get_children():

            jsonnet_file = None
            docker_file = tag.lookup_docker_files_tag(dirs)
            if not docker_file:
                jsonnet_file = tag.lookup_jsonnet_files_tag(dirs)

            results.append(
                {
                    "tag": tag,
                    "jsonnet_file": first(jsonnet_file),
                    "docker_file": first(docker_file),
                }
            )

        return results



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

        # Update sources
        # TOFIX: Be more selective on the source
        assert len(self.prj.sources.get_children()) > 0, f"Missing default source!"
        for src_name, src in self.prj.sources.get_children().items():
            src.install(update=False)

        
        # Parse vars and find docker-compose files
        globvars = self.prj.config.vars
        localvars = self.vars

        vars_base = self.gen_conveniant_vars()
        vars_global = globvars.parse_vars(current=vars_base)
        vars_run = localvars.parse_vars(current=vars_global)

        # Report to user
        self.log.info("Docker vars:")
        for key, val in vars_run.items():
            self.log.info (f"  {key}: {val}")

        # Resolve all tags files
        all_tags = self.resolve_all_tags()

        # Build docker files list
        self.log.info("Docker files:")
        docker_files = []
        for cand in all_tags:
            docker_file = cand.get("docker_file")
            if docker_file:
                docker_files.append(docker_file)
                self.log.info (f"  Insert: {docker_file}")
        
        # Prepare docker-file output directory
        outfile = os.path.join(self.path, 'docker-compose.run.yml')
        if not os.path.isdir(self.path):
            self.log.info(f"Create missing directory: {self.path}")
            os.mkdir(self.path)

        # Build final docker file
        engine = self.engine
        try:
            out = engine.assemble(docker_files, env=vars_run)
        except Exception as err:
            err = bin2utf8(err)
            self.log.critical(err.txterr)
            raise err
            raise error.DockerBuildConfig(f"Impossible to build docker-compose files: ") from err

        # Fetch output
        docker_run_content = out.stdout.decode("utf-8")
        docker_run_payload = anyconfig.loads(docker_run_content, ac_parser='yaml')

        # Build jsonnet files
        self.log.info("Jsonnet files:")


        for cand in all_tags:
            docker_file = cand.get("docker_file")

            # Fetch only jsonnet if docker_file is absent
            if docker_file:
                continue
            jsonnet_file = cand.get("jsonnet_file")
            if not jsonnet_file:
                continue
            self.log.info (f"  Insert: {jsonnet_file}")

            # Create local environment vars
            jsonnet_data = cand.get("tag").vars or {}
            env_vars = dict(vars_run)
            env_vars.update(jsonnet_data)

            # Prepare jsonnet environment
            assert isinstance(jsonnet_data, dict), f"Error, env is not a dict, got: {type(jsonnet_data)}"
            ext_vars = {
                # ALL VALUES MUST BE JSON STRINGS
                "action": json.dumps("docker_transform"),
                "user_data": json.dumps(jsonnet_data),
                "docker_data": json.dumps(docker_run_payload),
            }

            # Process jsonnet tag
            try:
                result = _jsonnet.evaluate_file(
                    jsonnet_file, 
                    ext_vars=ext_vars,
                )
            except RuntimeError as err:
                self.log.critical(f"Can't parse jsonnet file: {jsonnet_file}")
                raise error.JsonnetBuildFailed(err)
            docker_run_payload = json.loads(result)


        # Save the final docker-compose.run.yml file
        self.log.info(f"Writing docker-compose file: {outfile}")
        write_file (outfile, docker_run_payload)

        return 


class PaasifyStackManager(NodeList,PaasifyObj):

    conf_schema={
        #"$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Stack configuration",
        "type": "array",
        "default": [],
        #"items": PaasifyStack.schema_def,
    }

    conf_children = PaasifyStack
        
    def conf_post_build(self):

        stack_paths = self.list_stack_by('path')
        stack_names = self.list_stack_by('name')

        dup = duplicates(stack_paths)
        if len(dup) > 0:
            raise error.ProjectInvalidConfig(f"Cannot have duplicate paths: {dup}")
  

    def list_stacks(self):
        return self.get_children()

    def list_stack_by_ident(self):
        return [x.ident for x in self.get_children()]

    def list_stack_by(self, attr='ident'):
        return [getattr(x, attr) for x in self.get_children()]


    # TODO: IS THIS ONE USED AT SOME POINTS ?
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