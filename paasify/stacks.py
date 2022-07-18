

import os
import sys
import re
import logging
import json

import yaml
import anyconfig
import sh
import _jsonnet

from pprint import pprint, pformat

from paasify.common import *
from paasify.class_model import ClassClassifier


log = logging.getLogger(__name__)

# =====================================================================
# StackEnv
# =====================================================================

class StackEnv(ClassClassifier):

    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "StackEnv configuration",

        "oneOf": [
            {
                "type": "object",
                "patternProperties": {
                    '.*': {
                        "oneOf": [
                            {"type": "string"},
                            {"type": "null"},
                        ],
                    }
                },
            },
            {
                "type": "array",
                "items": {
                    "type": "string"
                }
            },
        ],
    }


# =====================================================================
# StackTags management
# =====================================================================

class StackTag(ClassClassifier):

    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
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
    
    
    def _init(self, lookup_mode='public'):

        self.lookup_mode = lookup_mode
        self._exec = self.parent._exec


        # Init config, features
        self.cand_jsonnet_script, self.cand_jsonnet_vars = self.lookup_jsonnet()
        self.cand_composefile = self.lookup_docker_files()


    def get_candidates(self, store):
        "Return the list of all candidates"

        store = getattr(self, store, None)
        assert isinstance(store, list), f"Not a list :("

        result = []
        for item in store:

            candidates = [ x for x in item["matches"] if len(item["matches"]) > 0 ]
            result.extend(candidates)

        return result


    def has_jsonnet_support(self):
        "Return true if this tag can run jsonnet processing"
        if len(self.get_candidates("cand_jsonnet_script")) > 0:
            return True
        return False


    # Docker file lookup management
    # =============================

    def process_jsonnet(self, docker_data):
        "Transform docker-compose with jsonnet filter"

        # Select first jsonnet script candidate        
        jsonnet_src_path = self.get_candidates("cand_jsonnet_script")
        if len(jsonnet_src_path) < 1:
            raise Exception("Can't run jsonnet on this tag")
        jsonnet_src_path = jsonnet_src_path[0]

        # Fetch data
        vendor_config_files = self.get_candidates("cand_jsonnet_vars")
        

        
        vendor_config = anyconfig.load(vendor_config_files, ac_merge=anyconfig.MS_DICTS_AND_LISTS) if vendor_config_files else {}
        project_config = self.root.project.tags_config.get(self.name, {})
        user_config = self.user_config["local_config"]

        # prepare ext_vars
        user_data = {}
        user_data.update(vendor_config)
        user_data.update(project_config)
        user_data.update(user_config)
        ext_vars = {
            "user_data": user_data, # overrides possible from paasify.yml only
            "docker_data": docker_data, # Current state of the compose file
        }    
        self.log.trace(f"Jsonnet vars:  (script:{jsonnet_src_path})")
        self.log.trace(pformat (ext_vars))

        # Execute jsonnet
        ext_vars = {k: json.dumps(v) for k, v in ext_vars.items() }
        docker_data = _jsonnet.evaluate_file(
            jsonnet_src_path, # The actual jsonnet file
            ext_vars = ext_vars,
        )
        docker_data = json.loads(docker_data)

        self.log.trace("Tag jsonnet result:")
        self.log.trace(pformat (docker_data))

        return docker_data

        # Deprecated
        cli_args = [
            "--ext-str-file", f"user_data=$target/paasify.yml",
            "--ext-str-file", f"vendor_data=$target/vendor.yml",
            "--ext-str-file", f"docker_data=$target/docker-compose.yml",
            jsonnet_src_path
        ]
        self._exec("jsonnet", cli_args, _fg=True)

        print (f"Exec jsonnet --ext-str-file user_data=DOCKER_FILE --ext-str-file vendor_data=VENDOR.yml docker_data  JSONNET.jsonnet")




    def lookup_jsonnet(self):
        "Generate candidates for jsonnet parsing"

        stack = self.parent
        tag = self.name

        # Prepare main config
        lookup_config_jsonnet = [
            {
                "path": stack.path,
                "pattern": [
                    f"paasify.{tag}.jsonnet",
                    f"paasify/{tag}.jsonnet",
                ],
            },
            {
                "path": stack.app_path,
                "pattern": [
                    f"paasify.{tag}.jsonnet",
                    f"paasify/{tag}.jsonnet",
                ],
            },
            {
                "path": self.runtime['top_project_dir'],
                "pattern": [
                    f"{tag}.jsonnet",
                    #f"paasify/{tag}.jsonnet",
                ],
            },
            {
                "path": self.runtime['plugins_dir'],
                "pattern": [
                    f"{tag}.jsonnet",
                    #f"paasify/{tag}.jsonnet",
                ],
            },
        ]

        # Generate vars lookups
        lookup_config_jsonnet_vars = []
        for path_config in lookup_config_jsonnet:
            patterns = path_config["pattern"]
            new_config = dict(path_config)
            new_config["pattern"] = [x.replace(f"{tag}.jsonnet", f"{tag}.vars.yml") for x in patterns]
            lookup_config_jsonnet_vars.append(new_config)
        

       # Generate output result
        result = []
        for lookups in [lookup_config_jsonnet, lookup_config_jsonnet_vars]:
            lookup_result = []
            for lookup in lookups:

                if lookup["path"]:
                    cand = filter_existing_files(
                        lookup["path"],
                        lookup["pattern"])


                    lookup["matches"] = cand
                    lookup_result.append(lookup)

            result.append(lookup_result)
            
        return result[0], result[1]



    def lookup_docker_files(self):
        "Generate candidates for jsonnet parsing"

        stack = self.parent
        tag = self.name

        # Prepare main config
        lookup_config_dfile = [
            {
                "path": stack.path,
                "pattern": [
                    f"docker-compose.{tag}.yml",
                    f"docker-compose.{tag}.yaml",
                    f"paasify/{tag}.yml",
                    f"paasify/{tag}.yaml",
                ],
            },
            {
                "path": stack.app_path,
                "pattern": [
                    f"docker-compose.{tag}.yml",
                    f"docker-compose.{tag}.yaml",
                    f"paasify/{tag}.yml",
                    f"paasify/{tag}.yaml",
                ],
            },
            {
                "path": self.runtime['plugins_dir'],
                "pattern": [
                    f"{tag}.yml",
                    f"{tag}.yaml",
                ],
            },
        ]

        # # Generate vars lookups
        # lookup_config_jsonnet_vars = []
        # for path_config in lookup_config_jsonnet:

        #     patterns = path_config["pattern"]
        #     new_config = dict(path_config)
        #     new_config["pattern"] = [x.replace(f"{tag}.jsonnet", f"{tag}.vars.yml") for x in patterns]
        #     lookup_config_jsonnet_vars.append(new_config)
        
       # Generate output result
        result = []
        for lookups in [lookup_config_dfile]:
            lookup_result = []
            for lookup in lookups:
                if lookup["path"]:
                    cand = filter_existing_files(
                        lookup["path"],
                        lookup["pattern"])


                    lookup["matches"] = cand
                    lookup_result.append(lookup)

            result.append(lookup_result)
            
        return result[0] #, result[1]




    def lookup_docker_compose_files(self): # DEPRECATED, replaced by: lookup_docker_files
        "This method return the list of files to add to docker-compose build"
        "Generate candidates for docker-compose file merging"
        stack = self.parent
        tag = self.name
        # Lookup dirs:
        # - local dir
        # - app collection dir (optional)
        # - internal plugin search

        std_lookup_order = [
            #f"/docker-compose.{tag}.jsonnet",
            f"docker-compose.{tag}.yml",
            f"docker-compose.{tag}.yaml",

            #f"{root_path}/paasify/{tag}.jsonnet",
            f"paasify/{tag}.yml",
            f"paasify/{tag}.yaml",

            # Useful when moving files ...
            #f"/docker-compose.{tag}.jsonnet",
            f"paasify/docker-compose.{tag}.yml",
            f"paasify/docker-compose.{tag}.yaml",
        ]

        internal_lookup_order = [
            f"{tag}.yml",
            f"{tag}.yaml",
        ]

        # self.log.debug (stack.path)
        # self.log.debug (stack.app_path)
        # self.log.debug (self.runtime['plugins_dir'])

        r1 = filter_existing_files(stack.path,
            std_lookup_order)

        r2 = filter_existing_files(stack.app_path,
            std_lookup_order) if stack.app_path else []

        r3 = filter_existing_files(
            self.runtime['plugins_dir'],
            internal_lookup_order)

        result = r1 + r2 + r3

        return result




