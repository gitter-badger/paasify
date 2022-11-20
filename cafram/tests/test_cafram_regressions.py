# pylint: disable=no-member


from pprint import pprint
import pytest
import logging

from cafram.nodes import NodeAuto

log = logging.getLogger()


# Testing regressions
# =====================================


payload_regression = {
    # Simple nodeval
    "_0_values": {
        "_0_key_str": "string",
        "_0_key_bool": True,
        "_0_key_int": 1234,
        "_0_key_null": None,
    },
    # Dict
    "_1_dict_empty": {},
    "_2_dict_nested": {
        "_0_dict": {"str": "string_value1"},
        "_1_dict": {"str": "string_value2"},
        "_2_dict": {"str": "string_value3"},
        "_3_dict": {"str": "string_value4"},
        "_4_dict_empty": {},
    },
    "_3_dict_mixed": {
        "_0_key_str": "string",
        "_1_key_bool": True,
        "_2_key_int": 1234,
        "_3_key_null": None,
        "_4_key_dict_empty": {},
        "_5_key_dict_misc": {
            "_0_key_str": "string",
            "_1_key_bool": True,
            "_2_key_int": 1234,
            "_3_key_null": None,
            "_4_key_dict_nested": {
                "_4_key_dict_nested": {
                    "_4_key_dict_nested": {"nest_key": "nested_value"}
                }
            },
        },
    },
    # List
    "_4_list_str": [
        "string1",
        "string2",
        "string3",
    ],
    "_4_list_int": [
        123,
        456,
        789,
    ],
    "_4_list_bool": [True, False, True, False],
    "_4_list_null": [
        None,
        None,
        None,
    ],
    "_5_list_dict": [
        {
            "key": "value1",
        },
        {
            "key": "value2",
        },
        {
            "key": "value3",
        },
    ],
    "_6_list_list": [
        ["value1"],
        ["value2"],
        [1234],
    ],
    "_7_list_empty": [],
    # "_8_list_mixed": ["value", 12, True, {"key": "val", "dict": {"subkey": 1234}}],
    # "_9_list_mixed_KO": [ 12, True, {"key": "val", "dict": {"subkey": 1234}}],
}


def test_autoconf_levels_get_values_minus1():

    node = NodeAuto(ident="AutoConf-1", payload=payload_regression, autoconf=-1)
    pprint(node.__dict__)
    node.dump()
    assert node.get_value() == {}


def test_autoconf_levels_get_values_0():

    node = NodeAuto(ident="AutoConf0", payload=payload_regression, autoconf=0)
    assert node.get_value() == payload_regression


def test_autoconf_levels_get_values_1():

    node = NodeAuto(ident="AutoConf1", payload=payload_regression, autoconf=1)
    assert node.get_value() == payload_regression


def test_autoconf_levels_get_values_2():

    node = NodeAuto(ident="AutoConf2", payload=payload_regression, autoconf=2)
    assert node.get_value() == {}


def test_autoconf_levels_get_values_3():

    node = NodeAuto(ident="AutoConf3", payload=payload_regression, autoconf=3)
    assert node.get_value() == {}


def test_autoconf_get_values_regressions(data_regression):

    print("HELLO")

    node = NodeAuto(ident="AutoConf2", payload=payload_regression, autoconf=2)

    result = {}
    for name, i in node.get_children().items():
        out = i.get_value(lvl=-1)
        result[name] = out

    data_regression.check(result)


def test_autoconf_get_children_regressions(data_regression):

    node = NodeAuto(ident="AutoConf2", payload=payload_regression, autoconf=4)

    pprint(node.__dict__)
    pprint(node.get_children())
    # node.dump(all=True)

    result = {}
    for name, child in node.get_children().items():
        count = child.get_children()
        pprint(count)
        # out = len(childs)
        result[name] = len(count)
        # result[name] = f"{child.__class__.__name__}_{child.kind}_{child.ident} {len(count)}"

    pprint(result)
    data_regression.check(result)


if __name__ == "__main__":
    retcode = pytest.main([__file__])
