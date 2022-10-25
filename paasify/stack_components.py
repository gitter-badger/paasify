"""
Stack components class

"""

import os
from string import Template
from pprint import pprint

import json
import _jsonnet
import anyconfig

from cafram.nodes import NodeList, NodeMap
from cafram.utils import flatten, first

from paasify.common import lookup_candidates
from paasify.framework import PaasifyObj, PaasifyConfigVar
import paasify.errors as error
from paasify.engines import bin2utf8


# =======================================================================================
# Stack Assembler
# =======================================================================================


class StackAssembler(PaasifyObj):
    "Object to manage stack assemblage"

    _vars = []

    conf_logger = "paasify.cli.builder"

    def __init__(self, *arsg, **kwargs):

        self._vars = []
        super().__init__(*arsg, **kwargs)

    # Vars management
    # ===========================

    def add_as_key(self, key, value):
        "Add a list of vars into object"
        obj = PaasifyConfigVar(
            parent=None, ident="PaasifyStackVar", payload={key: value}
        )
        self._vars.append(obj)

    def add_as_list(self, vars):
        "Add a list of vars into object"
        assert isinstance(vars, list)
        self._vars.extend(vars)

    def add_as_dict(self, vars):
        "Add a list of vars into object"
        assert isinstance(vars, dict)

        for var_name, var_value in vars.items():
            self.add_as_key(var_name, var_value)

    def template_value(self, value, env, hint=None):
        "Render a string with template engine"

        if not isinstance(value, str):
            return value

        # Safe usage of user input templating
        tpl = Template(value)

        # pylint: disable=broad-except
        try:
            old_value = value
            value = tpl.substitute(**env)
            if old_value != value:
                self.log.debug(f"Transformed template value: {old_value} => {value}")

        except KeyError as err:
            self.log.warning(f"Variable {err} is not defined in: {hint}='{value}'")

        except Exception as err:
            self.log.warning(
                f"Could not parse variable: {hint}='{value}' ( => {err.__class__}/{err})"
            )
            raise error.ProjectInvalidConfig(err)

        return value

    def render_as_dict(self, parse=False, dict_override=None):
        "Return a dict of the variable"

        result = {}
        for var in self._vars:
            key = var.name
            value = var.value

            if parse:
                value = self.template_value(value, result, hint=key)
            result[key] = value

        # Dict override
        if dict_override:
            result.update(dict_override)
            if parse:
                for key, value in dict_override.items():
                    result[key] = self.template_value(value, result, hint=key)

        return result

    # Docker processors
    # ===========================
    def _get_docker_files(self, all_tags):
        "Retrieve the list of tags docker-files"

        self.log.info("Docker files:")
        docker_files = []
        for cand in all_tags:
            docker_file = cand.get("docker_file")
            if docker_file:
                docker_files.append(docker_file)
                self.log.info(f"  Insert: {docker_file}")

        return docker_files

    def assemble_docker_compose(self, all_tags, engine):
        "Generate the docker-compose file"

        docker_files = self._get_docker_files(all_tags)

        # Report to user
        env = self.render_as_dict(parse=True)

        self.log.debug("Docker vars:")
        for key, val in env.items():
            self.log.debug(f"  {key}: {val}")

        try:
            out = engine.assemble(docker_files, env=env)
        except Exception as err:
            err = bin2utf8(err)
            # pylint: disable=no-member
            self.log.critical(err.txterr)
            raise error.DockerBuildConfig(
                f"Impossible to build docker-compose files: {err}"
            ) from err

        # Fetch output
        docker_run_content = out.stdout.decode("utf-8")
        docker_run_payload = anyconfig.loads(docker_run_content, ac_parser="yaml")
        return docker_run_payload

    # Vars processors
    # ===========================

    def process_yml_vars(self, lookup):
        """Process yml vars from a tag_list"""

        self.log.info("Process yaml vars")

        vars_cand = lookup_candidates(lookup)
        vars_cand = flatten([x["matches"] for x in vars_cand])
        for cand in vars_cand:
            self.log.debug(f"Loading vars file: {cand}")
            conf = anyconfig.load(cand, ac_parser="yaml")
            assert isinstance(conf, dict)
            self.add_as_dict(conf)

    def process_jsonnet_vars(self, all_tags):
        """Process jsonnet vars from a tag_list"""

        for cand in all_tags:

            jsonnet_file = cand.get("jsonnet_file")
            if not jsonnet_file:
                continue

            current_vars = self.render_as_dict()
            # Parse jsonnet file
            ext_vars = {
                "user_data": current_vars,
            }
            self.log.debug(f"Loading jsonnet vars file: {jsonnet_file}")
            payload = self.process_jsonnet_exec(jsonnet_file, "vars_default", ext_vars)

            # Update result
            for key, val in payload["vars_default"].items():

                # Set variable only if not already set
                curr_val = current_vars.get(key, None)
                if curr_val is None:
                    self.add_as_key(key, val)

        # return vars_run

    def process_jsonnet_transforms(self, all_tags, docker_run_payload):
        "Process jsonnet tag jsonnet transforms"

        self.log.info("Jsonnet files (transform):")

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
            jsonnet_data = {}
            tag = cand.get("tag")
            if tag:
                jsonnet_data = tag.vars or {}
            # print ("UPDATING DOCKER VARS", jsonnet_data)

            env_vars = self.render_as_dict(parse=True, dict_override=jsonnet_data)

            # env_vars.update(jsonnet_data)

            # Remove all null values
            # Should I keep this ?
            # => env_vars = {k: v for k, v in env_vars.items() if v is not None}

            # Parse jsonnet file
            ext_vars = {
                "user_data": env_vars,
                "docker_file": docker_run_payload,
            }
            # self.log.debug(f"Loading jsonnet transform file: {jsonnet_file}")
            payload = self.process_jsonnet_exec(
                jsonnet_file, "docker_override", ext_vars
            )
            docker_run_payload = payload["docker_override"]

        return docker_run_payload

    def process_jsonnet_exec(self, file, action, data):
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
        self.log.trace(f"Process jsonnet: {file} (action={action})")
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


