import sys
import unittest
from pprint import pprint
import pytest
import logging
import os

import cafram

from cafram.base import MissingIdent, InvalidSyntax
from cafram.nodes import (
    Base,
    NodeMap,
    map_node_class,
    NodeDict,
    NodeList,
    NotExpectedType,
    NodeMapEnv,
    expand_envar_syntax,
)

# from cafram.nodes_conf import *

log = logging.getLogger()


# Testing bases
# =====================================


class Test01_ConfVal(unittest.TestCase):
    "Test base objects"

    def test_ident_is_correctly_set(self):
        """
        Test class with ident
        """

        node = Base(ident="My App")
        self.assertEqual(node.ident, "My App")

    def test_fail_without_ident_arg(self):
        """
        Test if class fails if not named with ident
        """

        try:
            Base()
        except MissingIdent:
            pass
        except:
            self.assertFalse(True)

    def test_parents(self):
        """
        Ensure the _node_parent relationship work as expected
        """

        node = NodeMap(ident="TestInstance")
        self.assertEqual(node._node_parent, node._node_root)
        self.assertNotEqual(node._node_parent, None)
        self.assertNotEqual(node._node_root, None)

        node = NodeMap(ident="TestInstance", parent=None)
        self.assertEqual(node._node_parent, node._node_root)
        self.assertNotEqual(node._node_parent, None)
        self.assertNotEqual(node._node_root, None)

        # Todo: Test with inheritance
        # node = CustomConfigAttrIdent(parent="MyParent")
        # pprint (node.__dict__)
        # self.assertEqual(node._node_parent, node._node_root)
        # self.assertEqual(node._node_parent, None)

    def test_dump_method(self):
        """
        Ensure the dump method works correctly
        """

        node = NodeMap(ident="TestInstance")
        node.dump()


# ConfMixed Testing
# ================================

payload_keydict = {
    "subkey2": "val2",
    "subkey3": 1234,
    "subkey4": None,
}
payload_keylist = ["item1", "item2"]
payload_value = "MyValue"
payload = {
    "keyVal": payload_value,
    "keyDict": payload_keydict,
    "keyList": payload_keylist,
}


@pytest.fixture(scope="function")
def node_inst(request):

    # Prepare class according payload
    payload = None
    cls = NodeMap
    if hasattr(request, "param"):
        params = request.param
        payload = request.param

        cls = map_node_class(payload)
        if isinstance(params, tuple):
            payload = params[0]
            cls = params[1] if len(params) > 1 else map_node_class(payload)

    print("Create new obj:", cls, payload)

    class MyConfig(cls):
        ident = "ConfigTest"

        def node_hook_conf(self):

            # Assert children are not set
            assert not self._nodes

        def node_hook_children(self):

            # Ensure nodes is correct type if dict or list
            if isinstance(self, (NodeList, NodeDict)):
                assert isinstance(self._nodes, type(self.__class__._nodes))

    # Create instance
    inst = MyConfig(ident=f"TestInstance-{cls}", payload=payload)
    return inst


# Simple tests
# ------------------------


@pytest.mark.parametrize(
    "node_inst",
    [
        (payload_keydict),
        (payload_keylist),
        (payload_value),
        (payload),
    ],
    indirect=["node_inst"],
)
def test_is_root_method(node_inst):
    "All instances should be root"
    assert node_inst.is_root() == True


@pytest.mark.parametrize(
    "node_inst",
    [
        (payload_keydict),
        (payload_keylist),
        (payload_value),
        (payload),
    ],
    indirect=["node_inst"],
)
def test_get_parent_method(node_inst):
    "Parent should be self"
    assert node_inst.get_parent() == node_inst


@pytest.mark.parametrize(
    "node_inst",
    [
        (payload_keydict),
        (payload_keylist),
        (payload_value),
        (payload),
    ],
    indirect=["node_inst"],
)
def test_get_parent_root_method(node_inst):
    "Should return empty things"
    assert node_inst.get_parent_root() == node_inst


