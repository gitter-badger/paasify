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

    _node_parent_kind = ["PaasifyStack"]

    version = None
    docker_file_exists = False
    docker_file_path = None
    arg_prefix = []

    conf_default = {
        "stack_name": None,
        "stack_path": None,
        "docker_file": "docker-compose.yml",
    }

    ident = "default"

    def node_hook_children(self):
        "Create stack context on start"

        # Get parents
        stack = self._node_parent
        # prj = stack.prj

        # Init object
        stack_name = stack.stack_name
        stack_path = stack.stack_path
        self.docker_file_path = os.path.join(stack_path, self.docker_file)

        # Pre build args
        self.arg_prefix = [
            "--project-name",
            f"{stack_name}",
            "--project-directory",
            f"{stack_path}",
        ]

    def node_hook_final(self):
        "Enable cli logging"
        self.set_logger("paasify.cli.engine")

    def require_stack(self):
        "Ensure stack context"

        if not self.stack_name:
            assert False, "Command not available for stacks!"

    def require_compose_file(self):
        "Raise an exception when compose file is absent"

        self.require_stack()

        if not os.path.isfile(self.docker_file_path):
            self.log.warning("Please build stack first")
            raise error.BuildStackFirstError("Docker file is not built yet !")

    def assemble(self, compose_files, env_file=None, env=None):
        "Generate docker-compose file"

        self.require_stack()

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

        self.require_compose_file()
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

        return out

    def down(self, **kwargs):
        "Stop containers"

        self.require_stack()
        cli_args = list(self.arg_prefix)
        cli_args = [
            "--project-name",
            self.stack_name,
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

        self.require_stack()
        sh_options = {}
        cli_args = [
            "--project-name",
            self.stack_name,
            "logs",
        ]
        if follow:
            cli_args.append("-f")
            sh_options["_fg"] = True

        out = _exec("docker-compose", cli_args, **sh_options)
        print(out)

    # pylint: disable=invalid-name
    def ps(self):
        "Return container processes"

        self.require_stack()
        cli_args = [
            "--project-name",
            self.stack_name,
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
