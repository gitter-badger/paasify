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
import traceback

from pathlib import Path

# from rich.console import Console
# from rich.syntax import Syntax

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


cli = typer.Typer(
    help="Paasify, build your compose-files",
    no_args_is_help=True)



@cli.callback()
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

    # collections_dirs: list(Path) = typer.Option(f"{Path.home()}/.config/paasify/collections", "-l", "--collections_dir",
    #     help="Path of paasify collections directory.", 
    #     envvar="PAASIFY_COLLECTIONS_DIR"),

    # ):
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
# ==============================
@cli.command()
def info(
    ctx: typer.Context,
    ):
    """Show context infos"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_info()


@cli.command()
def ls(
    ctx: typer.Context,
    ):
    """List all stacks"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_stacks_list()

@cli.command()
def schema(
    ctx: typer.Context,
    format: OutputFormat = OutputFormat.json,

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show paasify config schema"""
    paasify = ctx.obj["paasify"]
    print(paasify.cmd_config_schema(format=format))


@cli.command()
def init(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(None,
        help="Name of reference project to create",)
    ):
    """Create new project/namespace"""
    paasify = ctx.obj["paasify"]
    prj = paasify.init_project(name)

# Source commands
# ==============================
@cli.command()
def src_ls(
    ctx: typer.Context,
    ):
    """List sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_list()

@cli.command()
def src_install(
    ctx: typer.Context,
    ):
    """Install sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_install()

@cli.command()
def src_update(
    ctx: typer.Context,
    ):
    """Update sources"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_update()

@cli.command()
def src_tree(
    ctx: typer.Context,
    ):
    """Show source tree"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_src_tree()


# Stack commands
# ==============================
@cli.command()
def apply(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build and clily stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()

    log.notice("Rebuild docker-compose ...")
    prj.cmd_build(stack=stack)

    log.notice("Apply stack")
    prj.cmd_up(stack=stack)


@cli.command()
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



@cli.command()
def build(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Build docker-files"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_build(stack=stack)


@cli.command()
def up(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Start docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_up(stack=stack)


@cli.command()
def down(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Stop docker stack"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_down(stack=stack)


@cli.command()
def ps(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Show docker stack instances"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    prj.cmd_ps(stack=stack)

@cli.command()
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


@cli.command()
def reset(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),

    stack: Optional[str] = typer.Argument(None,
        help="Stack to target, current cirectory or all",)
    ):
    """Reset presistent application volume data (destructive!)"""
    paasify = ctx.obj["paasify"]
    prj = paasify.get_project()
    raise Exception("Not implemented yet")






def app():
    "Actually start the app"

    try:
        cli()
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

        elif err_type.startswith("sh"):
            log.error (err)
            log.critical (f"While executing command: {err_type}")
            sys.exit(1)  
        else:
            log.error(traceback.format_exc())
            log.error (err)
            log.critical (f"Paasify exited with a BUG! ({type(err)}, {err_type})")
            sys.exit(128)


if __name__ == "__main__":
    app()



