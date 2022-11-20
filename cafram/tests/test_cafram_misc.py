import sys
import unittest
from pprint import pprint
import pytest


from cafram.nodes import *

# from cafram.nodes_conf import *


# def test_attribute_class():
#     "Should return empty things"

#     assert str(unset) == "<cafram.unset>"
#     assert str(drop) == "<cafram.drop>"


if __name__ == "__main__":
    retcode = pytest.main([__file__])
