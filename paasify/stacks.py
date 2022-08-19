

import os
import sys
import re
import logging
import json
import glob

import yaml
import anyconfig
import sh
import _jsonnet

from pprint import pprint, pformat

from paasify.common import extract_shell_vars, lookup_candidates, write_file, cast_docker_compose
from paasify.common import merge_env_vars, filter_existing_files, read_file
import paasify.errors as error
from paasify.class_model import ClassClassifier
from paasify.var_parser import BashVarParser


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


    # Helpers
    # =============================

    def _exec_jsonnet(self, file, ext_vars=None):
        "Execute jsonnet command"

        ext_vars = ext_vars or {}

        # Flatten to json extvars
        ext_vars = {k: json.dumps(v) for k, v in ext_vars.items() }

        # Process file
        self.log.exec(f"Parse {ext_vars['action']} jsonnet file: {file}")
        #self.log.trace(pformat(ext_vars))
        result = _jsonnet.evaluate_file(
            file,
            ext_vars=ext_vars,
        )

        # Return json data
        return json.loads(result)


    # Environment management
    # =============================

    def tag_env_get_local(self):
        "Retrieve user configuration"

        return self.user_config["local_config"] or {}


    def tag_env_get(self, env=None):
        """Build tag configuration from user config and paasify
        
        If env is empty, then it fetch global + stack + tag config
        """

        # Look if any candidates or return None
        cand = self.get_candidates("cand_jsonnet_script")
        if len(cand) < 1:
            return None
        cand = cand[0]

        # Load env
        env = env or {}
        assert isinstance(env, dict), f"Error, env is not a dict, got: {type(env)}"

        # Process tag
        ext_vars = {
            "action": "vars_docker",
            'user_data': env,
            'docker_data': {},
        }

        # PROBE:
        # pprint (ext_vars)
        
        out = self._exec_jsonnet(cand, ext_vars=ext_vars)
        return out
            

    # Docker file lookup management
    # =============================

    def process_transform(self, docker_data, env=None):
        "Transform docker-compose with jsonnet filter"


        # Look if any candidates or return None
        cand = self.get_candidates("cand_jsonnet_script")
        if len(cand) < 1:
            return None     
        cand = cand[0]

        # Load env
        if not env:
            self.log.warning ("BUG HERE")
            user_data = self.tag_env_get(env).get("diff")
        else:
            user_data = env

        # Process tag
        ext_vars = {
            "action": "docker_transform",
            'user_data': user_data,
            'docker_data': docker_data,
        }

        # Return transformed docker_data
        try:
            return self._exec_jsonnet(cand, ext_vars=ext_vars)
        except Exception as err:
            print (20 * '!') 
            pprint (ext_vars)
            print (err)
            print (20 * '!')
            sys.exit(1)


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
        config.update(self.user_config)

        # Sanity check
        fail_on_app=True
        app_name = config["app"] or config["name"] or config["path"] or None
        if not app_name:
            raise StackMissingOrigin(f"Missing 'app' or 'path' or 'name' option for stack: {self.default_user_config}")
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
         

    def _dump(self):
        self.log.notice (f"Path: {self.path}")

        self.log.notice ("Stack config:")
        self.log.notice (pformat (self.config))

        self.log.notice ("Env User:")
        self.log.notice (pformat (self.env_get_user()))

        self.log.notice ("Env:")
        self.log.notice (pformat (self.env_get()))

        self.log.notice ("Tags:")
        tags = self.tags

        self.log.notice ("Docker-compose config:")
        stores =  ["cand_composefile"]
        for tag in tags:
            
            for sub_item in stores:
                candidates = tag.get_candidates(sub_item)
                if len(candidates) > 0:
                    self.log.notice (f"  - Name: {tag.name}")
                    self.log.notice (f"    {sub_item}: ({len(candidates)} candidates)")
                    for cand in candidates:
                        self.log.notice(f"      - {cand}")


        self.log.notice ("Processor config:")
        stores =  ["cand_jsonnet_script", "cand_jsonnet_vars"]
        for tag in tags:

            # Show all file candidates
            show = False
            for sub_item in stores:
                candidates = tag.get_candidates(sub_item)
                if len(candidates) > 0:
                    show = True

            if show:
                self.log.notice (f"  - Name: {tag.name}")

                # Show tag configuration
                local_config = getattr(tag, 'local_config', None)
                if local_config:
                    self.log.notice (f"    Config:")
                    for k, v in local_config.items():
                        self.log.notice(f"      {k}: {v}")

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

            # Create tag config
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

    def env_get_user(self):
        '''Return env config from user config'''

        global_env = self.obj_prj.project.env
        local_env = self.config["env"]

        r0 = {}
        # We just ignore .env files .... forevever
        # if self.app_path:
        #     app_env_file = filter_existing_files(self.app_path, [".env"])
        #     if len(app_env_file) > 0:
        #         r0 = anyconfig.load(app_env_file, ac_parser="shellvars")

        r1 = self._env_parse(global_env)
        r3 = self._env_parse(local_env)
        r2 = self._env_inject({**r1, **r3})

        result = {}
        result.update(r0)   # .env file
        result.update(r1)   # Global vars (paasify.yml/project/vars)
        result.update(r2)   # Generated stack vars (internal paasify vars)
        result.update(r3)   # Stack vars (paasify.yml/stack/vars)
        
        return result


    # TO BE RENAMMED STAGE_01
    def env_get(self, remove_overrides=False ) -> dict: 
        "Return a dict of the environment variables, with tags"

        # if hasattr(self, '_env'):
        #     print ("HIT CACHE: env_get")
        #     return getattr(self, '_env')


        # DYNAMIC VARS # TO BE REPLACED BY JSONNETS
        #################

        # Then load variables: from x-paasify-config: config (packaged)
            # Look into: app-collection/docker-compose.yaml AND app/docker-compose.yaml
                # Look into x-paasify:
                # Examples:
                    # app_service_ident: traefik
                    # app_network:
                    # app_front_network: traefik
                    # app_back_network: EMPTY  # Do not create external network if empty
                    # app_image: traefik:latest

        # Then load: Initial vars (ext_vars) (OVERRIDES)
        # then load user overrides: from paasify.yml (env/vars from NS then STACK)
        # Then loop over each var plugins

        self.log.trace (f"Init paasify config vars:")
        result = self.env_get_user()
        override_keys = []
        self.log.trace (pformat(result))

        self.log.trace (f"Init plugins vars: {[tag.name for tag in self.tags]}")
        for tag in self.tags:
            
            if not tag.has_jsonnet_support:
                continue

            payload = tag.tag_env_get(env=result)
            if not isinstance(payload, dict):
                self.log.info (f"Plugin did not returned env data: {tag.name}, {payload}")
                continue

            env_data = payload["diff"]
            
            # PROBE: Environment data output
            # print ("INPUT ENV")
            # pprint (result)
            # print ("OUTPUT ENV")
            # pprint (payload)
            # #pprint(env_data)

            self.log.info (f"Plugin returned env data: {tag.name} ({len(env_data)} items), _items will be merged!")
            self.log.trace (pformat(env_data))

            env_data, keys = merge_env_vars(env_data)
            override_keys.append(keys)

            result.update(env_data)
                

        if remove_overrides:
            # This remove overrided values
            self.log.trace (f"Transform dynamic vars into static vars")
            for key in override_keys:
                result.pop(key)

        # self.log.trace (f"Final docker-compose vars:")
        # self.log.trace (pformat(result))

        return result


    def _env_inject(self, current=None) -> dict:
        "Inject environment vars and return a dict of it"

        current = current or {}
        current_service = current.get('paasify_stack_service', self.name)
        current_services = current.get('paasify_stack_services', current_service)
        
        tag_names = [tag.name for tag in self.tags]
        ext_vars = {

            "paasify_ns": self.runtime["namespace"],
            "paasify_ns_dir": self.runtime["prj_dir"],

            "paasify_stack": self.name,
            "paasify_stack_dir": self.path,

            "paasify_stack_ident": self.runtime["namespace"] + '_' + self.name,
            "paasify_cwd": os.getcwd(),
            "paasify_collections_dir": self.runtime["collections_dir"],

            "paasify_sep": "_",
            "paasify_sep_dir": os.path.sep,

            # These variables can be overrided !
            'paasify_stack_service': current_service,
            'paasify_stack_services': current_services,
            'paasify_stack_tags': ','.join(tag_names),

        }
        return ext_vars


    # TOFIX: Should be static method !!!
    def _env_parse(self, payload) -> dict:
        "Accept any user configuration and return a dict"

        if isinstance(payload, list):
            result = {}
            for stmt_obj in payload:
                stmt = []

                # Manage strings format
                if isinstance(stmt_obj, str):
                    stmt = stmt_obj.split("=", 1)
                    if len(stmt) < 2:
                        raise Exception(f"Could not parse value: {stmt_obj}, missing '='")
                
                # Manage dict format
                elif isinstance(stmt_obj, dict):
                    for k, v in stmt_obj.items():
                        stmt = [k, v]
                        break

                    assert len(stmt) == 2, f"Error while parsing: {stmt_obj}"

                key = stmt[0]
                value = stmt[1]
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

        def bin2utf8(obj):
            obj.txtout = obj.stdout.decode("utf-8").rstrip('\n')
            obj.txterr = obj.stderr.decode("utf-8").rstrip('\n')
            return obj  


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
            bin2utf8(output)
            return output

        except sh.ErrorReturnCode as err:
            bin2utf8(err)
            self.log.error (f"Command returned code {err.exit_code}: {err.full_cmd}")
            if err.stdout:
                self.log.notice ( err.txtout)

            raise error.ShellCommandFailed(err.txterr)



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


    def _docker_compose_write_envfile2(self, env, allowed_vars=None):
        "Generate .env file focker docker-compose"

        env = env or {}
        allowed_vars = allowed_vars or list(env.keys())
        dst_file = os.path.join(self.path, '.env')

        file_content = []
        for var, val in env.items():
            if var in allowed_vars:
                file_content.append(f'{var}="{val}"')

        # self.log.trace(f"Preparing .env file: {dst_file}")
        # self.log.trace(pformat(file_content))

        file_content = '\n'.join(file_content) + '\n'
        write_file(dst_file, file_content)

        self.log.info (f"Environment file created/updated: {dst_file}")


    # Docker High Level Commands
    # ==================================

    def docker_assemble(self, output=None):
        "Generate docker-compose.run.yml"

        ## Part 1

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
        used_vars = []

        # Implementation switch:
        # v1: Use basic regex, broken by design
        # v2: Use lark parser, broken
        # v3: Use regex, work but limited
        MODE='v3'
        ENABLE_ENV_WRITE=False
        rgx = re.compile('(?P<prefix>\$?\$)[\{]?(?P<name>[a-zA-Z_][a-zA-Z_0-9]*)(?P<opts>(:?[-?])?)')
        for cand in candidates:
            # Keep only first match of all candidates, we overrides here !
            docker_file = cand["matches"][0]

            if MODE == 'v1':
                # Extract file's used vars
                file_vars = extract_shell_vars(docker_file)
                used_vars.extend(file_vars)

            elif MODE == 'v2':
                self.log.info(f"Parsing file: {docker_file}")
                payload = read_file(docker_file)
                data_var = BashVarParser(payload=payload, env=None)

                data_var.render(mode = 'raw')
                for var in data_var.var_list:
                    used_vars.append(var)

            else:
                
                payload = read_file(docker_file)
                for x in rgx.finditer(payload):
                    match = x.groupdict()
                    if match['prefix'] == '$':
                        used_vars.append(match['name'])


            # Build CLI file list
            args_docker_compose_list.extend(["--file", docker_file])

            # Log report
            tag_name = getattr(cand["tag"], "name", "DEFAULT")
            self.log.trace(f" - {tag_name :>16}: {docker_file}")


        # Manage environment file
        stack_env = self.env_get()
        #pprint (stack_env)

        if MODE == 'v1':
            allowed_vars = list(set([x['name'] for x in used_vars]))
            self._docker_compose_write_envfile2(stack_env, allowed_vars=allowed_vars)
        else:
            if MODE == 'v2':
                allowed_vars = list(set([x.name for x in used_vars]))
            else:
                allowed_vars = list(set(used_vars))

            if ENABLE_ENV_WRITE:
                self._docker_compose_write_envfile2(stack_env, allowed_vars=allowed_vars)

                args_env_file = filter_existing_files(
                    self.path,
                    [".env",
                    ])[0] or None


        # Prepare command
        cli_args = [
          #  "compose", 
            "--project-name", f"{self.ns}_{self.name}",
            "--project-directory", self.path,
        ]
        if ENABLE_ENV_WRITE:
            if args_env_file:
                cli_args.extend(["--env-file", args_env_file]) 
        cli_args.extend(args_docker_compose_list)
        cli_args.extend([
            "config", 
            # "--no-interpolate",
            # "--no-normalize",
        ])

        # Stack env
        self.log.debug ("Available vars for docker-compose files:")
        self.log.debug (pformat (stack_env))

        # Execute generation of docker-compose
        if ENABLE_ENV_WRITE:
            output = self._exec("docker-compose", cli_args, _out=None)
        else:
            env_string = { k: cast_docker_compose(v) for k, v in stack_env.items() if v is not None }
            output = self._exec("docker-compose", cli_args, _out=None, _env=env_string) 

        if output.txterr:
            self.log.warn(output.txterr)

        # Write outfile
        #stdout = output.stdout.decode("utf-8") 
        stdout = output.txtout
        with open(output_file, 'w') as writer:
           writer.write(stdout)
        self.log.notice (f"Docker-compose file has been generated: {output_file}")


        ## Part 2

        # Create extra paasify vars
        docker_data = anyconfig.load(output_file)

        # Create global environment
        svc_names = list(docker_data.get("services", {}).keys())
        main_svc = svc_names[0] if len(svc_names) > 0 else svc_stack
        tag_names = [tag.name for tag in tags]
        tag_env = {
            'paasify_stack_service': main_svc,
            'paasify_stack_services': ','.join(svc_names),
            'paasify_stack_tags': ','.join(tag_names),
        }
        docker_env = {}
        docker_env.update(tag_env)
        docker_env.update(stack_env)
        
        
        self.log.debug ("Available extra vars for tranform filters:")
        self.log.debug (json.dumps(tag_env, indent=2, sort_keys=True))

        docker_rewrite = dict(docker_data)
        # Loop over jsonnet processing tag after tag
        for tag in tags:
            if tag.has_jsonnet_support():

                local_conf = tag.tag_env_get_local()

                tag_env = {}
                tag_env.update(docker_env)
                tag_env.update(local_conf)

                self.log.info (f"Processing jsonnet tag '{tag.name}' with local data: {pformat(local_conf)}")
                change_raw = tag.process_transform(docker_rewrite, env=tag_env)

                # TOFIX
                try:
                    docker_diff = change_raw['diff']
                    docker_merged = change_raw['merged']
                    
                except KeyError:
                    docker_diff = "NOT SUPPORTED"
                    docker_merged = change_raw
                    self.log.warning(f"Old Plugin API for plugin: {tag.name}")


                if isinstance(docker_diff, dict):
                    self.log.debug (json.dumps(docker_diff, indent=2, sort_keys=True))
                else:
                    raise Exception(f"TOFIX: Broken plugin {tag.name}:", docker_diff)

                docker_rewrite = docker_merged

        self.log.trace("Final docker file:")
        self.log.trace(json.dumps(docker_rewrite, indent=2, sort_keys=True))

        # Update docker-compose file
        output_file = os.path.join(self.path, output_file)
        file_content = yaml.dump(docker_rewrite)
        with open(output_file, 'w') as writer:
            writer.write(file_content)
        log.debug (f"File updated: {output_file}")
        return docker_rewrite


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
        #stdout = result.stdout.decode("utf-8") 
        stdout = result.stdout
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
        # TOFIX: Should we accept paths as well ?
        result = [x for x in self.store if x.name == name]
        return result[0] if len(result) > 0 else None

    def get_stacks_by_name(self, name):
        result = [x for x in self.store if x.name == name or name.startswith(x.short_path)]
        return result

    def get_all_stacks(self):
        return self.store

    def get_all_stack_names(self):
        return [x.name for x in self.store ]

    def get_one_or_all(self, name):
        """
        If name is a string, return the mathing stack (including from paths), or all stacks
        """

        if isinstance(name, str):
            match = self.get_stacks_by_name(name)
            if match:
                return match
            else:
                available_stacks = ', '.join([x.name for x in self.store])
                raise error.PaasifyError(
                    f"Impossible to find a stack called '{name}' under project: {self.runtime['top_project_dir']}",
                    advice = f"Please choose one of: {available_stacks}"
                )
        else:
            return self.store

    def dump_stacks(self):

        for k in self.store:
            self.log.info (pformat (k.__dict__))


