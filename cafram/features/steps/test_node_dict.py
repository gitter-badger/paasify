from behave import *
from cafram.nodes import *
from pprint import pprint

# Examples
# ===============================


class Class_conf_with_node_rename(NodeDict):
    "Example: Class key remap to attribute as node"

    # Set class expectations
    expected_value = {
        "other_key": "other_value",
    }

    expected_conf = {
        **{
            "new_name": "my private value",
        },
        **expected_value,
    }
    expected_children_keys = ["new_name"]

    # Configure class
    ident = "Test instance"
    conf_children = [
        {
            "key": "_old_name",
            "attr": "new_name",
            "cls": NodeVal,
            # "cls": str,
        }
    ]
    conf_default = {
        **{
            "_old_name": "my private value",
        },
        **expected_value,
    }


class Class_conf_with_val_rename(Class_conf_with_node_rename):
    "Example: Class key remap to attribute as value"

    expected_value = {"other_key": "other_value", "new_name": "my private value"}
    expected_conf = expected_value
    expected_children_keys = []

    # Configure class
    conf_children = [
        {
            "key": "_old_name",
            "attr": "new_name",
            # "cls": NodeVal,
            "cls": str,
        }
    ]


ex_classes = {
    "conf_with_node_rename": Class_conf_with_node_rename,
    "conf_with_val_rename": Class_conf_with_val_rename,
}


# Givens
# ===============================
@given("instance of '{config_cls}'")
def step_impl(context, config_cls):

    cls = ex_classes[config_cls]
    context.inst = cls()


@given("any class examples")
def step_impl(context):

    context.inst = []
    for name, cls in ex_classes.items():
        node = cls(ident=name)
        context.inst.append(node)


# When
# ===============================


# Then
# ===============================
@then("instance interfaces work as expected")
def check_key_remap(context):

    instances = context.inst
    if not isinstance(instances, list):
        instances = [instances]

    for inst in instances:
        print(f"Running test against: {inst}")
        pprint(inst.__dict__)

        # Ensure serialize return the correct output
        print(inst.serialize(mode="parsed"), inst.expected_conf)
        assert inst.serialize(mode="parsed") == inst.expected_conf
        assert inst.serialize(mode="default") == inst.conf_default
        assert inst.serialize(mode="raw") == None

        # Ensure value is correct
        value = inst.get_value()
        print(value, inst.expected_value)
        assert value == inst.expected_value

        # Ensure children are correclty setup
        children = inst.get_children()
        print("Children:", children, inst.expected_children_keys)
        for name in inst.expected_children_keys:
            assert name in children
            del children[name]
        assert (
            children == {}
        ), f"There should be other children than: {inst.expected_children}"

        # Reinject payload and check_raw_config value
        inst.deserialize(inst.conf_default)
        assert inst.serialize(mode="raw") == inst.conf_default
