"""
Paasify Stack management

This library provides two classes:

* PaasifyStackManager: Manage a list of stacks
* PaasifyStack: A stack instance
"""

# pylint: disable=logging-fstring-interpolation


import os

import json
from pprint import pprint


import _jsonnet
import anyconfig


from cafram.nodes import NodeList, NodeMap
from cafram.utils import (
    to_domain,
    to_yaml,
    first,
    flatten,
    duplicates,
    write_file,
    to_json,
    # to_dict,
    # from_yaml,
    # serialize,
    # json_validate,
)

from paasify.common import lookup_candidates  # serialize, , json_validate, duplicates
from paasify.framework import PaasifyObj, PaasifyConfigVars  # , PaasifySimpleDict
from paasify.engines import bin2utf8
from paasify.stack_components import PaasifyStackTagManager, PaasifyStackApp
import paasify.errors as error


# Try to load json schema if present
ENABLE_JSON_SCHEMA = False
try:
    from json_schema_for_humans.generate import (
        generate_from_filename,
        generate_from_schema,
    )
    from json_schema_for_humans.generation_configuration import GenerationConfiguration

    ENABLE_JSON_SCHEMA = True
except ImportError:
    ENABLE_JSON_SCHEMA = False


class PaasifyStack(NodeMap, PaasifyObj):
    "Paasify Stack Instance"

    conf_ident = "{self.namespace}/{self.stack_name}"

    conf_default = {
        "path": None,
        "name": None,
        "app": None,
        "service": None,
        "network": None,
        "volume": None,
        "tags": [],
        "tags_suffix": [],
        "tags_prefix": [],
        "vars": [],
    }

    conf_children = [
        {
            "key": "app",
            "cls": PaasifyStackApp,
            "action": "unset",
            # "hook": "init_stack",
        },
        {
            "key": "vars",
            "cls": PaasifyConfigVars,
        },
    ]

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
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

    # Other objects
    tag_manager = None
    engine = None
    prj = None

    # TODO: State vars
    docker_candidates = None

    # TODO: Fix those vars
    stack_dir = None
    prj_dir = None
    # name = None
    # path = None
    stack_name = None

    namespace = None

    # CaFram functions
    # ---------------------

    def node_hook_transform(self, payload):

        # Internal attributes
        self.prj = self.get_parent().get_parent()
        assert (
            self.prj.__class__.__name__ == "PaasifyProject"
        ), f"Expected PaasifyProject, got: {self.prj}"

        # Ensure payload is a dict
        if isinstance(payload, str):
            if ":" in payload:
                payload = {
                    "name": payload.split(":")[1],
                    "app": payload,
                }
            else:
                payload = {
                    "name": payload,
                    "path": payload,
                }

        return payload

    def node_hook_children(self):
        "Self init object after loading of app"

        # Config update
        self.stack_name = self.get_name()
        self.name = self.stack_name  # Legacy code

        self.path = self.get_path()  # legacy code
        assert self.stack_name, f"Bug here, should not be empty, got: {self.stack_name}"

        self.prj_dir = self.prj.runtime.root_path
        self.stack_dir = os.path.join(self.prj.runtime.root_path, self.stack_name)
        self.namespace = self.prj.config.namespace or os.path.basename(self.stack_name)

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
        tag_list = (
            self.tags_prefix
            or self.prj.config.tags_prefix + self.tags
            or self.prj.config.tags + self.tags_suffix
            or self.prj.config.tags_suffix
        )
        self.tag_manager = PaasifyStackTagManager(
            parent=self, ident="StackTagMgr", payload=tag_list
        )

    # Local functions
    # ---------------------

    def get_path(self):
        "Return stack relative path"

        result = self.path or self.name
        if self.app:
            result = result or self.app.app_name

        if not result:
            pprint(self.__dict__)
            print(self.path, self.name)
        assert result, f"Error while getting path: {result}"
        return result

    def get_name(self):
        "Return stack name"

        result = self.name or self.get_path()
        if self.app:
            result = result or self.app.app_name

        return result.replace(os.path.sep, "_")

    # Local functions
    # ---------------------

    def resolve_stack_files(self):
        """Return all docker-files candidates: local, app and tags

        Modify object and set:
            Name: self.docker_candidates
            Content: A list of docker candidates

        Return nothing
        """

        stack_dir = self.stack_dir
        app = self.app

        # Search in:
        # <local>/docker-compose.yml
        # <app>/docker-compose.yml
        # <local>/docker-compose.<tags>.yml
        # <app>/docker-compose.<tags>.yml

        # 1. Get local docker compose
        lookup = [
            {
                "path": stack_dir,
                "pattern": ["docker-compose.yml", "docker-compose.yml"],
            }
        ]
        local_cand = lookup_candidates(lookup)

        # 2. Get app cand as fallback
        app_cand = []
        if app:
            local_cand = app.lookup_docker_files_app()

        # 3. Flatten result to matching candidates
        results = []
        results.extend(local_cand)
        results.extend(app_cand)

        # Filter result
        if len(results) < 1:
            msg = f"Can't find `docker-compose.yml` file neither in stack or app in: {stack_dir}"
            raise error.StackMissingDockerComposeFile(msg)

        # Return all results
        self.docker_candidates = results

    def get_tag_plan(self):
        """
        Resolve all files associated to tags

        Return the list of tags with files
        """

        if not self.docker_candidates:
            self.resolve_stack_files()

        # 0. Init
        # Objects:
        app = self.app or None
        # Vars:
        stack_dir = self.stack_dir
        project_jsonnet_dir = self.prj.runtime.project_jsonnet_dir

        # 1. Generate default tag (docker compose files only)
        tag_base = {
            "tag": None,
            "jsonnet_file": None,
            "docker_file": first(self.docker_candidates),
        }

        # 2. Forward to StackTagManager: Generate directory lookup for tags
        dirs = [
            stack_dir,
            project_jsonnet_dir,
        ]
        if app:
            dirs.append(app.app_dir)
            dirs.append(app.tags_dir)
        tag_list = self.tag_manager.resolve_tags_files(dirs)

        # 3. Return result list
        results = []
        results.append(tag_base)
        results.extend(tag_list)
        return results

    def gen_conveniant_vars(self, docker_file):
        "Generate default available variables"

        # Extract stack config
        dfile = anyconfig.load(docker_file, ac_ordered=True, ac_parser="yaml")
        default_service = self.service or first(dfile.get("services", ["default"]))
        default_network = self.network or first(dfile.get("networks", ["default"]))

        # default_volume = self.volume or first(dfile.get("volumes", ["default"]))
        # flat_dict = to_dict(dfile)
        # default_svc = flat_dict.get("services", {}).get(default_service)

        # pprint (self.__dict__)
        # dsfsdf

        # Build default
        # app_dir = self.path
        result = {
            "paasify_sep": "_",
            "prj_path": self.prj_dir,
            "prj_namespace": self.prj.config.namespace,
            "prj_domain": to_domain(self.prj.config.namespace),
            "stack_name": self.ident,
            "stack_network": default_network,
            "stack_service": default_service,
            "stack_path": self.stack_dir,
            "stack_app_path": self.app.app_dir,
            "stack_collection_app_path": self.app.collection_dir,
            # "app_network_name": self.namespace,
            # # "app_image": "TOTO",
            # "app_service": default_service,
            # "app_volume": default_volume,
            # "app_network": default_network,
            # "app_dir": app_dir,
            # "app_dir_conf": './' + os.path.join(app_dir, 'conf'),
            # "app_dir_data": './' + os.path.join(app_dir, 'data'),
            # "app_dir_logs": './' + os.path.join(app_dir, 'logs'),
        }
        return result

    def process_jsonnet(self, file, action, data):
        "Process jsonnet file"

        # Developper init
        data = data or {}
        assert isinstance(data, dict), f"DAta must be dict, got: {data}"
        assert action in [
            "metadata",
            "vars_default",
            "vars_override",
            "docker_override",
        ], f"Action not supported: {action}"

        # Prepare input variables
        ext_vars = {
            "action": json.dumps(action),
        }
        for key, val in data.items():
            ext_vars[key] = json.dumps(val)

        # Process jsonnet tag
        try:
            # pylint: disable=c-extension-no-member
            result = _jsonnet.evaluate_file(
                file,
                ext_vars=ext_vars,
            )
        except RuntimeError as err:
            self.log.critical(f"Can't parse jsonnet file: {file}")
            raise error.JsonnetBuildFailed(err)

        # Return python object from json output
        return json.loads(result)

    def gen_stacks_vars(self, docker_file=None, all_tags=None):
        "Generate global and local vars"
        globvars = self.prj.config.vars
        localvars = self.vars

        # 1. Define default generic local stack vars
        vars_base = self.gen_conveniant_vars(docker_file=docker_file)

        # 2. Read tag vars
        # Run each tag and get default variables
        all_tags = all_tags or []
        jsonnet_cand = flatten(
            [x["jsonnet_file"] for x in all_tags if x["jsonnet_file"]]
        )

        # 3. Process default tags vars !
        for jsonnet_file in jsonnet_cand:

            # Parse jsonnet file
            ext_vars = {
                "user_data": vars_base,
            }

            payload = self.process_jsonnet(jsonnet_file, "vars_default", ext_vars)

            # Update result
            for key, val in payload["vars_default"].items():
                vars_base[key] = val

        # 4. Read static files:
        # Read <collection>/<stack>/vars.yml
        # Read <stack>/vars.yml
        lookup = [
            {
                "path": self.app.app_dir,
                "pattern": ["vars.yml", "vars.yaml"],
            },
            {
                "path": self.stack_dir,
                "pattern": ["vars.yml", "vars.yaml"],
            },
        ]
        vars_cand = lookup_candidates(lookup)
        vars_cand = flatten([x["matches"] for x in vars_cand])
        for cand in vars_cand:
            conf = anyconfig.load(cand, ac_parser="yaml")
            vars_base.update(conf)

        # 5. Read project vars with parsing
        vars_global = globvars.parse_vars(current=vars_base)

        # 6. Read stack vars with parsing
        vars_run = localvars.parse_vars(current=vars_global)

        # 7. Loop again on tags and override/process tags vars
        # Overrides unset vars only
        for jsonnet_file in jsonnet_cand:

            # Parse jsonnet file
            ext_vars = {
                "user_data": vars_run,
            }
            payload = self.process_jsonnet(jsonnet_file, "vars_override", ext_vars)

            # Update result if current value is kinda null
            for key, val in payload["vars_override"].items():
                dst = vars_run.get(key, None)
                # print(dst)
                if not dst:
                    vars_run[key] = val

        return vars_run

    def assemble(self):
        "Generate docker-compose.run.yml and parse it with jsonnet"

        print(f"Build the stack: {self}")

        # 1. Update sources
        # TOFIX: Be more selective on the source
        if not len(self.prj.sources.get_children()) > 0:
            msg = f"Missing default source for stack: {self.serialize(mode='raw')}"
            raise error.StackMissingOrigin(msg)

        for src_name, src in self.prj.sources.get_children().items():
            src.install(update=False)

        # 2. Resolve all tags files
        all_tags = self.get_tag_plan()

        # 3. Parse stack vars
        vars_run = self.gen_stacks_vars(
            docker_file=all_tags[0]["docker_file"], all_tags=all_tags
        )

        # Report to user
        self.log.info("Docker vars:")
        for key, val in vars_run.items():
            self.log.info(f"  {key}: {val}")

        # 4. Build docker files list
        self.log.info("Docker files:")
        docker_files = []
        for cand in all_tags:
            docker_file = cand.get("docker_file")
            if docker_file:
                docker_files.append(docker_file)
                self.log.info(f"  Insert: {docker_file}")

        # 5. Prepare docker-file output directory
        outfile = os.path.join(self.stack_dir, "docker-compose.run.yml")
        if not os.path.isdir(self.stack_dir):
            self.log.info(f"Create missing directory: {self.stack_dir}")
            os.mkdir(self.stack_dir)

        # 6. Build final docker file
        engine = self.engine
        try:
            out = engine.assemble(docker_files, env=vars_run)
        except Exception as err:
            err = bin2utf8(err)
            # pylint: disable=no-member
            self.log.critical(err.txterr)
            raise err
            # raise error.DockerBuildConfig(
            #     f"Impossible to build docker-compose files: {err}"
            # ) from err

        # Fetch output
        docker_run_content = out.stdout.decode("utf-8")
        docker_run_payload = anyconfig.loads(docker_run_content, ac_parser="yaml")

        # 7. Build jsonnet files
        self.log.info("Jsonnet files:")

        for cand in all_tags:
            docker_file = cand.get("docker_file")

            # Fetch only jsonnet if docker_file is absent
            if docker_file:
                continue
            jsonnet_file = cand.get("jsonnet_file")
            if not jsonnet_file:
                continue
            self.log.info(f"  Insert: {jsonnet_file}")

            # Create local environment vars
            jsonnet_data = cand.get("tag").vars or {}
            env_vars = dict(vars_run)
            env_vars.update(jsonnet_data)

            # Parse jsonnet file
            ext_vars = {
                "user_data": env_vars,
                "docker_file": docker_run_payload,
            }
            payload = self.process_jsonnet(jsonnet_file, "docker_override", ext_vars)

            docker_run_payload = payload["docker_override"]

            # # Prepare jsonnet environment
            # assert isinstance(jsonnet_data, dict), f"Error, env is not a dict, got: {type(jsonnet_data)}"
            # ext_vars = {
            #     # ALL VALUES MUST BE JSON STRINGS
            #     "action": json.dumps("docker_override"),
            #     "user_data": json.dumps(jsonnet_data),
            #     "docker_file": json.dumps(docker_run_payload),
            # }

            # # Process jsonnet tag
            # try:
            #     result = _jsonnet.evaluate_file(
            #         jsonnet_file,
            #         ext_vars=ext_vars,
            #     )
            # except RuntimeError as err:
            #     self.log.critical(f"Can't parse jsonnet file: {jsonnet_file}")
            #     raise error.JsonnetBuildFailed(err)
            # docker_run_payload = json.loads(result)["docker_override"]
            # pprint (docker_run_payload)
            # docker_run_payload = result["docker_override"]

        # 8. Save the final docker-compose.run.yml file
        self.log.notice(f"Writing docker-compose file: {outfile}")
        # pprint (docker_run_payload)
        output = to_yaml(docker_run_payload)
        write_file(outfile, output)

    def explain_tags(self):
        "Explain hos tags are processed on stack"

        print(f"  Scanning stack plugins: {self.ident}")
        matches = self.get_tag_plan()

        # 0. Internal functions
        def list_items(items):
            "List items"
            _first = "*"
            # list_items(items)
            for cand in items:
                print(f"          {_first} {cand}")
                _first = "-"

        def list_jsonnet_files(items):
            "List jsonnet files"
            for match in items:

                tag = match.get("tag")
                if tag:
                    cand = match.get("jsonnet_file")
                    if cand:
                        print(f"        - {tag.name}")

        # 1. Show all match combinations
        for match in matches:

            tag = match.get("tag")

            if not tag:
                print("    Default config:")
                list_items(self.docker_candidates)
                print("    Tag config:")
                continue

            print(f"      tag: {tag.name}")

            if tag.docker_candidates:
                print("        Docker tags:")
                list_items(tag.docker_candidates)

            if tag.jsonnet_candidates:
                print("        Jsonnet tags:")
                list_items(tag.jsonnet_candidates)

        # 2. Show actual loading
        print("\n    Tag Loading Order:")

        # 2.1 Var loading
        print("      Loading vars:")
        list_jsonnet_files(matches)

        # 2.2 Tag loading
        print("      Loading Tags:")
        for match in matches:

            tag = match.get("tag")

            if not tag:
                cand = match.get("docker_file")
                print(f"        * base: {cand}")
                continue
            else:
                cand = match.get("docker_file")
                if cand:
                    print(f"        - {tag.name}")

        # 2.3 Jsonnet loading
        print("      Loading jsonnet:")
        list_jsonnet_files(matches)

    def gen_doc(self, output_dir=None):
        "Generate documentation"

        matches = self.get_tag_plan()

        # 3. Show jsonschema
        print("\n    Plugins jsonschema:")
        for match in matches:

            tag = match.get("tag")
            if not tag:
                continue

            file = match.get("jsonnet_file")
            if not file:
                continue

            # Create output dir
            dest_dir = os.path.join(output_dir, tag.name)
            if not os.path.isdir(dest_dir):
                os.makedirs(dest_dir)

            print(f"        # {tag.name}: {file}")
            out = self.process_jsonnet(file, "metadata", None)
            tag_meta = out["metadata"]
            tag_schema = tag_meta.get("jsonschema")
            # pprint (tag_meta)
            if "jsonschema" in tag_meta:
                del tag_meta["jsonschema"]

            dest_schema = os.path.join(dest_dir, f"jsonschema")
            if tag_schema:
                print(f"Generated jsonschema files in: {dest_schema}.[json|yml]")
                write_file(dest_schema + ".json", to_json(tag_schema))
                write_file(dest_schema + ".yml", to_yaml(tag_schema))

            # Create HTML documentation
            if ENABLE_JSON_SCHEMA:

                fname = "web.html"
                dest_html = os.path.join(dest_dir, fname)
                print(f"Generated HTML doc in: {dest_html}")
                config = GenerationConfiguration(
                    copy_css=True,
                    description_is_markdown=True,
                    examples_as_yaml=True,
                    footer_show_time=False,
                    expand_buttons=True,
                    show_breadcrumbs=False,
                )
                generate_from_filename(dest_schema + ".json", dest_html, config=config)

                # /schema_doc/paasify_yml_schema.html
                # /plugin_api_doc/{tag.name}/web.html
                markdown_doc = f"""
# {tag.name}

Documentationfor tag: `{tag.name}`

## Informations

``` yaml
{to_yaml(tag_meta)}
```

## Tag documentation

<iframe scrolling="yes" src="/plugins_apidoc/{tag.name}/{fname}" style="width: 100vw; height: 70vh; overflow: auto; border: 0px;">
</iframe>


                """
                dest_md = os.path.join(dest_dir, f"markdown.md")
                write_file(dest_md, markdown_doc)
                print(f"Generated Markdown doc in: {dest_md}")