# =======================================================================================
# Stack Apps
# =======================================================================================


class PaasifyStackApp(NodeMap, PaasifyObj):
    "Stack Applicationk Object"

    conf_default = {
        "app": None,
        "app_source": None,
        "app_path": None,
        "app_name": None,
    }

    def node_hook_transform(self, payload):

        if isinstance(payload, str):
            payload = {"app": payload}

        app_def = payload.get("app")
        app_path = payload.get("app_path")
        app_source = payload.get("app_source")
        app_name = payload.get("app_name")

        app_split = app_def.split(":", 2)

        if len(app_split) == 2:
            app_source = app_source or app_split[0] or "default"
            app_path = app_path or app_split[1]
        else:
            # Get from default namespace
            app_name = app_source or app_split[0] or "default"
            app_source = "default"
            app_path = app_name
        app_def = f"{app_source}:{app_path}"

        if not app_name:
            app_name = "_".join([part for part in os.path.split(app_path) if part])

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
            self.prj.runtime.project_collection_dir, self.app_source
        )
        self.app_dir = os.path.join(self.collection_dir, self.app_path)
        self.tags_dir = os.path.join(self.collection_dir, ".paasify", "plugins")

    def lookup_docker_files_app(self):
        """Lookup docker-compose files in app directory"""

        lookup = [
            {
                "path": self.app_dir,
                "pattern": ["docker-compose.yml", "docker-compose.yml"],
            }
        ]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([x["matches"] for x in local_cand])

        return local_cand

    def lookup_jsonnet_files_app(self):
        """Lookup docker-compose files in app directory"""

        lookup = [
            {
                "path": self.app_dir,
                "pattern": ["docker-compose.yml", "docker-compose.yml"],
            }
        ]
        local_cand = lookup_candidates(lookup)
        local_cand = flatten([x["matches"] for x in local_cand])

        return local_cand


