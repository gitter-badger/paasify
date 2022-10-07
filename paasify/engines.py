"""Paasify Engine management

This class helps to deal with docker engine versions
"""

# pylint: disable=logging-fstring-interpolation
# pylint: disable=invalid-name


import os
import re
import logging
import json

from distutils.version import StrictVersion

# from packaging.version import StrictVersion
from pprint import pprint

import semver

# from semver.version import Version

import sh

from cafram.utils import _exec
from cafram.nodes import NodeMap

import paasify.errors as error
from paasify.common import cast_docker_compose
from paasify.framework import PaasifyObj


log = logging.getLogger(__name__)


def bin2utf8(obj):
    "Transform sh output bin to utf-8"

    if hasattr(obj, "stdout"):
        obj.txtout = obj.stdout.decode("utf-8").rstrip("\n")
    else:
        obj.txtout = None
    if hasattr(obj, "stderr"):
        obj.txterr = obj.stderr.decode("utf-8").rstrip("\n")
    else:
        obj.txterr = None
    return obj


#####################


class EngineCompose(NodeMap, PaasifyObj):
    "Generic docker-engine compose API"

    version = None
    docker_file_exists = False
    docker_file_path = None
    arg_prefix = []

    conf_default = {
        "project_dir": ".",
        "project_name": "default",
        "docker_file": "docker-compose.yml",
    }

    ident = "default"

    def node_hook_children(self):
        "Create stack context on start"
        # , project_dir=None, project_name=None, docker_file='docker-compose.run.yml', **kwargs):

        # self.project_dir = project_dir
        # self.project_name = project_name

        # DEPRECATED self.cont_engine = EngineDocker(self)
        # self.compose_engine = EngineCompose(self)
        # self.jsonnet_engine = EngineJsonnet(self)

        # pprint (self.conf_default)
        # pprint (self.__dict__)

        # stack = self.get_parent()
        # prj = stack.get_parent().get_parent()
        # print (">>>>>>> STACK, PROJECT", stack, prj)
        project_name = self.project_name
        project_dir = self.project_dir

        self.arg_prefix = [
            "--project-name",
            f"{project_name}",
            "--project-directory",
            f"{project_dir}",
        ]
        # print ((project_dir, self.docker_file))
        self.docker_file_path = os.path.join(project_dir, self.docker_file)

        # self.docker_file_exists = False
        if os.path.isfile(self.docker_file_path):
            self.docker_file_exists = True

        # self.engine = 'docker'
        # self.engine = 'podman-compose'

        # Check here if support for with versions:
        # docker-compose (legacy) (support all)
        # docker compose (new) (support docker only)
        # podman compose (new) (support podman only)

    def assemble(self, compose_files, env_file=None, env=None):
        "Generate docker-compose file"

        cli_args = list(self.arg_prefix)

        if env_file:
            cli_args.extend(["--env-file", env_file])
        for file in compose_files:
            cli_args.extend(["--file", file])
        cli_args.extend(
            [
                "config",
                # "--no-interpolate",
                # "--no-normalize",
            ]
        )

        env_string = env or {}
        env_string = {
            k: cast_docker_compose(v) for k, v in env.items() if v is not None
        }

        result = _exec(
            "docker-compose", cli_args, _out=None, _env=env_string, logger=self.log
        )
        bin2utf8(result)
        return result

    # pylint: disable=invalid-name
    def up(self, **kwargs):
        "Start containers"

        if not self.docker_file_exists:
            self.log.notice(f"Stack {self.parent.project_name} is not built yet")
            return None

        cli_args = list(self.arg_prefix)
        cli_args = [
            "--file",
            self.docker_file_path,
            "up",
            "--detach",
        ]
        out = _exec("docker-compose", cli_args, **kwargs)
        if out:
            out = bin2utf8(out)
            log.notice(out.txtout)

    def down(self, **kwargs):
        "Stop containers"

        if not self.docker_file_exists:
            self.log.notice(f"Stack {self.parent.project_name} is not built yet")
            return None

        cli_args = list(self.arg_prefix)
        cli_args = [
            "--file",
            self.docker_file_path,
            "down",
            "--remove-orphans",
        ]

        try:
            out = _exec("docker-compose", cli_args, **kwargs)
            if out:
                bin2utf8(out)
                log.notice(out.txtout)

        # pylint: disable=no-member
        except sh.ErrorReturnCode_1 as err:
            bin2utf8(err)

            # This is U.G.L.Y
            if not "has active endpoints" in err.txterr:
                raise error.DockerCommandFailed(f"{err.txterr}")

    def logs(self, follow=False):
        "Return container logs"

        if not self.docker_file_exists:
            self.log.notice(f"Stack {self.parent.project_name} is not built yet")
            return None

        sh_options = {}
        cli_args = [
            "--file",
            self.docker_file_path,
            "logs",
        ]
        if follow:
            cli_args.append("-f")
            sh_options["_fg"] = True

        _exec("docker-compose", cli_args, **sh_options)

    # pylint: disable=invalid-name
    def ps(self):
        "Return container processes"

        if not self.docker_file_exists:
            self.log.notice(f"Stack {self.parent.project_name} is not built yet")
            return None

        cli_args = [
            "--file",
            self.docker_file_path,
            "ps",
            "--all",
            "--format",
            "json",
        ]

        result = _exec("docker-compose", cli_args, _out=None)
        bin2utf8(result)

        # Report output from json
        stdout = result.txtout
        payload = json.loads(stdout)
        for svc in payload:

            # Get and filter interesting ports
            published = svc["Publishers"] or []
            published = [x for x in published if x.get("PublishedPort") > 0]

            # Reduce duplicates
            for pub in published:
                if pub.get("URL") == "0.0.0.0":
                    pub["URL"] = "::"

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
            print(
                f"  {svc['Project'] :<32} {svc['Name'] :<40} {svc['Service'] :<16} {svc['State'] :<10} {', '.join(exposed)}"
            )


