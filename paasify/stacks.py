

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
        "title": "Environment configuration",
        "description": "Environment configuration. Paasify leave two choices for the configuration, either use the native dict configuration or use the docker-compatible format",

        "oneOf": [
            {
                "title": "Env configuration (dict)",
                "examples": [{ 
                    'env': {
                    'MYSQL_ADMIN_USER': 'MyUser',
                    'MYSQL_ADMIN_DB': 'MyDB',
                    } 
                }]
                ,
                "type": "object",
                "patternProperties": {
                    '.*': {
                        "oneOf": [
                            {
                                "title": "Environment Key value",
                                "description": "Value must be a string",
                                
                                "oneOf": [
                                    {"type": "string"},
                                    {"type": "boolean"},
                                    {"type": "integer"},
                                ],
                            },
                            {
                                "title": "Ignored value",
                                "description": "If empty, value is ignored",
                                "type": "null"
                            },
                        ],
                    }
                },
            },
            {
                "title": "Env configuration (list)",
                "examples": [{ 
                    'env': [
                    'MYSQL_ADMIN_USER=MyUser',
                    'MYSQL_ADMIN_DB=MyDB',
                ]
                }],

                "type": "array",
                "items": {
                    "title": "Environment list",
                    "description": "Value must be a string, under the form of: KEY=VALUE",
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
    
    
    def _init(self):

        self.obj_prj = self.parent.obj_prj
        self.obj_stack = self.parent
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
        project_config = self.obj_prj.project.tags_config.get(self.name, {})
        user_config = self.user_config["local_config"] or {}

        # prepare ext_vars
        user_data = {}
        user_data.update(vendor_config)
        user_data.update(project_config)
        user_data.update(user_config)

        docker_env = self.parent.env_get()

        app_domain = docker_env.get("PAASIFY_STACK_DOMAIN", None)
        svc_stack = self.obj_stack.name

        app_default_fqdn = f"{svc_stack}.{app_domain}" if app_domain else svc_stack

        app_fqdn = docker_env.get("PAASIFY_STACK_FQDN", app_default_fqdn)

        svc_names = list(docker_data.get("services", {}).keys())
        main_svc = svc_names[0] if len(svc_names) > 0 else svc_stack

        paasify_config = {
            "PAASIFY_STACK_NS": self.obj_prj.runtime["namespace"],
            "PAASIFY_STACK_NAME": svc_stack,
            "PAASIFY_STACK_SVC": main_svc,
            "PAASIFY_STACK_SVCS": ','.join(svc_names),
            "PAASIFY_STACK_FQDN": app_fqdn,
            "PAASIFY_STACK_DOMAIN": app_domain,

            # COMPAT
            "APP_FQDN": app_fqdn,
            "APP_DOMAIN": app_fqdn, # TOFIX ?
            "APP_TOP_DOMAIN": app_domain,
        }

        local_env = {}
        local_env.update(paasify_config)
        local_env.update(docker_env)
        local_env.update(user_data)

        ext_vars = {
            "stack_data": {} , #self.obj_prj.runtime,
            "env_data": {} , #self.parent.env_get(),

            "user_data": local_env, # overrides possible from paasify.yml only
            "docker_data": docker_data, # Current state of the compose file
        }



        self.log.trace(f"Jsonnet script:  (script:{jsonnet_src_path})")
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

        # Generate jsonnet lookups
        lookup_config_jsonnet = [
            {
                # Look into the working dir stack
                "path": stack.path,
                "pattern": [
                    f"paasify.{tag}.jsonnet",
                    f"paasify/plugins/{tag}.jsonnet",
                ],
            },
            {
                # Look into the project dir
                "path": self.runtime['top_project_dir'],
                "pattern": [
                    f".paasify/plugins/{tag}.jsonnet",
                    #f"paasify/{tag}.jsonnet",
                ],
            },
            {
                # Look in app source directory
                "path": stack.src_path,
                "pattern": [
                    f".paasify/plugins/{tag}.jsonnet",
                ],
            },
            {
                # Look into local user dirs
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
            new_config = dict(path_config)
            new_config["pattern"] = [x.replace(f"{tag}.jsonnet", f"{tag}.vars.yml") for x in new_config["pattern"]]
            lookup_config_jsonnet_vars.append(new_config)
        

        r1 = lookup_candidates(lookup_config_jsonnet)
        r2 = lookup_candidates(lookup_config_jsonnet_vars)
        return r1, r2


    def lookup_docker_files(self):
        "Generate candidates for jsonnet parsing"

        stack = self.parent
        tag = self.name

        # Prepare main config
        lookup_config = [
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

        return lookup_candidates(lookup_config)




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

            # Extra parameters
            "docker_file": "docker-compose.run.yml",
            "env_file": ".env",
        }

    def _init(self):

        # Create links
        self.obj_prj = self.parent.obj_prj

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

        self.prj_dir = self.obj_prj.runtime['prj_dir']
        self.ns = self.obj_prj.runtime['namespace']
        self.project_name = f"{self.ns}_{self.name}"
        self.path = os.path.join(self.prj_dir, self.short_path)
        
        self.config = config

        # Fetch source configuration
        # Require the source object to be inited !
        self._init_source()

        self.tags = self.tags_get()

        

    def _init_source(self):
        "Resolve stack source and app"

        query = self.config['app']

        srcMgr = self.obj_prj.sources
        app_rel_path, app_name = srcMgr.resolve_ref_pattern(query)

        self.app_rel_path = app_rel_path
        self.app_name = app_name
        self.obj_source = None
        self.src_path = None

        if app_name:
            src = srcMgr.get_source(app_name)
            # TOFIX: Check if the target dir exists !
            if src:
                self.obj_source = src
                self.src_path = src.get_path()
            else:
                raise Exception (f"Can't find source for: {query}")

            app_path = os.path.join( src.path, app_rel_path)
        else:
            app_path = os.path.join( self.runtime["cwd"], app_rel_path)

        self.app_path = app_path
         
    def source_update(self):
        "Update source"

    # def source_ensure(self):
    #     "Ensure source is present and installed"
    #     src = self.obj_source

    #     if not src.is_installed():
    #         src.install()


    # def resolve_app(self, app_def):
    #     "Find the associated source DEPRECATED by fetch_source()"

    #     if not app_def:
    #         return None

    #     # Parse format
    #     if ':' in app_def:
    #         app_src = app_def.split(':')[0]
    #         app_target = app_def.split(':', 2)[1]

    #         source = self.obj_prj.sources.get_source(app_src)
    #         assert source, f"Could not find source: {app_src} for {stack_def}"
    #         app_path = os.path.join( source.path, app_target)
    #     else:
    #         app_src = None
    #         app_target = app_def
    #         app_path = os.path.join( self.runtime["cwd"], app_target)

    #     return app_path







    def _dump(self):

        self.log.notice ("Misc:")
        self.log.notice (f"Path: {self.path}")
        self.log.notice (pformat (self.config))

        self.log.notice ("Env:")
        self.log.notice (pformat (self.env_get()))

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












    
    # Tag management
    # ----------------------
    def tags_get(self):
        "Create and return a list of StackTags objects"

        # Preparse tag structure
        tags_names = self._tags_parse()
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
        tags = [ StackTag(self, name=tag["name"], user_config=tag) for tag in tags ]
        return tags


    def _tags_parse(self):
        "Return the list of tags after merge"

        # Merge global and local tags
        default_tags = {
            "tags": [],
            "tags_auto": ["user", self.obj_prj.project.namespace ],
            "tags_prefix": [],
            "tags_suffix": [],
        }
        global_tags = { k: v for k, v in self.obj_prj.project.items() if k.startswith("tags") and v}
        local_tags = { k: v for k, v in self.user_config.items() if k.startswith("tags") and v}

        default_tags.update(global_tags)
        default_tags.update(local_tags)

        tags = default_tags["tags_prefix"] + default_tags["tags_auto"] + default_tags["tags"] + default_tags["tags_suffix"]
        return tags



    # Environment related tasks (required by docker)
    # ----------------------

    def env_get(self) -> dict:
        "Return a dict of the environment variables"
        global_env = self.obj_prj.project.env
        local_env = self.config["env"]

        r0 = {}
        if self.app_path:
            app_env_file = filter_existing_files(self.app_path, [".env"])
            if len(app_env_file) > 0:
                r0 = anyconfig.load(app_env_file, ac_parser="shellvars")


        r1 = self._env_parse(global_env)
        r2 = self._env_inject()
        r3 = self._env_parse(local_env)


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


    def _env_inject(self) -> dict:
        "Inject environment vars and return a dict of it"
        ns = self.runtime["namespace"]

        result = {
            "APP_NAME": self.name,
            "APP_NAMESPACE": ns,
            "APP_PROJECT_DIR": self.runtime["prj_dir"],
            "APP_COLLECTION_DIR": self.runtime["collections_dir"],

            # front_network
            #"APP_TRAEFIK_NETWORK": f"{ns}_traefik",
            "APP_NETWORK": f"{ns}_{self.name}",

            # Expose Tag
            #"APP_EXPOSE_IP": "127.0.0.1",

            "APP_PROJECT_DIR": self.runtime["prj_dir"],
            "APP_PROJECT_DIR": self.runtime["prj_dir"],
            "APP_PROJECT_DIR": self.runtime["prj_dir"],

        }
        return result

    def _env_parse(self, payload) -> dict:
        "Accept any user configuration and return a dict"

        if isinstance(payload, list):
            result = {}
            for stmt_str in payload:
                stmt = stmt_str.split("=", 2)
                if len(stmt) < 2:
                    raise Exception(f"Could not parse value: {stmt_str}, missing '='")
                key = stmt[0]
                value = '='.join(stmt[1:])
                result[key] = value
            return result
        elif isinstance(payload, dict):
            return payload
        else:
            return {}





    # Command Execution framework
    # ==================================
    def _exec(self, command, cli_args=None, _log=True, **kwargs):
        "Execute any command"

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
        cmd = sh.Command(command)
        cmd = cmd.bake(*cli_args)

        # Log command
        if _log:
            cmd_line = [cmd.__name__ ] + [ x.decode('utf-8') for x in cmd._partial_baked_args]
            cmd_line = ' '.join(cmd_line)
            self.log.exec (cmd_line)

        # Execute command via sh
        try:
            output = cmd(**sh_opts)
        except sh.ErrorReturnCode as err:
            raise Exception(err)
            #self.log.critical (f"Command failed with message:\n{err.stderr.decode('utf-8')}")
            #sys.exit(1)

        return output






    # Compose Commands
    # ==================================

    def docker_compose_get_files(self, tags=None):
        "List all tag candidates"
        
        result = [self._docker_compose_base_file()]
        result.extend(self._docker_compose_tags_file(tags=tags))

        return result


    def _docker_compose_base_file(self):
        "Return first docker-compose candidates"

        # Lookup docker-compose file locations
        lookup_config = [
            {
                "path": self.path,
                "pattern": [
                    "docker-compose.yml",
                    "docker-compose.yaml",
                ],
            },
            {
                "path": self.app_path,
                "pattern": [
                    "docker-compose.yml",
                    "docker-compose.yaml",
                ],
            },
        ]
        for x in lookup_config:
            x["tag"] = None
        result = lookup_candidates(lookup_config)

        # Return best docker-compose file candidate
        result = [ x for x in result if len(x["matches"]) > 0 ]
        if len(result) < 1:
            raise Exception (f"Can't find any valid docker-compose.yml file in this stack")
            
        return result[0]


    def _docker_compose_tags_file(self, tags=None):
        "Return tagged docker-compose candidates"

        results = []
        for tag in tags:

            # Retrieve docker-compose files
            result = tag.lookup_docker_files()

            # Return only metched files
            result = [ x for x in result if len(x["matches"]) > 0 ]
            if len(result) > 0:
                for x in result:
                    x["tag"] = tag
                results.extend(result)

        return results


    def _docker_compose_write_envfile(self, env=None):
        "Generate .env file focker docker-compose"

        env = env or self.env_get()
        dst_file = os.path.join(self.path, '.env')

        file_content = []
        for var, val in env.items():
            file_content.append(f'{var}="{val}"')

        self.log.trace(f"Preparing .env file: {dst_file}")
        self.log.trace(pformat(file_content))

        file_content = '\n'.join(file_content) + '\n'
        file_folder = os.path.dirname(dst_file)
        if not os.path.exists(file_folder):
            print ("VALUE  ", file_folder)
            os.makedirs(file_folder)

        with open(dst_file, 'w') as writer:
            writer.write(file_content)

        self.log.info (f"Environment file created/updated: {dst_file}")







    # Docker High Level Commands
    # ==================================

    def docker_assemble(self, output=None):
        "Generate docker-compose.run.yml"

        # Split this function in:
        # - docker-assemble
        # - docker-jsonnet

        tags = self.tags
        output = output or self.runtime['docker_compose_output']
        output_file = os.path.join(self.path, output)

        # Build command line argument
        self.log.trace("List of tags and files:")
        candidates = self.docker_compose_get_files(tags=tags)
        args_docker_compose_list = []
        for cand in candidates:
            # Keep only first match of all candidates, we overrides here !
            docker_file = cand["matches"][0]
            args_docker_compose_list.extend(["--file", docker_file])

            tag_name = getattr(cand["tag"], "name", "DEFAULT")
            self.log.trace(f" - {tag_name :>16}: {docker_file}")

        # Manage environment file
        # TOFIX: Actually this file is almost useful only during build time
        # Solution: Remove this file once generated ...
        self._docker_compose_write_envfile()
        args_env_file = filter_existing_files(
            self.path,
            [".env",
            ])[0] or None

        # Prepare command
        cli_args = [
          #  "compose", 
            "--project-name", self.name,
            "--project-directory", self.path,
        ]
        if args_env_file:
            cli_args.extend(["--env-file", args_env_file]) 
        cli_args.extend(args_docker_compose_list)
        cli_args.extend([
            "convert", 
            # "--no-interpolate",
            # "--no-normalize",
        ])

        # Execute generation of docker-compose
        output = self._exec("docker-compose", cli_args, _out=None)

        # Write outfile
        stdout = output.stdout.decode("utf-8") 
        with open(output_file, 'w') as writer:
           writer.write(stdout)
        self.log.notice (f"Docker-compose file has been generated: {output_file}")


        # Loop over jsonnet processing tag after tag
        docker_data = anyconfig.load(output_file)
        for tag in tags:
            if tag.has_jsonnet_support():
                self.log.info (f"Processing jsonnet tag: {tag.name}")
                docker_data = tag.process_jsonnet(docker_data)


        # Update docker-compose file
        output_file = os.path.join(self.path, output_file)
        file_content = yaml.dump(docker_data)
        with open(output_file, 'w') as writer:
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
            "--format", "json",
        ]
        result = self._exec("docker-compose", cli_args, _out=None)

        # Report output from json
        stdout = result.stdout.decode("utf-8") 
        payload = json.loads(stdout)
        for svc in payload:

            # Get and filter interesting ports
            published = svc["Publishers"]
            published = [ x for x in published if x.get('PublishedPort') > 0 ]

            # Reduce duplicates
            for x in published:
                if x.get('URL') == '0.0.0.0':
                    x['URL']='::'

            # Format port strings
            exposed = []
            for port in published:
                src_ip = port["URL"]
                src_port = port["PublishedPort"]
                dst_port = port["TargetPort"]
                prot = port["Protocol"]

                r = f"{src_ip}:{src_port}->{dst_port}/{prot}"
                exposed.append(r)

            # Remove duplicates ports and show
            exposed = list(set(exposed))
            print (f"  {svc['Project'] :<32} {svc['Name'] :<40} {svc['Service'] :<16} {svc['State'] :<10} {', '.join(exposed)}")
    

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

        self.obj_prj = self.parent

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


