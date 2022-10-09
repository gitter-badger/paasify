#!/usr/bin/env pytest

import sys
import os
import unittest
from pprint import pprint
import pytest
import logging


from typer.testing import CliRunner
from paasify.cli import cli_app
from paasify.app2 import PaasifyApp
import paasify.errors as error




# Test cli
# ------------------------
cwd = os.getcwd()
runner = CliRunner()

def test_cli_info_without_project():
    result = runner.invoke(cli_app, ["-vvvvv", "--config", cwd + "/tests/examples", "info"])
    out = result.stdout_bytes.decode("utf-8")
    print (out)
    assert result.exit_code != 0
    #assert "Impossible to find" in out

def test_cli_info_with_project():
    result = runner.invoke(cli_app, ["--config", cwd + "/tests/examples/minimal", "info"])
    out = result.stdout_bytes.decode("utf-8")
    assert result.exit_code == 0
    




# Test stacks
# ------------------------

def test_stacks_resolution(data_regression):
    "Ensure name, app path and direct string config works correctly"

    # Load project
    app_conf = {
        "config": {
            "root_hint": cwd + "/tests/examples/unit_stacks_idents",
        }
    }
    psf = PaasifyApp(payload=app_conf)
    prj = psf.load_project()

    results = []
    for stack in prj.stacks.get_children():
        result = {
            "stack_config": stack.serialize(mode='raw'),
            "stack_name": stack.stack_name,
            # TOFIX: THIS
            "stack_dir": stack.stack_dir,
            "stack_app": stack.app.serialize() if stack.app else None,
        }
        results.append(result)
        
    data_regression.check(results)


def test_stacks_resolution_dupl(data_regression):
    "Ensure name, app path and direct string config works correctly"

    # Load project
    app_conf = {
        "config": {
            "root_hint": cwd + "/tests/examples/unit_stacks_idents_dup_fail",
        }
    }
    psf = PaasifyApp(payload=app_conf)
    
    # Test the load fails
    try:
        psf.load_project()
        assert False, "Duplicate configuration should have raised an error!"
    except error.ProjectInvalidConfig:
        pass



# Main run
# ------------------------

if __name__ == "__main__":
    
    pytest.main([__file__])


    
    #unittest.main()


