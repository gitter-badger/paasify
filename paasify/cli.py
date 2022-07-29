#!/usr/bin/env python3
"""Paasify CLI interface"""

# Run like this:
#   python3 python_cli.py -vvvv demo
# Author: mrjk

import typer
import os
import sys
#import logging
import yaml
import json

from pathlib import Path

from rich.console import Console
from rich.syntax import Syntax

import anyconfig
#import paasify.app as Paasify

import re
from pprint import pprint
#from paasify.app import DirectoryItem, Namespace
#from paasify.app2 import Project

from paasify.app import App

import os
import os.path
import glob
import sh

from enum import Enum
from typing import List, Optional


# import logging
# log = logging.getLogger("paasify")

from paasify.common import get_logger
log, log_level = get_logger(logger_name="paasify")


class OutputFormat(str, Enum):
    yaml = "yaml"
    json = "json"
    toml = "toml"


app = typer.Typer(
    help="Paasify, build your compose-files",
    no_args_is_help=True)



@app.callback()
def main(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, min=0, max=4),

    config_file: Path = typer.Option("paasify.yml", "-c", "--config",
        help="Path of paasify.yml configuration file.", 
        envvar="PAASIFY_CONFIG"),

    collections_dir: Path = typer.Option(f"{Path.home()}/.config/paasify/collections", "-l", "--collections_dir",
        help="Path of paasify collections directory.", 
        envvar="PAASIFY_COLLECTIONS_DIR"),

    ):
    """
    Manage users in the awesome CLI app.
    """

    log_lvl = 24 - (verbose * 5)
    log.setLevel(level=log_lvl)

    paasify = App(
        config_path=str(config_file.resolve()),
        collections_dir=str(collections_dir.resolve()),
    )

    # Prepare shared context
    ctx.obj = {
        "paasify": paasify,
    }


# Generic commands
@app.command()
def info(
    ctx: typer.Context,
    ):
    """Show context infos"""
    paasify = ctx.obj["paasify"]
    paasify.cmd_info()


@app.command()
def ls(
    ctx: typer.Context,
    ):
    """List all stacks"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_stacks_list()

# Source commands
@app.command()
def src_ls(
    ctx: typer.Context,
    ):
    """List sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_list()

@app.command()
def src_install(
    ctx: typer.Context,
    ):
    """Install sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_install()

@app.command()
def src_update(
    ctx: typer.Context,
    ):
    """Install and update sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_update()

@app.command()
def src_tree(
    ctx: typer.Context,
    ):
    """Install and update sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_tree()


# Stack commands

@app.command()
def apply(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build and apply stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()

    log.notice("Rebuild docker-compose ...")
    prj.cmd_build(stack=stack)

    log.notice("Apply stack")
    prj.cmd_up(stack=stack)


@app.command()
def recreate(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Stop, rebuild and create stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()

    #log.notice("Remove stacks")
    prj.cmd_down(stack=stack)

    #log.notice("Rebuild docker-compose ...")
    prj.cmd_build(stack=stack)

    #log.notice("Apply stack")
    prj.cmd_up(stack=stack)



@app.command()
def build(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build docker-files"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_build(stack=stack)


@app.command()
def up(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Start docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_up(stack=stack)


@app.command()
def down(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Stop docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_down(stack=stack)


@app.command()
def ps(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show docker stack instances"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_ps(stack=stack)

@app.command()
def logs(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show stack logs"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_logs(stack=stack, follow=follow)


@app.command()
def schema(
    ctx: typer.Context,
    format: OutputFormat = OutputFormat.json,

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show paasify config schema"""
    paasify = ctx.obj["paasify"]
    print(paasify.cmd_config_schema(format=format))




if __name__ == "__main__":
    
    #typer.run(CmdApp)
    app()




############################### EEEENNNNDDD OFFFF FILFFFFEEEE
# Legacy below



































# @app.command()
# def up(
#     ctx: typer.Context,
#     ):
#     """start"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('up')

# @app.command()
# def down(
#     ctx: typer.Context,
#     ):
#     """Down"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('down')

# @app.command()
# def apply(
#     ctx: typer.Context,
#     ):
#     """Assemble and start"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('assemble')
#     paasify.forward_stacks('up')

# @app.command()
# def restart(
#     ctx: typer.Context,
#     ):
#     """Assemble and restart"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('assemble')
#     paasify.forward_stacks('down')
#     paasify.forward_stacks('up')

# @app.command()
# def recreate(
#     ctx: typer.Context,
#     ):
#     """Assemble, rm and restart"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('assemble')
#     paasify.forward_stacks('down')
#     paasify.forward_stacks('rm')
#     paasify.forward_stacks('up')



# @app.command()
# def rm(
#     ctx: typer.Context,
#     ):
#     """Remove"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('down')
#     paasify.forward_stacks('rm')