class EngineCompose_26(EngineCompose):
    "Docker-engine: Support for version until 2.6"

    ident = "docker-compose-2.6"


class EngineCompose_129(EngineCompose):
    "Docker-engine: Support for version until 1.29"

    ident = "docker-compose-1.29"

    # pylint: disable=invalid-name
    def ps(self):
        cli_args = [
            "--file",
            self.docker_file_path,
            "ps",
            "--all",
        ]

        result = _exec("docker-compose", cli_args, _fg=True)

        return result


class EngineCompose_16(EngineCompose):
    "Docker-engine: Support for version until 1.6"

    ident = "docker-compose-1.6"


#############################


# # DEPRECATED ?
# class ContainerEngine(PaasifyObj):


#     def __init__(self, project_dir=None, project_name=None):

#         self.project_dir = project_dir
#         self.project_name = project_name

#         # DEPRECATED self.cont_engine = EngineDocker(self)
#         self.compose_engine = EngineCompose(self)
#         #self.jsonnet_engine = EngineJsonnet(self)

#     def assemble(self, compose_files, **kwargs):
#         return self.compose_engine.assemble(compose_files, **kwargs)

#     def up(self, **kwargs):
#         return self.compose_engine.up(**kwargs) if self.compose_engine.docker_file_exists else None

#     def down(self, **kwargs):
#         return self.compose_engine.down(**kwargs) if self.compose_engine.docker_file_exists else None

#     def logs(self, **kwargs):
#         return self.compose_engine.logs(**kwargs) if self.compose_engine.docker_file_exists else None

#     def ps(self, **kwargs):
#         print ("YOOOOOOOOOOO")
#         print (self.compose_engine.docker_file_exists)
#         return self.compose_engine.ps(**kwargs) if self.compose_engine.docker_file_exists else None


#############################

# class EngineDetect(PaasifyObj):
class EngineDetect:
    "Class helper to retrieve the appropriate docker-engine class"

    versions = {
        "docker": {
            "20.10.17": {},
        },
        "docker-compose": {
            "2.6.1": EngineCompose_26,
            "1.29.0": EngineCompose_129,
            "1.6.3": EngineCompose_16,
        },
        "podman-compose": {},
    }

    def detect_docker_compose(self):
        "Detect current version of docker compose. Return a docker-engine class."

        # pylint: disable=no-member
        out = "No output for command"
        try:

            # cmd = sh.Command("docker-compose", _log_msg='paasify')
            log.notice("This can take age when debugger is enabled...")
            out = _exec("docker-compose", ["--version"])
            # TOFIX: This takes ages in debugger, when above _log_msg is unset ?
            # out = cmd('--version')
            bin2utf8(out)
        except sh.ErrorReturnCode as err:
            raise error.DockerUnsupportedVersion(
                f"Impossible to guess docker-compose version: {out}"
            ) from err

        # Scan version
        patt = r"version v?(?P<version>(?P<major>[0-9]+)\.(?P<minor>[0-9]+)\.(?P<patch>[0-9]+))"
        match = re.search(patt, out.txtout)
        if match:
            version = match.groupdict()
        else:
            raise error.DockerUnsupportedVersion(
                f"OUtput format of docker-compose is not recognised: {out.txtout}"
            )
        curr_ver = version["version"]

        # Scan available versions
        versions = [key for key in self.versions["docker-compose"]]
        versions.sort(key=StrictVersion)
        versions.reverse()
        match = None
        for version in versions:
            works = semver.match(curr_ver, f">={version}")
            if works:
                match = version
                break

        if not match:
            raise error.DockerUnsupportedVersion(
                f"Version of docker-compose is not supported: {curr_ver}"
            )

        cls = self.versions["docker-compose"][match]
        cls.version = match
        cls.name = "docker-compose"
        cls.ident = match
        return cls

    def detect(self, engine=None):
        "Return the Engine class that match engine string"

        if not engine:
            log.info("Guessing best docker engine ...")
            obj = self.detect_docker_compose()
        else:

            if engine not in self.versions["docker-compose"]:
                versions = list(self.versions["docker-compose"].keys())
                log.warning(f"Please select engine one of: {versions}")
                raise error.DockerUnsupportedVersion(
                    f"Unknown docker-engine version: {engine}"
                )
            obj = self.versions["docker-compose"][engine]
        # if not result:
        #     raise error.DockerUnsupportedVersion(f"Can;t find docker-compose")

        log.debug(f"Detected docker-compose version: {obj.version}")

        return obj