# =======================================================================================
# Stack Tag schemas
# =======================================================================================

stack_name_pattern = {
    "title": "Short form",
    "description": (
        "Just pass the tag you want to apply as string."
        " This form does not allow jsonnet ovar override"
    ),
    "type": "string",
    "oneOf": [
        {
            "title": "Reference collection app",
            "description": (
                "Reference a tag from a specific collection."
                " This form does not allow jsonnet ovar override"
            ),
            "pattern": "^.*:.*$",
        },
        {
            "title": "Direct or absolute app path",
            "description": ("Reference a tag from a specific collection."),
            "pattern": ".*/[^:]*",
        },
        {
            "title": "Tag",
            "description": ("Will find the best matvhing tag."),
            "pattern": "^.*$",
        },
    ],
}


stack_ref_kind_defs = [
    {
        "title": "With value",
        "description": "Pass extra vars for during jsonet tag processing.",
        "type": "object",
    },
    {
        "title": "Without value",
        "description": ("No vars are added for this jsonnet tag processing."),
        "type": "null",
    },
]
stack_ref_defs = {
    "[!^~].*": {
        "title": "Disabled Tag: ~$tag_name",
        "description": (
            "Disable a tag from processing. Any vars are ignored. Other chars are also supported: !^"
        ),
        "oneOf": stack_ref_kind_defs,
        "default": {},
    },
    "^.*:.*$": {
        "title": "Collection tag: $collection_name:$tag_name",
        "description": (
            "Reference a tag from a specific collection."
            "See: Specific tag documentation for further informations."
        ),
        "oneOf": stack_ref_kind_defs,
        "default": {},
    },
    # ".*/[^:]*": {
    #     "title": "Absolute tag: $tag_path",
    #     "description": (
    #         "Reference a tag from a absolute app path."
    #     ),
    # },
    ".*": {
        "title": "Tag name: $tag_name",
        "description": (
            "Will find the best matching tag."
            "See: Specific tag documentation for further informations."
        ),
        "oneOf": stack_ref_kind_defs,
        "default": {},
    },
}