# @app.command()
# def ps(
#     ctx: typer.Context,
#     ):
#     """Processes"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('ps')

# @app.command()
# def logs(
#     ctx: typer.Context,
#     ):
#     """Logs"""
#     paasify = ctx.obj["paasify"]
#     paasify.forward_stacks('logs')


# @app.command()
# def ls(
#     ctx: typer.Context,
#     ):
#     """List stacks"""
#     paasify = ctx.obj["paasify"]
#     for i in paasify.stacks:
#         print ( i.rel_path, i.get_tags())

# @app.command()
# def vars(
#     ctx: typer.Context,
#     ):
#     """List vars"""
#     paasify = ctx.obj["paasify"]

#     console = Console()
#     ret = {}
#     for i in paasify.stacks:
#         v = {
#                 #i.name: i.get_vars()
#                 'vars': i.get_vars()
#                 }
#         ret[i.name] = v

#     v = yaml.dump(ret, default_flow_style=False)
#     v = Syntax(v, lexer='YamlLexer')
#     console.print(f"Stack vars:")
#     console.print(v)

# @app.command()
# def dev(
#     ctx: typer.Context,
#     ):
#     """Debvelopment commands"""

#     # Init
#     file = ctx.obj["paasify"]["config"]
#     config = Project.find_config()

#     # Action
#     paasify = Project(config=config)
#     paasify.forward_stacks('up')







##### STABLE
#
#@app.command()
#def docker_build (
#    ctx: typer.Context,
#    ):
#    """Build docker compose files"""
#    
#    file = ctx.obj["paasify"]["config"]
#    print ("WIP")
#
#
#@app.command()
#def docker_start (
#    ctx: typer.Context,
#    ):
#    """Start stacks"""
#    
#
#    file = ctx.obj["paasify"]["config"]
#    p = DirectoryItem.namespace(config_file=file)
#    p.docker_start()
#
#    print ("Stack is started")
#
#
#@app.command()
#def docker_stop (
#    ctx: typer.Context,
#    ):
#    """Stop stacks"""
#    
#    file = ctx.obj["paasify"]["config"]
#    print ("WIP")
#
#@app.command()
#def docker_restart (
#    ctx: typer.Context,
#    ):
#    """Restart stacks"""
#    
#    file = ctx.obj["paasify"]["config"]
#    print ("WIP")
#
#
#@app.command()
#def config(
#    ctx: typer.Context,
#    ):
#    """Show project config"""
#    
#    file = ctx.obj["paasify"]["config"]
#    p = Namespace(config_file=file, is_root=True)
#    ret = p.config
#    print (anyconfig.dumps(ret, ac_parser="yaml"))
#
#
#@app.command()
#def list(
#    ctx: typer.Context,
#    ):
#    """Show stack list"""
#    
#    file = ctx.obj["paasify"]["config"]
#    p = Namespace(config_file=file, is_root=True)
#    ret = p.read_stacks_order()
#    print (anyconfig.dumps(ret, ac_parser="yaml"))
#  


# class Paasify():


#     def __init__(self, path_root="."):

#         self.path_root = path_root

#         subprojects = self.guess_subprojects(path_root)
#         self.prjs = self.find_subpj_children(subprojects)


#     def find_subpj_children(self, prjs):

#         print ("helloo")

#         for prj_name, prj_def in prjs.items():

#             # Load docker compose
#             file = prj_def["path"]
#             ret = anyconfig.load(file, ac_parser="yaml")

#             #prjs[prj_name]["compose"] = ret

#             # SAve services
#             prjs[prj_name]["services"] = list(ret.get("services").keys())



#             pattern = re.compile('[^\$]?\${([A-Za-z_][A-Za-z0-9_]*)}')
#             pattern2 = re.compile('[^\$]?\$([A-Za-z_][A-Za-z0-9_]*)')

#             envars = []
#             for line in open(file):
#                 #print ("LINE ", line)
#                 line = line.lstrip('\#')

#                 try:
#                     match = re.search(pattern, line).groups()
#                     envars.append(match)
#                 except AttributeError:
#                     pass
#                 try:
#                     match = re.search(pattern2, line).groups()
#                     envars.append(match)
#                 except AttributeError:
#                     pass


#             prjs[prj_name]["env"] = list(set(envars))



#         return prjs

            


#     def guess_subprojects(self, path=None):

#         path = path or self.path_root
#         ret = {}
#         index = 0
#         for dirpath, dirnames, filenames in os.walk(path):
#             for filename in [f for f in filenames if f.startswith("docker-compose.y")]:
#                 prj_path = os.path.join(dirpath, filename)
#                 prj_name = dirpath[2:]
#                 ret[prj_name] = {
#                     "path": prj_path,
#                     "project": prj_name,
#                     "compose": filename ,
#                     "index": index ,
#                     }
#                 index = index + 1
#         return ret

