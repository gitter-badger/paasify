#!/usr/bin/env python3
"""Paasify CLI interface

This API provides a similar experience as the CLI, but in Python.

Example:
``` py title="test.py"
from paasify.cli import app

paasify = app()
paasify.info()
paasify.apply()
```

"""

# pylint: disable=logging-fstring-interpolation

# Run like this:
#   python3 python_cli.py -vvvv demo
# Author: mrjk

import os
import sys

import traceback

from typing import Optional


from pprint import pprint
from pathlib import Path

import typer
from cafram.utils import get_logger


import paasify.errors as error
from paasify.version import __version__
from paasify.common import OutputFormat
from paasify.app2 import PaasifyApp

# from rich.console import Console
# from rich.syntax import Syntax

# import paasify.app as Paasify


# from paasify.app import DirectoryItem, Namespace
# from paasify.app2 import Project

# from paasify.app import App

# import os
# import os.path

# import logging
# log = logging.getLogger("paasify")

log = get_logger(logger_name="paasify.cli")


cli_app = typer.Typer(
    help="Paasify, build your compose-files",
    invoke_without_command=True,
    no_args_is_help=True,
)


@cli_app.callback()
def main(
    ctx: typer.Context,
    verbose: int = typer.Option(1, "--verbose", "-v", count=True, min=0, max=5),
    working_dir: str = typer.Option(
        os.getcwd(),
        "-c",
        "--config",
        help="Path of paasify.yml configuration file.",
        envvar="PAASIFY_PROJECT_DIR",
    ),
    collections_dir: Path = typer.Option(
        f"{Path.home()}/.config/paasify/collections",
        "-l",
        "--collections_dir",
        help="Path of paasify collections directory.",
        envvar="PAASIFY_COLLECTIONS_DIR",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Show version info",
    ),
):
    """
    Prepare Paasify App instance.
    """

    # 50: Crit
    # 40: Err
    # 30: Warn
    #   25: Notice
    # 20: Info
    #   15: Exec
    # 10: Debug
    #   5: Trace
    # 0: Not set

    verbose = 30 - (verbose * 5)
    verbose = verbose if verbose > 0 else 0
    log.setLevel(level=verbose)

    # log.critical("SHOW CRITICAL")
    # log.error("SHOW ERROR")
    # log.warning("SHOW WARNING")

    # log.notice("SHOW NOTICE")
    # log.info("SHOW INFO")
    # log.exec("SHOW EXEC")
    # log.debug("SHOW DEBUG")
    # log.trace("SHOW TRACE")

    # Init paasify
    app_conf = {
        "config": {
            "default_source": "default",
            "cwd": os.getcwd(),
            "working_dir": working_dir,
            # "collections_dir": collections_dir,
        }
    }

    if version:
        print(__version__)
        return

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
def explain(
    ctx: typer.Context,
    mode: Optional[str] = typer.Option(
        None,
        help="If a path, generate the doc, if none, report stdout",
    ),
):
    """Show project plugins"""
    psf = ctx.obj["paasify2"]
    prj = psf.load_project()
    prj.stacks.cmd_stack_explain(mode=mode)


@cli_app.command()
def ls(
    ctx: typer.Context,
):
    """List all stacks"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_ls()


# pylint: disable=redefined-builtin
@cli_app.command()
def schema(
    ctx: typer.Context,
    format: OutputFormat = OutputFormat.yaml,
    target: Optional[str] = typer.Argument(
        None,
        help="Show segment only: app, project, stack",
    ),
    mode: Optional[str] = typer.Option(
        None,
        help="Determine output format: cli,standalone,doc",
    ),
    output: Optional[str] = typer.Option(
        None,
        help="Determine output directory",
    ),
):
    """Show paasify configurations schema format"""
    psf = ctx.obj["paasify2"]
    out = psf.cmd_config_schema(format=format, target=target, mode=mode, output=output)
    print(out)


@cli_app.command()
def init(
    ctx: typer.Context,
    name: Optional[str] = typer.Argument(
        None,
        help="Name of reference project to create",
    ),
):
    """Create new project/namespace"""
    # TODO: To fix
    paasify = ctx.obj["paasify"]
    paasify.init_project(name)


@cli_app.command()
def help(
    ctx: typer.Context,
):
    """Show this help message"""
    print(ctx.parent.get_help())


# Source commands
# ==============================
# TODO: To fix


@cli_app.command()
def src_ls(
    ctx: typer.Context,
):
    """List sources"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.cmd_src_list()


@cli_app.command()
def src_install(
    ctx: typer.Context,
):
    """Install sources"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.cmd_src_install()


@cli_app.command()
def src_update(
    ctx: typer.Context,
):
    """Update sources"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.cmd_src_update()


