import os
import sys
from string import Template
import logging


from pprint import pprint

from cafram.nodes import NodeList, NodeMap, NodeDict
from cafram.base import Log, Base, Hooks
from cafram.utils import serialize, flatten, json_validate

import paasify.errors as error


_log = logging.getLogger()


# class PaasifyObj(Conf,Family,Log,Base):
class PaasifyObj(Log, Hooks, Base):

    module = "paasify"
    log = _log

    def __init__(self, *args, **kwargs):
        # print ("INIT PaasifyObj", self, '->'.join([ x.__name__ for x in self.__class__.__mro__]), args, kwargs)

        super(PaasifyObj, self).__init__(*args, **kwargs)

        # self.log.trace(f"__init__: PaasifyObj2/{self}")
        # print(f"XXX: __init__: PaasifyObj2/{self}")


class PaasifySimpleDict(NodeMap, PaasifyObj):

    conf_default = {}


class PaasifyConfigVar(NodeMap, PaasifyObj):

    conf_ident = "{self.name}={self.value}"
    conf_default = {
        "name": None,
        "value": None,
    }

    def node_hook_transform(self, payload):

        result = None
        if isinstance(payload, dict):
            for key, value in payload.items():
                result = {
                    "name": key,
                    "value": value,
                }
        elif isinstance(payload, str):
            value = payload.split("=", 2)
            result = {
                "name": value[0],
                "value": value[1],
            }
        else:
            raise Exception(f"Unsupported () type {type(payload)}: {payload}")

        # print (f"INIT NEW VAR: {result} VS {payload}")
        return result

    # def conf_post_build(self):

    #     self.ident = f"{self.name}={self.value}"


class PaasifyConfigVars(NodeList, PaasifyObj):

    conf_children = PaasifyConfigVar

    conf_schema = {
        # "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Environment configuration",
        "description": "Environment configuration. Paasify leave two choices for the configuration, either use the native dict configuration or use the docker-compatible format",
        "default": {},
        "oneOf": [
            {
                "title": "Env configuration (dict)",
                "examples": [
                    {
                        "env": {
                            "MYSQL_ADMIN_USER": "MyUser",
                            "MYSQL_ADMIN_DB": "MyDB",
                        }
                    }
                ],
                "type": "object",
                "patternProperties": {
                    ".*": {
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
                                "type": "null",
                            },
                        ],
                    }
                },
            },
            {
                "title": "Env configuration (list)",
                "examples": [
                    {
                        "env": [
                            "MYSQL_ADMIN_USER=MyUser",
                            "MYSQL_ADMIN_DB=MyDB",
                        ]
                    }
                ],
                "type": "array",
                "items": {
                    "title": "Environment list",
                    "description": "Value must be a string, under the form of: KEY=VALUE",
                    "type": "string",
                },
            },
            {
                "title": "Env configuration (Empty)",
                "examples": [{"env": None}],
                "type": "null",
            },
        ],
    }

    def node_hook_transform(self, payload):

        result = []
        if not payload:
            pass
        elif isinstance(payload, dict):
            for key, value in payload.items():
                var_def = {key: value}
                result.append(var_def)
        elif isinstance(payload, list):
            result = payload

        # elif isinstance(payload, str):
        #         value = payload.split("=", 2)
        #         result = {
        #             "name": value[0],
        #             "value": value[1],
        #         }
        else:
            raise error.InvalidConfig(f"Unsupported type: {payload}")

        # print (f"INIT NEW VARSSSS: {type(payload)} {result} VS {payload}")
        return result

    def parse_vars(self, current=None):

        result = dict(current or {})

        for var in self._nodes:
            value = var.value
            if isinstance(value, str):

                # Safe usage of user input templating
                tpl = Template(value)
                try:
                    value = tpl.substitute(**result)
                except KeyError as err:
                    self.log.warning(
                        f"Variable {err} is not defined in: {var.name}='{value}'"
                    )
                except Exception as err:
                    self.log.warning(
                        f"Could not parse variable: {var.name}='{value}' ( => {err.__class__}/{err})"
                    )

            result[var.name] = value

        return result


class PaasifySource(NodeDict, PaasifyObj):
    "Paasify source configuration"

    def install(self, update=False):
        "Install a source if not updated"

        # Check if the source if installed or install latest

        prj = self.get_parent().get_parent()
        coll_dir = prj.runtime.project_collection_dir
        src_dir = os.path.join(coll_dir, self.ident)
        git_dir = os.path.join(src_dir, ".git")

        if os.path.isdir(git_dir) and not update:
            self.log.debug(
                f"Collection '{self.ident}' is already installed in: {git_dir}"
            )
            return

        self.log.info(f"Install source '{self.ident}' in: {git_dir}")
        raise NotImplemented


class PaasifySources(NodeDict, PaasifyObj):
    "Sources manager"
    conf_children = PaasifySource
