
# from pydantic import BaseModel
import os
import sys
import re
from dataclasses import dataclass, astuple, asdict
from pathlib import Path
from copy import copy

from pprint import pprint, pformat

# @dataclasses
# class ProjectData():
#     cwd: str
#     project_dir: str
#     signup_ts: Optional[datetime] = None
#     friends: List[int] = []
import anyconfig
import sh

#from paasify.common import get_logger, list_parent_dirs, find_file_up
from paasify.common import *
# print ("yupp")
# log, log_level = get_logger(logger_name=__name__)
# print ("yupp")


import logging
log = logging.getLogger(__name__)



# =====================================================================
# Class helpers
# =====================================================================

class ClassClassifier():

    default_user_config = {}

    # Objects can have names
    name = "UNNAMMED"

    # Define initial user_configuration
    user_config = {}

    # Define live shared runtime data
    runtime = {}

    # Define live object config (can map as attributes)
    config = {}

    # Define live store, for containers
    store = None



    def __init__(self, parent, user_config=None, name=None, *args, **kwargs):

        # Init object classifier
        if parent:
            self.parent = parent
            self.root = parent.root
        else:
            self.parent = self
            self.root = self
        self.name = name or self.__class__.__name__
        self.log = logging.getLogger(f"paasify.{self.__class__.__name__}.{self.name}")

        #log, _ = get_logger(logger_name=f"paasify.{self.__class__.__name__}.{self.name}")


        self.runtime = getattr(parent, 'runtime', {})
        self.user_config = user_config
        self._init_attr_from_dict(self.default_user_config)

        # Init objects
        self._init(*args, **kwargs)


    def __repr__(self):
        return f"Instance {id(self)}: {self.__class__.__name__}:{self.name}"

    def _init_attr_from_dict(self, conf):
        "Init object attribute from dict"
        keys = []

        for k, v in conf.items():
            setattr(self, k, v)
            keys.append(k)

        self.keys = keys


    def get_root_parent(self):
        # print (f"Getting parent of ... {self}")

        if not hasattr(self, 'parent'):
            raise Exception(f"Bug, missing parent attribute for {self}!")
        elif self.parent == self:
            return self

        parent = self.parent
        if hasattr(parent, 'get_root_parent'):
            return parent.get_root_parent()
        else:
            return parent

    def dump(self):
        self.log.info (f"\nDump of object: {self.name} ({self.__class__}, {id(self)})")
        self.log.info ("="*20)


        
        #print ("Shared Runtime:")
        #pprint (self.runtime)

        #print ("-"*20)
        self.log.info ("User config:")
        self.log.info (pformat (self.user_config))
        self.log.info ("Instance Store:")
        self.log.info (pformat (self.store))
        self.log.info ("Instance Config:")
        self.log.info (pformat (self.config))



        cls_dump = getattr(self, "_dump", None)
        if callable(cls_dump):
            self.log.info ("-"*20)
            cls_dump()

        self.log.info ("="*20)


# =====================================================================
# Source management
# =====================================================================

class SourcesManager(ClassClassifier):

    def _init(self):

        assert isinstance(self.user_config, dict), f"Source def is not a dict"

        store= []

        for source_name, source_def in self.user_config.items():
            source = Source(self, user_config=source_def, name=source_name)
            store.append(source)

        self.store = store

    def list_all_names(self):
        r1 = [src.name for src in self.store ]
        r2 = [src.alias for src in self.store ]
        return r1 + r2


    def get_source(self, src_name):

        result = [src for src in self.store if src_name == src.name ] or [src for src in self.store if src_name == src.alias ]
        return result[0] if len(result) > 0 else None


    def resolve_ref_pattern(self, src_pat):
        "Return a resource from its name or alias"

        for src_name_def in self.root.sources.list_all_names():

            if src_name_def in src_pat:
                split_len = len(src_name_def)
                source_name = src_pat[:split_len]
                source_path = src_pat[split_len:]
                return source_name, source_path
                break



class Source(ClassClassifier):
    """ A Source instance
    """

    def _init(self):

        config = {
            "name": self.name,
            "url": None,
            "alias": None,
        }
        config.update(self.user_config)

        self.config = config
        self._init_attr_from_dict(config)
        self.path = self.get_path()
        

    def get_path(self):
        return os.path.join(self.runtime['collections_dir'], self.name)





# =====================================================================
# Stack management
# =====================================================================

class StackManager(ClassClassifier):

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



class Stack(ClassClassifier):
    """ A stack instance
    """

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
        config["name"] = re.sub(f'[^0-9a-zA-Z{os.sep}]+', '_', config["name"])


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
        self.tags = self.get_tags()
        
    def _dump(self):
        self.log.info ("Misc:")
        self.log.info (f"Path: {self.path}")
        self.log.info ("Tags:")
        self.log.info (pformat (self.get_tags()))
        self.log.info ("Env:")
        self.log.info (pformat (self.parse_env()))

        

    
    # Misc
    # ----------------------

    def get_tags(self):
        "Return stack tags"

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

        # Remove exclusions
        exclude = [ tag[1:] for tag in tags if tag.startswith('-') or tag.startswith('~') or tag.startswith('!') ]
        tags = [ StackTag(self, name=tag) for tag in tags if tag not in exclude ]
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
# StackTags management
# =====================================================================

class StackTag(ClassClassifier):
    
    
    def _init(self, lookup_mode='public'):

        self.lookup_mode = lookup_mode


    # Docker file lookup management
    # =============================

    def lookup_docker_compose_files(self):
        "This method return the list of files to add to docker-compose build"
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

    APP_SCHEMA="""

    """

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
        # (rc, err) = anyconfig.validate(project_config, self.APP_SCHEMA)

        prj_namespace = project_config['project'].get('namespace', None) or os.path.basename(project_dir)

        # Generate new config
        new_config = {
            'cwd': cwd,
            'level': project_level,
            'config_path': project_config_path,
            'project_dir': project_dir,
            #'collections_dir': f"{Path.home()}/.config/paasify/collections",
            'collections_dir': os.path.join(project_dir, '.collections'),
            'plugins_dir': f"{Path.home()}/.config/paasify/plugins",

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

        print ("Hello")

        stacks = self.stacks.get_all_stacks()

        self.log.notice(f"List of stacks:")
        for stack in stacks:
            self.log.notice(f"- {stack.name}")