class PaasifyStackTag(NodeMap, PaasifyObj):
    """Paasify Stack object"""

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "StackTag configuration",
        "description": (
            "Tag definition. It support two formats at the same time: as string or dict."
            " If the name is prefixed with a `!`, then it is removed from the"
            " processing list (both vars, docker-file and jsonnet processing)."
        ),
        "oneOf": [
            {
                "title": "As string",
                "description": (
                    "Just pass the tag you want to apply as string."
                    " This form does not allow jsonnet ovar override"
                ),
                "type": "string",
                "default": "",
                "examples": [
                    {
                        "tags": [
                            "my_tagg",
                            "~my_prefix_tag",
                            "my_collection:my_prefix_tag",
                        ],
                    },
                ],
                "oneOf": [
                    {
                        "title": stack["title"],
                        "description": stack["description"],
                        "pattern": stack_pattern,
                    }
                    for stack_pattern, stack in stack_ref_defs.items()
                ],
            },
            {
                "title": "As object",
                "description": (
                    "Define a tag. The key represent the name of the"
                    " tag, while it's value is passed as vars during"
                    " jsonnet processing. This form allow jsonnet ovar override"
                ),
                "type": "object",
                "default": {},
                "examples": [
                    {
                        "tags": [
                            {
                                "other_tag": {
                                    "specific_conf": "val1",
                                }
                            },
                            {"my_collection:another_tag": None},
                            {
                                "~ignore_this_tag": {
                                    "specific_conf": "val1",
                                }
                            },
                        ],
                    },
                ],
                "minProperties": 1,
                "maxProperties": 1,
                # "additionalProperties": False,
                "patternProperties": stack_ref_defs,
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
            # "cls": dict,
        },
    ]
    #     {
    #     "name": str,
    #     "vars": dict,
    # }

    # Place to store list of candidates
    jsonnet_candidates = None
    docker_candidates = None

    # Object shortcuts
    stack = None
    prj = None
    app = None

    def node_hook_transform(self, payload):

        # Init parent objects
        self.stack = self.get_parent().get_parent()
        self.prj = self.stack.get_parent().get_parent()
        self.app = self.prj.get_parents()

        # Transform input
        result = {
            "name": None,
            "vars": {},
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

    def _lookup_file(self, dirs, pattern):
        "Lookup a specific file name in dirs"

        lookup = []
        for dir_ in dirs:
            self.log.trace(f"Looking up file '{','.join(pattern)}' in dir: {dir_}")
            lookup_def = {
                "path": dir_,
                "pattern": pattern,
            }
            lookup.append(lookup_def)

        local_cand = lookup_candidates(lookup)
        local_cand = flatten([x["matches"] for x in local_cand])

        return local_cand

    def lookup_docker_files_tag(self, dirs):
        """Lookup docker-compose files in app directory"""
        pattern = [f"docker-compose.{self.name}.yml", f"docker-compose.{self.name}.yml"]
        return self._lookup_file(dirs, pattern)

    def lookup_jsonnet_files_tag(self, dirs):
        """Lookup docker-compose files in app directory"""
        pattern = [f"{self.name}.jsonnet"]
        return self._lookup_file(dirs, pattern)


class PaasifyStackTagManager(NodeList, PaasifyObj):
    "Manage Stacks"

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Paasify Stack Tags configuration",
        "description": ("Determine a list of tags to apply."),
        "type": "array",
        # "default": [],
        # "additionalProperties": PaasifyStackTag.conf_schema,
        # "items": PaasifyStackTag.conf_schema,
        "oneOf": [
            {
                "title": "List of tags",
                "description": (
                    "Define a list of tags. You can interact in few ways with"
                    " tags. Tags can support boths syntaxes at the same time."
                ),
                "type": "array",
                "default": [],
                "additionalProperties": PaasifyStackTag.conf_schema,
                # "items": PaasifyStackTag.conf_schema,
                "examples": [
                    {
                        "tags": [
                            "my_tagg",
                            "~my_prefix_tag",
                            "my_collection:my_prefix_tag",
                            {
                                "other_tag": {
                                    "specific_conf": "val1",
                                }
                            },
                            {"my_collection:another_tag": None},
                            {
                                "~ignore_this_tag": {
                                    "specific_conf": "val1",
                                }
                            },
                        ],
                    },
                ],
            },
            {
                "title": "Unset",
                "description": "Do not declare any tags",
                "type": "null",
                "default": None,
                "examples": [
                    {
                        "tags": None,
                    },
                ],
            },
        ],
    }

    conf_children = PaasifyStackTag

    def list_tags(self):
        "List all tags (deprecated)"
        return self._nodes

    def resolve_tags_files(self, dirs):
        """Generate a list of file tags

        Return a list of dict:
        """

        # Actually find best candidates
        results = []
        for tag in self.get_children():

            # Match files
            docker_files = tag.lookup_docker_files_tag(dirs)
            jsonnet_files = tag.lookup_jsonnet_files_tag(dirs)

            # Backup data in object
            tag.jsonnet_candidates = jsonnet_files
            tag.docker_candidates = docker_files

            # Sanity check
            if len(jsonnet_files) + len(docker_files) == 0:
                dirs = ', '.join(dirs)
                msg = f"Could not find tag '{tag.name}' for stack '{tag.stack.stack_name}' in following directories: {dirs}"
                raise error.MissingTag(msg)

            results.append(
                {
                    "tag": tag,
                    "jsonnet_file": first(jsonnet_files),
                    "docker_file": first(docker_files),
                }
            )

        return results
