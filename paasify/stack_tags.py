from cafram.nodes import NodeList, NodeMap
from cafram.utils import serialize, flatten

from paasify.common import lookup_candidates
from paasify.framework import PaasifyObj


class PaasifyStackTag(NodeMap, PaasifyObj):

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "StackTag configuration",
        "oneOf": [
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
                    ".*": {
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
        "default": [],
        "oneOf": [
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
