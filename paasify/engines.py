import os
import sys
import re
import logging
import json
import sh
from pprint import pprint

from paasify.common import _exec, cast_docker_compose
import paasify.errors as error
from paasify.class_model import ClassClassifier


log = logging.getLogger(__name__)


def bin2utf8(obj):
    if hasattr(obj, "stdout"):
        obj.txtout = obj.stdout.decode("utf-8").rstrip('\n')
    if hasattr(obj, "stderr"):
        obj.txterr = obj.stderr.decode("utf-8").rstrip('\n')
    return obj



class EngineCompose(ClassClassifier):

    versions = {
            'docker': {
                    '20.10.17': {},
                },
            'docker-compose': {
                    '1.6.1': {},
                    '1.29.2': {},
                },
            'podman-compose': {},
            }

    def _init(self, docker_file='docker-compose.run.yml'):

        self.engine = 'docker-compose'

        self.arg_prefix = [
            "--project-name", f"{self.parent.project_name}",
            "--project-directory", f"{self.parent.project_dir}",
        ]
        self.docker_file_path = os.path.join(self.parent.project_dir, docker_file)

        #self.engine = 'docker'
        #self.engine = 'podman-compose'

        # Check here if support for with versions:
        # docker-compose (legacy) (support all)
        # docker compose (new) (support docker only)
        # podman compose (new) (support podman only)
        pass

    def assemble(self, compose_files, env_file=None, env=None):

        cli_args = [
          #  "compose", 
            "--project-name", f"{self.parent.project_name}",
            "--project-directory", f"{self.parent.project_dir}",
        ]
        if env_file:
            cli_args.extend(["--env-file", env_file]) 
        for file in compose_files:
            cli_args.extend(['--file', file])
        cli_args.extend([
            "config", 
            # "--no-interpolate",
            # "--no-normalize",
        ])

        env_string = env or {}
        env_string = { k: cast_docker_compose(v) for k, v in env.items() if v is not None }

        result = _exec("docker-compose", cli_args, _out=None, _env=env_string)
        bin2utf8(result)
        return result

    def up(self, **kwargs):
        cli_args = list(self.arg_prefix)
        cli_args = [
            "--file", self.docker_file_path,
            "up",
            "--detach",
        ]
        out = _exec("docker-compose", cli_args, **kwargs)
        if out:
            out = bin2utf8(out)
            log.notice(out.txtout)

    def down(self, **kwargs):
        cli_args = list(self.arg_prefix)
        cli_args = [
            "--file", self.docker_file_path,
            "down",
            "--remove-orphans",
        ]

        try:
            out = _exec("docker-compose", cli_args, **kwargs)
            if out:
                bin2utf8(out)
                log.notice(out.txtout)
        except sh.ErrorReturnCode_1 as err:
            bin2utf8(err)

            # This is U.G.L.Y
            if not 'has active endpoints' in err.txterr:
                raise error.DockerCommandFailed(f"{err.txterr}")


    def logs(self, follow=False):
        sh_options = {}
        cli_args = [
            "--file", self.docker_file_path,
            "logs",
        ]
        if follow:
            cli_args.append("-f")
            sh_options["_fg"]=True

        _exec("docker-compose", cli_args, **sh_options)


    def ps(self):
        cli_args = [
            "--file", self.docker_file_path,
            "ps",
            "--all",
            "--format", "json",
        ]

        result = _exec("docker-compose", cli_args, _out=None)
        bin2utf8(result)

        # Report output from json
        stdout = result.txtout
        payload = json.loads(stdout)
        for svc in payload:

            # Get and filter interesting ports
            published = svc["Publishers"] or []
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
    





# class EngineDocker(ClassClassifier):

#     versions = {
#             'docker': {
#                     '20.10.17': {},
#                 },
#             'podman': {},
#             }

#     def _init(self):
#         self.engine = 'docker'
#         #self.engine = 'docker-swarm'
#         #self.engine = 'podman'
#         pass
#         # Check here if:
#         # simple docker
#         # swarm docker
#         # podman


#     def up(self):



class EngineJsonnet(ClassClassifier):
    pass

class ContainerEngine(ClassClassifier):


    def __init__(self, project_dir=None, project_name=None):

        self.project_dir = project_dir
        self.project_name = project_name

        # DEPRECATED self.cont_engine = EngineDocker(self)
        self.compose_engine = EngineCompose(self)
        self.jsonnet_engine = EngineJsonnet(self)

    def assemble(self, compose_files, **kwargs):
        return self.compose_engine.assemble(compose_files, **kwargs)

    def up(self, **kwargs):
        return self.compose_engine.up(**kwargs)

    def down(self, **kwargs):
        return self.compose_engine.down(**kwargs)

    def logs(self, **kwargs):
        return self.compose_engine.logs(**kwargs)
    def ps(self, **kwargs):
        return self.compose_engine.ps(**kwargs)