@pytest.mark.parametrize(
    "node_inst",
    [
        (payload_keydict),
        (payload_keylist),
        (payload_value),
        (payload),
    ],
    indirect=["node_inst"],
)
def test_get_parents_method(node_inst):
    "Should return empty things"

    assert node_inst.get_parents() == []


# Data tests
# ------------------------


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, payload_keydict),
        (payload_keylist, payload_keylist),
        (payload_value, payload_value),
        ((payload, NodeDict), payload),
    ],
    indirect=["node_inst"],
)
def test_node_get_value_method(node_inst, result):
    pprint(node_inst.__dict__)
    assert node_inst.get_value() == result


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, {}),
        (payload_keylist, []),
        (payload_value, None),
        ((payload, NodeDict), {}),
    ],
    indirect=["node_inst"],
)
def test_get_children_method(node_inst, result):
    "Should return empty things"
    assert node_inst.get_children() == result


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, payload_keydict),
        (payload_keylist, payload_keylist),
        (payload_value, payload_value),
        (payload, payload),
    ],
    indirect=["node_inst"],
)
def test_get_value_method(node_inst, result):
    assert node_inst.get_value() == result


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, payload_keydict),
        (payload_keylist, payload_keylist),
        (payload_value, payload_value),
        (payload, payload),
    ],
    indirect=["node_inst"],
)
def test_serialize(node_inst, result):
    assert node_inst.serialize() == result


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, payload_keydict),
        (payload_keylist, payload_keylist),
        (payload_value, payload_value),
        (payload, payload),
    ],
    indirect=["node_inst"],
)
def test_deserialize_method(node_inst, result):
    node_inst.deserialize(result)
    assert node_inst.serialize() == result


@pytest.mark.parametrize(
    "node_inst,result",
    [
        (payload_keydict, payload_keydict),
        (payload_keylist, payload_keylist),
        (payload_value, payload_value),
        (payload, payload),
    ],
    indirect=["node_inst"],
)
def test_serialize_method(node_inst, result):
    assert node_inst.serialize() == result


# Test NodeList
# ------------------------


payload_list_str = [
    "string1",
    "string2",
    "string3",
]
payload_list_int = [123, 456, 789]
payload_list_bool = [True, False, True, False]
payload_list_mixed_ko1 = [
    123,
    False,
    "string",
]
payload_list_mixed_ko2 = [
    "string",
    123,
    False,
]


class ConfigListTester(NodeList):

    ident = "ListTester"


# @pytest.mark.parametrize(
#     "node_inst,result",
#     [
#         ((payload, ConfigListTester), payload),
#     ],
#     indirect=["node_inst"],
# )
# def test_list_default_class(node_inst, result):
#     "Ensure first element of the list determine the class"

#     node_inst.deserialize(payload_list_str)
#     pprint (node_inst.__dict__)

#     assert False, "WIPP"

# @pytest.mark.parametrize(
#     "node_inst,result",
#     [
#         ((payload, ConfigListTester), payload),
#     ],
#     indirect=["node_inst"],
# )
def test_list_fail_on_mixed_class(node_inst):
    "Ensure this fail when mixed type elements are present in a list"

    node_inst = ConfigListTester(autoconf=-1)

    for payload in [payload_list_mixed_ko1, payload_list_mixed_ko2]:
        try:
            node_inst.deserialize(payload)
            pprint(node_inst.__dict__)
            assert False, "This test should have failed"
        except NotExpectedType:
            pass

    # assert False, "WIPPPP"


# Test NodeMapEnv
# ------------------------


class ConfigEnvMock(NodeMapEnv):

    conf_default = payload


