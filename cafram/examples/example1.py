import sys

import yaml
import json
from pprint import pprint
from cafram.nodes import *
from cafram.utils import serialize


# App configuration
#######################

yaml_config = """
version: 1
config:
  namespace: "my_ns"
  create_file: True
  backups: 3
  backup_prefix: null

files:
  - name: hello
    filters:
      - author
  - name: world

filters:
  content:
    prepend: "Added at first"
    append: "Added at last"
  author:
    name: MyName
    date: True
"""

config = yaml.safe_load(yaml_config)


# App definition
#######################


# File management
# ----------------
class Config(ConfAttr):
    "Application config"
    conf_struct2 = ConfVal
    conf_struct2 = [
        {
            "key": "namespace",
            "cls": ConfVal,
        },
    ]


# Filter management
# ----------------
class Filter(ConfAttr):
    "A filter configuration"
    pass


class Filters(ConfAttr):
    "Filter manager"
    conf_struct2 = Filter


# File management
# ----------------
class FileFilters(ConfList):
    "Applied filters to file"
    conf_struct2 = ConfVal


class File(ConfAttr):
    "File to process"

    conf_struct2 = [
        {
            "key": "name",
            "cls": ConfVal,
        },
        {
            "key": "filters",
            "cls": FileFilters,
        },
    ]


class Files(ConfList):
    "File manager"
    conf_struct2 = File


class MyAppV2(ConfAttr):
    # class MyAppV2(ConfAuto):
    "Root application"

    conf_struct2 = [
        {
            "key": "config",
            "cls": Config,
        },
        {
            "key": "filters",
            "cls": Filters,
        },
        {
            "key": "files",
            "cls": Files,
        },
    ]


# App instance
#######################

app2 = MyAppV2(ident="app", payload=config, autoconf=-1)
app2 = ConfAuto(ident="app", payload=config, autoconf=-1)
# app2 = MyAppV2(ident="app", payload=config, autoconf=-1)
# app2 = ConfAuto(ident="app", payload=config, autoconf=1)

pprint(app2.get_nodes())

print(str(app2.value))

# App tests
#######################

# print ("\nApp nodes")
# pprint (app2._nodes)
# print ("\nFilter nodes")
# pprint (app2.filters._nodes)
# print ("\nFile nodes")
# pprint (app2.files._nodes)


print("\n\nApp nodes:")
pprint(app2.get_nodes(explain=False))
print("---")
print(serialize(app2.get_nodes(explain=False)))

print("\nApp nodes: EXPLICIT")
pprint(app2.get_nodes(explain=True))
print("---")
print(serialize(app2.get_nodes(explain=True)))


sys.exit()


#  print ("===================")
#
#  print ("\n\nApp config: ")
#  pprint ( app2.get_config(explain=False))
#  print ("---")
#  print ( serialize(app2.get_config(explain=False)))
#
#  print ("\nApp config Explicit: ")
#  pprint ( app2.get_config(explain=True))
#  print ("---")
#  print ( serialize(app2.get_config(explain=True)))
#