@cli_app.command()
def src_tree(
    ctx: typer.Context,
):
    """Show source tree"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.cmd_src_tree()


# Stack commands
# ==============================
@cli_app.command()
def apply(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Build and apply stack"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()

    log.notice("Rebuild docker-compose ...")
    prj.stacks.cmd_stack_assemble(stacks=stack)

    log.notice("Apply stack")
    prj.stacks.cmd_stack_up(stacks=stack)


@cli_app.command()
def recreate(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Stop, rebuild and create stack"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()

    log.notice("Remove stacks")
    prj.stacks.cmd_stack_down(stacks=stack)

    log.notice("Rebuild docker-compose ...")
    prj.stacks.cmd_stack_assemble(stacks=stack)

    log.notice("Apply stack")
    prj.stacks.cmd_stack_up(stacks=stack)


@cli_app.command()
def build(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Build docker-files"""

    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_assemble(stacks=stack)

    return


@cli_app.command()
def up(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Start docker stack"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_up(stacks=stack)


@cli_app.command()
def down(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Stop docker stack"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_down(stacks=stack)


@cli_app.command()
def ps(
    ctx: typer.Context,
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Show docker stack instances"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_ps(stacks=stack)


@cli_app.command()
def logs(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Show stack logs"""
    paasify = ctx.obj["paasify2"]
    prj = paasify.load_project()
    prj.stacks.cmd_stack_logs(stacks=stack, follow=follow)


@cli_app.command()
def reset(
    ctx: typer.Context,
    follow: bool = typer.Option(False, "--follow", "-f"),
    stack: Optional[str] = typer.Argument(
        None,
        help="Stack to target, current cirectory or all",
    ),
):
    """Reset presistent application volume data (destructive!)"""
    paasify = ctx.obj["paasify2"]

# Top levels helpers
# ==============================

def clean_terminate(err):
    "Terminate nicely the program depending the exception"

    oserrors = [
            PermissionError, FileExistsError, 
            FileNotFoundError, InterruptedError,
            IsADirectoryError, NotADirectoryError, TimeoutError
        ]


    # Choose dead end way
    if isinstance(err, error.PaasifyError):
        err_name = err.__class__.__name__
        if isinstance(err.advice, str):
            log.warning(err.advice)

        log.error(err)
        log.critical(f"Paasify exited with error {err.rc}: {err_name}")
        sys.exit(err.rc)

    elif err.__class__ in oserrors:

        # Decode OS errors
        # errno = os.strerror(err.errno)
        # errint = str(err.errno)

        log.critical(f"Paasify exited with OS error: {err}")
        sys.exit(err.errno)


def app():
    "Return a Paasify App instance"

    try:
        return cli_app()

    # pylint: disable=broad-except
    except Exception as err:

        clean_terminate(err)

        # Developper catchall
        log.critical ("Uncatched error happened, this may be a bug!")
        log.error(traceback.format_exc())
        sys.exit(1)





        #assert False, "Bad app termination!!! => {err}"

        #err_type = err.__class__.__module__ + "." + err.__class__.__name__


        # # allowed_except = [
        # #     PermissionError, FileExistsError, 
        # #     FileNotFoundError, InterruptedError,
        # #     IsADirectoryError, NotADirectoryError, TimeoutError
        # # ]

        # # Remap exceptions 
        # if not isinstance(err, error.PaasifyError):
        

        #     if hasattr(err, 'errno'):
        #         # Remap OS errors

        #         raise error.OSError("Got System exception: {err}") from err


        # if isinstance(err, error.PaasifyError):

        # #if hasattr(err, "paasify2"):
        #     err_name = err.__class__.__name__
        #     if isinstance(err.advice, str):
        #         log.warning(err.advice)
        #     log.error(err)
        #     log.critical(f"OK: Error {err.rc}: {err_name}")
        #     sys.exit(err.rc)

        # # elif hasattr(err, 'errno'):
        # # #elif err.__class__ in allowed_except:

        # #     errno = os.strerror(err.errno)
        # #     errint = str(err.errno)

        # #     pprint (err.__dict__)
        # #     log.critical(f"Error {errint} ==> {errno}")
        # #     sys.exit(err.errno)

        # elif err_type.startswith("yaml"):
        #     log.error(err)
        #     log.critical(f"While parsing YAML file: {err_type}")
        #     sys.exit(1)

        # # elif err_type.startswith("sh"):
        # #     # pprint (dir(err))
        # #     # pprint (err.__dict__)
        # #     log.error(traceback.format_exc())
        # #     msg = []
        # #     if err.stdout:
        # #         msg.extend(["stdout:", err.stdout])
        # #     if err.stderr:
        # #         msg.extend(["stderr:", err.stderr])
        # #     if msg:
        # #         log.error (msg)
        # #     log.critical (f"Error '{err_type}' while executing command: {err.full_cmd}")
        # #     sys.exit(1)
        # else:
        #     log.error(traceback.format_exc())
        #     log.error(err)
        #     log.critical(f"Paasify exited with a BUG! ({type(err)}, {err_type})")
        #     sys.exit(1)


if __name__ == "__main__":
    app()