@pytest.mark.parametrize(
    "node_inst,result",
    [
        ((payload, ConfigEnvMock), payload),
    ],
    indirect=["node_inst"],
)
def test_get_env(node_inst, result, monkeypatch):
    "Test if"

    # Prepare environment vars
    name = f"{node_inst.conf_env_prefix or node_inst.kind}".upper()
    env_loop = (
        ("keyVal", "test123", "test123"),
        (
            "keyDict",
            "subkey1=val1,subkey2=val2",
            {"subkey1": "val1", "subkey2": "val2"},
        ),
        ("keyList", "test123", ["test123"]),
    )

    # Mokey patch environment vars
    for env_def in env_loop:
        key = env_def[0]
        val = env_def[1]
        key = f"{name}_{key}".upper()
        monkeypatch.setenv(key, val)

    # Load env vars
    node_inst.deserialize(payload)

    # Check env vars are correctly parsed
    node_conf = node_inst.get_value()
    for env_def in env_loop:
        key = env_def[0]
        val = env_def[1]
        result = env_def[2]
        assert node_conf[key] == result, f"Got: {node_conf[key]} != {val}"


# Test unset/drop attributes
# ------------------------


payload_none = {
    "keyVal": None,
    "keyDict": None,
    "keyList": None,
}
payload_empty = {
    "keyVal": "",
    "keyDict": {},
    "keyList": [],
}

###


class ConfigDropMock(NodeMapEnv):

    conf_children = [
        {
            "key": "keyDict",
            "action": "drop",
        },
        {
            "key": "keyList",
            "action": "drop",
        },
        {
            "key": "keyVal",
            "action": "drop",
        },
    ]


@pytest.mark.parametrize(
    "node_inst,result",
    [
        ((payload_none, ConfigDropMock), {}),
        ((payload_empty, ConfigDropMock), {}),
    ],
    indirect=["node_inst"],
)
def test_action_drop(node_inst, result, monkeypatch):
    "Ensure drop value are absent"

    pprint(result)
    pprint(node_inst.__dict__)
    assert node_inst.get_children() == {}
    assert node_inst.get_value() == {}


###


class ConfigUnsetMock(NodeMapEnv):

    conf_children = [
        {
            "key": "keyDict",
            "action": "unset",
            "cls": dict,
        },
        {
            "key": "keyList",
            "action": "unset",
            "cls": list,
        },
        {
            "key": "keyVal",
            "action": "unset",
            "cls": str,
        },
    ]


@pytest.mark.parametrize(
    "node_inst,result",
    [
        ((payload_empty, ConfigUnsetMock), payload_none),
        ((payload_none, ConfigUnsetMock), payload_none),
    ],
    indirect=["node_inst"],
)
def test_action_unset(node_inst, result, monkeypatch):
    "Ensure unset value are set to None"

    pprint(result)
    pprint(node_inst.__dict__)
    pprint(node_inst.get_value())
    assert node_inst.get_children() == {}
    assert node_inst.get_value() == result
    # assert False


# Test other functions
# ------------------------


@pytest.mark.parametrize(
    "payload,cls,expected",
    [
        (
            "key1=val1,key2=True,key3=123",
            dict,
            {"key1": "val1", "key2": "True", "key3": "123"},
        ),
        ("val1,True,123", list, ["val1", "True", "123"]),
        # Other edge cases
        ("val1,True,123", None, "val1,True,123"),
        (
            {"key1": "val1", "key2": "True", "key3": "123"},
            dict,
            {"key1": "val1", "key2": "True", "key3": "123"},
        ),
        (["val1", "True", "123"], list, ["val1", "True", "123"]),
    ],
)
def test_expand_envar_syntax(payload, cls, expected):

    result = expand_envar_syntax(payload, cls)
    assert expected == result


def test_expand_envar_syntax_invalid_syntax():

    payload = "key3_missing_equal,key1=val1,"

    try:
        expand_envar_syntax(payload, dict)
        assert False, f"This test should have failed because of missing '='"
    except InvalidSyntax:
        pass


# Main run
# ------------------------

if __name__ == "__main__":
    retcode = pytest.main([__file__])
