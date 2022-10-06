import os

from cafram.nodes import NodeList, NodeMap
from cafram.utils import flatten

from paasify.common import lookup_candidates
from paasify.framework import PaasifyObj


# =======================================================================================
# Stack Apps
# =======================================================================================


class PaasifyStackApp(NodeMap, PaasifyObj):

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

    def node_hook_transform(self, payload):

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

    def node_hook_children(self):
        "Self init object after loading of app"

        self.prj = self.get_parent()
        self.app = self.get_parents()

        # print("TAG", self, self.get_parents())
        # totooo

        # self.app_dir = os.path.join(
        #     self.prj.runtime.project_root_dir,
        #     '.paasify', 'collections',
        #     self.app_source, self.app_path)

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
        return self._nodes
