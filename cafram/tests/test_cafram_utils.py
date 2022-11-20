# import sys
# import unittest
from pprint import pprint
import pytest

from cafram.utils import get_logger, serialize, duplicates


def test_get_logger():
    "Test get_logger wrapper works correctly"

    logger = get_logger(logger_name="test_logger", verbose=5)
    assert logger.name == "test_logger"
    assert logger.level == 20


def test_serialize_json(data_regression):
    "Test serialize in json"

    payload = {
        "k1": "val1",
        "k2": ["val1"],
        "k3": {"k4": "val1"},
    }
    result = serialize(payload)
    data_regression.check(result)


def test_serialize_yaml(data_regression):
    "Test serialize in yaml"

    payload = {
        "k1": "val1",
        "k2": ["val1"],
        "k3": {"k4": "val1"},
    }
    result = serialize(payload, fmt="yaml")
    data_regression.check(result)


def test_duplicates(data_regression):

    payload = ["item1", "item2", "item3", "item1"]
    result = duplicates(payload)
    assert result == ["item1"]


if __name__ == "__main__":
    retcode = pytest.main([__file__])