# =====================================================================
# Stack Object
# =====================================================================


class Stack(ClassClassifier):
    """ A stack instance
    """

    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "title": "Paasify Stack configuration",
        "additionalProperties": False,
        "properties": {
            "path": {
                "type": "string",
            },
            "app": {
                "type": "string",
            },
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
            "env": StackEnv.schema_def,
        },
    }

    default_user_config = {
            "name": None,
            "path": None,
            "app": None,
            "tags": [],
            "env": [],
        }

    def _init(self):

        # Generate config
        config = dict(self.default_user_config)
        #config.update(default_config)
        config.update(self.user_config)

        # Sanity check
        #pprint (config)
        fail_on_app=True
        app_name = config["app"] or config["name"] or config["path"] or None
        if not app_name:
            raise Exception(f"Missing 'app' or 'path' or 'name' option for stack: {self.default_user_config}")
        if not config["app"]:
            fail_on_app=False
        default_name = re.sub(f'[^:]+:', '', app_name)

        # Ensure config
        config["name"] = config["name"] if config["name"] else default_name
        #config["app"] = config["app"] if config["app"] else None
        config["path"] = config["path"] if config["path"] else default_name
        config["name"] = config["name"].replace(os.sep, config["name"])
        config["name"] = re.sub(f'[^0-9a-zA-Z{os.sep}-]+', '_', config["name"])


        # Init object
        #self.name = config["name"] or self.short_path.replace(os.sep, '_')
        self.short_path = config.get('path')
        self.name = config["name"]

        self.project_dir = self.root.runtime['project_dir']
        self.ns = self.root.runtime['namespace']
        self.project_name = f"{self.ns}_{self.name}"
        self.path = os.path.join(self.project_dir, self.short_path)
        


        # Resolve resource
        self.config = config

        # if fail_on_app
        self.app_path = self.resolve_app(config['app'])
        self.tags_names = self._get_raw_tag_config()
        self.tags = self._get_tags(self.tags_names)
        
    def _dump(self):

        self.log.notice ("Misc:")
        self.log.notice (f"Path: {self.path}")
        self.log.notice (pformat (self.config))

        self.log.notice ("Env:")
        self.log.notice (pformat (self.parse_env()))

        self.log.notice ("Tags:")
        tags = self.tags
        #self.log.info (pformat (tags))


        self.log.notice ("Docker-compose config:")
        stores =  ["cand_composefile"]
        for tag in tags:
            self.log.notice (f"  - Name: {tag.name}")

            for sub_item in stores:
                candidates = tag.get_candidates(sub_item)
                if len(candidates) > 0:
                    self.log.notice (f"    {sub_item}: ({len(candidates)} candidates)")
                    for cand in candidates:
                        self.log.notice(f"      - {cand}")

        self.log.notice ("Processor config:")
        stores =  ["cand_jsonnet_script", "cand_jsonnet_vars"]
        for tag in tags:
            self.log.notice (f"  - Name: {tag.name}")

            for sub_item in stores:
                candidates = tag.get_candidates(sub_item)
                if len(candidates) > 0:
                    self.log.notice (f"    {sub_item}: ({len(candidates)} candidates)")
                    for cand in candidates:
                        self.log.notice(f"      - {cand}")

    
    # Misc
    # ----------------------

    def _get_raw_tag_config(self):
        "Return the list of tags after merge"

        # Merge global and local tags
        default_tags = {
            "tags": [],
            "tags_auto": ["user", self.root.project.namespace ],
            "tags_prefix": [],
            "tags_suffix": [],
        }
        global_tags = { k: v for k, v in self.root.project.items() if k.startswith("tags") and v}
        local_tags = { k: v for k, v in self.user_config.items() if k.startswith("tags") and v}

        default_tags.update(global_tags)
        default_tags.update(local_tags)

        tags = default_tags["tags_prefix"] + default_tags["tags_auto"] + default_tags["tags"] + default_tags["tags_suffix"]
        return tags


    def _get_tags(self, tags_names):
        "Create and return a list of StackTags objects"

        # Preparse tag structure
        tags = []
        for tag_def in tags_names:

            tag_name = tag_def
            tag_conf = {}

            # Long form config
            if isinstance(tag_def, dict):
                # Assume the name of the first key
                tag_name = list(tag_def.keys())[0]
                tag_conf = tag_def[tag_name]


            #print ("ADD TAG", tag_name, tag_conf)

            # Check if not already present ?
            cand =  [ x for x in tags if x["name"] == tag_name ]
            if len(cand) > 0:
                cand = cand[0]
                if tag_conf:
                    cand["local_config"].update(tag_conf)
            else:
                new_tag = {
                    "name": tag_name,
                    "local_config": tag_conf,
                }
                tags.append(new_tag)


        # Remove exclusions ["name"][1:]
        exclude = [ tag["name"][1:] for tag in tags if tag["name"].startswith('-') or tag["name"].startswith('~') or tag["name"].startswith('!') ]
        tags = [ tag for tag in tags if tag["name"] not in exclude ]

        # Create tags instances
        tags = [ StackTag(self, name=tag["name"], user_config=new_tag) for tag in tags ]
        return tags


    def resolve_app(self, app_def):
        "Find the associated source"

        if not app_def:
            return None

        # Parse format
        if ':' in app_def:
            app_src = app_def.split(':')[0]
            app_target = app_def.split(':')[1]

            source = self.root.sources.get_source(app_src)
            assert source, f"Could not find source: {app_src} for {stack_def}"
            app_path = os.path.join( source.path, app_target)
        else:
            app_src = None
            app_target = app_def
            app_path = os.path.join( self.runtime["cwd"], app_target)

        return app_path

    # Environment related tasks
    # ----------------------
    def parse_env(self):
        "Return a dict of the environment variables"
        global_env = self.root.project.env
        local_env = self.config["env"]

        r0 = {}
        if self.app_path:
            app_env_file = filter_existing_files(self.app_path, [".env"])
            if len(app_env_file) > 0:
                r0 = anyconfig.load(app_env_file, ac_parser="shellvars")


        r1 = self._parse_env_struct(global_env)
        r2 = self._env_inject()
        r3 = self._parse_env_struct(local_env)


        result = {}
        result.update(r0)
        result.update(r1)
        result.update(r2)
        result.update(r3)

        # DYNAMIC VARS
        overrides = {
            "APP_DOMAIN": result["APP_NAME"] + '.' + result["APP_TOP_DOMAIN"]
        }
        for key, val in overrides.items():
            if not key in result:
                result[key]=val

        return result

    def _env_read_in_parents(self):
        "Read env_file in parent app if exists"
        result={}
        return

    def _env_inject(self):
        ns = self.runtime["namespace"]

        result = {
            "APP_NAME": self.name,
            "APP_NAMESPACE": ns,
            "APP_PROJECT_DIR": self.runtime["project_dir"],
            "APP_COLLECTION_DIR": self.runtime["collections_dir"],

            # front_network
            #"APP_TRAEFIK_NETWORK": f"{ns}_traefik",
            "APP_NETWORK": f"{ns}_{self.name}",

            # Expose Tag
            "APP_EXPOSE_IP": "127.0.0.1",

            "APP_PROJECT_DIR": self.runtime["project_dir"],
            "APP_PROJECT_DIR": self.runtime["project_dir"],
            "APP_PROJECT_DIR": self.runtime["project_dir"],

        }
        return result

    def _parse_env_struct(self, payload):

        if isinstance(payload, list):
            result = {}
            for stmt in payload:
                stmt = stmt.split("=", 2)
                key = stmt[0]
                value = stmt[1]
                result[key] = value
            return result
        elif isinstance(payload, dict):
            return payload
        else:
            return {}


    # Docker related tasks
    # ----------------------

    def list_docker_compose_files_from_tags(self, tags=None):
        "Return stack tags"

        tags = tags or self.tags

        runbook = []

        # Insert default docker-config
        cand = filter_existing_files(
            self.path,
            [f"docker-compose.yml",
            f"docker-compose.yaml",
            ]) 
        if self.app_path:
            cand.append(filter_existing_files(
                self.app_path,
                [f"docker-compose.yml",
                f"docker-compose.yaml",
            ]))

        if len(cand) > 0:
            runbook.append({'tag': None, 'candidates': cand})
            

        # Insert tags docker-files
        for tag in tags:
            cand = tag.lookup_docker_compose_files()
            if len(cand) > 0:
                runbook.append({'tag': tag, 'candidates': cand})

        return runbook

    def docker_generate_envfile(self, env=None):
        "Generate .env file focker docker-compose"

        env = env or self.parse_env()
        dst_file = os.path.join(self.path, '.env')

        file_content = []
        for var, val in env.items():
            file_content.append(f'{var}="{val}"')

        self.log.trace(f"Preparing .env file: {dst_file}")
        self.log.trace(pformat(file_content))

        file_content = '\n'.join(file_content) + '\n'
        with open(dst_file, 'w') as writer:
            writer.write(file_content)

        self.log.info (f"Environment file created/updated: {dst_file}")






    # Docker Execution framework

    def _exec(self, command, cli_args=None, _log=True, **kwargs):
        "Execute a command"

        # Check arguments
        cli_args = cli_args or []
        assert isinstance(cli_args, list), f"_exec require a list, not: {type(cli_args)}"

        # Prepare context
        sh_opts = {
            '_in': sys.stdin,
            '_out': sys.stdout,
        }
        sh_opts = kwargs or sh_opts

        # Bake command
        dc = sh.Command(command)
        dc = dc.bake(*cli_args)

        # Log command
        if _log:
            cmd = ' '.join([dc.__name__ ] + [ x.decode('utf-8') for x in dc._partial_baked_args])
            self.log.exec (cmd)

        # Execute command
        try:
            output = dc (**sh_opts)
        except sh.ErrorReturnCode as err:
            raise Exception(err)
            #self.log.critical (f"Command failed with message:\n{err.stderr.decode('utf-8')}")
            #sys.exit(1)

        return output




    def docker_assemble(self, output="docker-compose.run.yml"):
        "Generate docker-compose.run.yml"

        self.docker_generate_envfile()
        output_file = os.path.join(self.path, self.runtime['docker_compose_output'])

        args_docker_compose_list = []
        candidates = self.list_docker_compose_files_from_tags()
        self.log.trace("List of tags and files:")

        for tag_match in candidates:
            tag = tag_match['tag']
            tag_name = tag.name if tag else __name__

            for cand in tag_match['candidates']:
                args_docker_compose_list.extend(["--file", cand])

                self.log.trace(f" - {tag_name :>16}: {cand}")
            #args_docker_compose_list.extend(tag['candidates'])

        args_env_file = filter_existing_files(
            self.path,
            [".env",
            ])[0] or None

        # Exec:
        dc = sh.Command("docker-compose")
        cli_args = [
          #  "compose", 
            "--project-name", self.name,
            "--project-directory", self.path,
        ]
        if args_env_file:
            cli_args.extend(["--env-file", args_env_file]) 
        cli_args.extend(args_docker_compose_list)
        cli_args.extend({
            "config", 
          #  "--no-interpolate"
        })

        # Execute generation of docker-compose
        output = self._exec("docker-compose", cli_args, _out=None)

        # Write outfile
        stdout = output.stdout.decode("utf-8") 
        with open(output_file, 'w') as writer:
           writer.write(stdout)
        self.log.notice (f"Docker-compose file has been generated: {output_file}")


        ### WIPPPP: jsonnet support
        self.jsonnet_postprocess()



    def jsonnet_postprocess(self, compose_file="docker-compose.run.yml"):
        "Postprocess jsonnet tags and update docker-compose.run.yml"

        # OR: tags = self.tags
        tags = self.tags

        # Apply all jsonnet processing tag after tag
        docker_data = anyconfig.load(compose_file)
        for tag in tags:
            if tag.has_jsonnet_support():
                self.log.info (f"Processing jsonnet for tag: {tag.name}")
                docker_data = tag.process_jsonnet(docker_data)

        # Update docker-compose file:
        # TOFIX: Make output consistent, reparse -it with docker-compose config
        compose_file = os.path.join(self.path, compose_file)
        file_content = yaml.dump(docker_data)
        with open(compose_file, 'w') as writer:
            writer.write(file_content)
        log.debug (f"File updated via tag: {self.name}")
        return docker_data


    def docker_up(self, compose_file="docker-compose.run.yml"):
        "Start docker stack"
        
        cli_args = [
            "--project-name", self.project_name,
            "--project-directory", self.path,
            "--file", os.path.join(self.path, compose_file),
            "up",
            "--detach",
        ]
        self._exec("docker-compose", cli_args)

    def docker_down(self):
        "Start docker stack"
        
        cli_args = [
            "--project-name", self.project_name,
            "down",
            "--remove-orphans",
        ]
        self._exec("docker-compose", cli_args)

    def docker_ps(self):
        "Start docker stack"
        
        cli_args = [
            "--project-name", self.project_name,
            "ps",
            "--all",
        ]
        self._exec("docker-compose", cli_args)

    def docker_logs(self, follow=False):
        "Show stack logs"
        
        sh_options = {}
        cli_args = [
            "--project-name", self.project_name,
            "logs",
        ]
        if follow:
            cli_args.append("-f")
            sh_options["_fg"]=True
            
        self._exec("docker-compose", cli_args, **sh_options)




# =====================================================================
# Stack management
# =====================================================================

class StackManager(ClassClassifier):

    schema_def={
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Stack configuration",
        "type": "array",
        "items": Stack.schema_def,
    }

    def _init(self):

        assert isinstance(self.user_config, list), f"Stack def is not a list"
        store = []

        for stack_def in self.user_config:
            stack = Stack(self, name=None, user_config=stack_def)
            store.append(stack)

        self.store = store

    def get_stack_by_name(self, name):
        result = [x for x in self.store if x.name == name]
        return result[0] if len(result) > 0 else None

    def get_stacks_by_name(self, name):
        result = [x for x in self.store if x.name == name]
        return result

    def get_all_stacks(self):
        return self.store

    def get_all_stack_names(self):
        return [x.name for x in self.store ]

    def get_one_or_all(self, name):
        """
        If name is a string, return the mathing stack, or all stacks
        """

        if isinstance(name, str):
            match = self.get_stacks_by_name(name)
            if match:
                return match
            else:
                raise Exception(f"Not such stack: '{name}'")
        else:
            return self.store

    def dump_stacks(self):

        for k in self.store:
            self.log.info (pformat (k.__dict__))


