#!/usr/bin/env python3
"""Paasify CLI interface"""

# Run like this:
#   python3 python_cli.py -vvvv demo
# Author: mrjk

import os
import sys

from enum import Enum
from typing import List, Optional

import glob
import sh
import yaml
import json
import traceback
import re

from pprint import pprint
from pathlib import Path

import typer
import anyconfig
from cafram.utils import serialize, get_logger

import paasify.errors as error
from paasify.app2 import PaasifyApp

# from rich.console import Console
# from rich.syntax import Syntax

#import paasify.app as Paasify


#from paasify.app import DirectoryItem, Namespace
#from paasify.app2 import Project

#from paasify.app import App

# import os
# import os.path

# import logging
# log = logging.getLogger("paasify")

log = get_logger(logger_name="paasify")


class OutputFormat(str, Enum):
    yaml = "yaml"
    json = "json"
    toml = "toml"


cli_app = typer.Typer(
    help="Paasify, build your compose-files",
    no_args_is_help=True)



@cli_app.callback()
def main(
    ctx: typer.Context,
    verbose: int = typer.Option(0, "--verbose", "-v", count=True, min=0, max=5),

    working_dir: str = typer.Option(os.getcwd() , "-c", "--config",
        help="Path of paasify.yml configuration file.", 
        envvar="PAASIFY_PROJECT_DIR"),

    collections_dir: Path = typer.Option(f"{Path.home()}/.config/paasify/collections", "-l", "--collections_dir",
        help="Path of paasify collections directory.", 
        envvar="PAASIFY_COLLECTIONS_DIR"),

    ):
    """
    Manage users in the awesome CLI app.
    """

    # 50: Crit
    # 40: Err
    # 30: Warn
        # 25: Notice
    # 20: Info
        # 15: Exec
    # 10: Debug
        # 5: Trace
    # 0: Not set

    verbose = 30 - (verbose * 5)
    verbose = verbose if verbose > 0 else 0
    log.setLevel(level=verbose)

    # log.critical("SHOW CRITICAL")
    # log.error("SHOW ERROR")
    # log.warning("SHOW WARNING")
    log.notice("SHOW NOTICE")
    log.info("SHOW INFO")
    log.exec("SHOW EXEC")
    log.debug("SHOW DEBUG")
    log.trace("SHOW TRACE")


    # Init paasify
    app_conf = {
        "config": {
            "default_source": "default",
            "cwd": os.getcwd(),
            "working_dir": working_dir,
        }
    }

    paasify2 = PaasifyApp(payload=app_conf)

    ctx.obj = {
        "paasify2": paasify2,
    }




# Generic commands
# ==============================
@cli_app.command()
def info(
    ctx: typer.Context,
    ):
    """Show context infos"""
    psf = ctx.obj["paasify2"]

    psf.info(autoload=None)
    
    


@cli_app.command()
def ls(
    ctx: typer.Context,
    ):
    """List all stacks"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_stacks_list()

@cli_app.command()
def schema(
    ctx: typer.Context,
    format: OutputFormat = OutputFormat.json,

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show paasify config schema"""
    paasify = ctx.obj["paasify"]
    print(paasify.cmd_config_schema(format=format))


@cli_app.command()
def init(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None,
        help="Name of reference project to create",)
    ):
    """Create new project/namespace"""
    paasify = ctx.obj["paasify"]
    prj = paasify.init_project(name)

@cli_app.command()
def help(
    ctx: typer.Context,
    ):
    """Show this help message"""
    print (ctx.parent.get_help())


# Source commands
# ==============================
@cli_app.command()
def src_ls(
    ctx: typer.Context,
    ):
    """List sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_src_list()

@cli_app.command()
def src_install(
    ctx: typer.Context,
    ):
    """Install sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_src_install()

@cli_app.command()
def src_update(
    ctx: typer.Context,
    ):
    """Update sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_src_update()

@cli_app.command()
def src_tree(
    ctx: typer.Context,
    ):
    """Show source tree"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_src_tree()


# Stack commands
# ==============================
@cli_app.command()
def apply(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build and clily stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()

    log.notice("Rebuild docker-compose ...")
    prj.cmd_build(stack=stack)

    log.notice("Apply stack")
    prj.cmd_up(stack=stack)


@cli_app.command()
def recreate(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Stop, rebuild and create stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()

    #log.notice("Remove stacks")
    prj.cmd_down(stack=stack)

    #log.notice("Rebuild docker-compose ...")
    prj.cmd_build(stack=stack)

    #log.notice("Apply stack")
    prj.cmd_up(stack=stack)



@cli_app.command()
def build(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build docker-files"""

    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.cmd_stack_cmd("assemble", stacks=stack)
    #prj.cmd_stack_assemble(stack=stack)

    return 

    #sys.exit(1)

    print ("\n\n")
    # print ("PASSED: Dict")
    # pprint (paasify.__dict__)
    # print ("PASSED: SAerialized")
    # pprint (paasify.serialize())
    # print ("PASSED: Children")
    # print (serialize(paasify.get_children_conf(), fmt='yml'))
    # print ("PASSED: Config")
    # pprint (paasify.config.serialize())
    # print ("\n\n\n\n")

    # #sys.exit(1)
    # print ("\n\n\n\n")
    # print ("PRJ: Dict")
    # pprint (prj.__dict__)
    # pprint (prj.stacks.__dict__)


    #pprint (dir(prj))

    #prj.cmd_stack_assemble(stack=stack)

    # print ("Childs")
    # print (serialize(paasify.get_config(), fmt='yml'))
    # print (serialize(paasify.__dict__, fmt='json'))
    # print (serialize(paasify.project.stacks.__dict__, fmt='json'))

    sys.exit(0)

    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_build(stack=stack)


@cli_app.command()
def up(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Start docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_up(stack=stack)


@cli_app.command()
def down(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Stop docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_down(stack=stack)


@cli_app.command()
def ps(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show docker stack instances"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_ps(stack=stack)

@cli_app.command()
def logs(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show stack logs"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    prj.cmd_logs(stack=stack, follow=follow)


@cli_app.command()
def reset(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Reset presistent application volume data (destructive!)"""
    paasify = ctx.obj["paasify"]
    prj = paasify.load_project()
    raise Exception("Not implemented yet")






def app():
    "Actually start the app"

    try:
        cli_app()
    except Exception as err:
        err_type = err.__class__.__module__ + '.' + err.__class__.__name__
        
        if hasattr(err, 'paasify'):
            err_name = err.__class__.__name__
            if isinstance(err.advice, str):
                log.warn (err.advice)
            log.error (err)
            log.critical (f"Error {err.rc}: {err_name}")
            sys.exit(err.rc)

        elif err_type.startswith("yaml"):
            log.error (err)
            log.critical (f"While parsing YAML file: {err_type}")
            sys.exit(1)  

        # elif err_type.startswith("sh"):
        #     # pprint (dir(err))
        #     # pprint (err.__dict__)
        #     log.error(traceback.format_exc())
        #     msg = []
        #     if err.stdout:
        #         msg.extend(["stdout:", err.stdout])
        #     if err.stderr:
        #         msg.extend(["stderr:", err.stderr])
        #     if msg:
        #         log.error (msg)
        #     log.critical (f"Error '{err_type}' while executing command: {err.full_cmd}")
        #     sys.exit(1)  
        else:
            log.error(traceback.format_exc())
            log.error (err)
            log.critical (f"Paasify exited with a BUG! ({type(err)}, {err_type})")
            sys.exit(1)


if __name__ == "__main__":
    app()