class PaasifyStackManager(NodeList, PaasifyObj):
    "Manage a list of stacks"

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Stack configuration",
        "type": "array",
        "default": [],
        # "items": PaasifyStack.schema_def,
    }

    conf_children = PaasifyStack

    def conf_post_build(self):
        "(deprecated)"

        stack_paths = self.list_stack_by("path")
        # stack_names = self.list_stack_by("name")

        dup = duplicates(stack_paths)
        if len(dup) > 0:
            raise error.ProjectInvalidConfig(f"Cannot have duplicate paths: {dup}")

    def list_stacks(self):
        "Get stacks children (deprecated)"
        return self.get_children()

    def list_stack_by_ident(self):
        "List stack per idents"
        return [x.ident for x in self.get_children()]

    def list_stack_by(self, attr="ident"):
        "List stacks by attribute"
        return [getattr(x, attr) for x in self.get_children()]

    # TODO: IS THIS ONE USED AT SOME POINTS ?
    def cmd_stack_assemble(self, stacks=None):
        "Assemble a stack"

        stacks = stacks or self._nodes
        for stack in stacks:
            print(stack)

            # stack.assemble()

    def cmd_stack_up(self, stacks=None):
        "Start a stack"

        stacks = stacks or self._nodes
        for stack in stacks:
            stack.up()

    def cmd_stack_down(self, stacks=None):
        "Stop a stack"

        stacks = stacks or self._nodes
        for stack in stacks:
            stack.down()

    def cmd_stack_recreate(self, stacks=None):
        "Recreate a stack"

        self.cmd_stack_down(stacks=stacks)
        self.cmd_stack_assemble(stacks=stacks)
        self.cmd_stack_up(stacks=stacks)

    def cmd_stack_apply(self, stacks=None):
        "Apply a stack"

        self.cmd_stack_assemble(stacks=stacks)
        self.cmd_stack_up(stacks=stacks)
