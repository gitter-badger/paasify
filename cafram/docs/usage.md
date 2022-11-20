# CAFram - Config As Framework

Opiniated config as framework for python applications

## Introduction

Let's create a basic config called `config1.yml`:
```
config:
  config1: val1
  config2: val2
  config3: val3
items_list:
  - hello
  - world
items_dict:
  bye:
  world:
    option: value
```

Then let's map this to the code:
```
from cafram import node


# Items
class AppItemList(node.ConfList):
  pass

class AppItemDict(node.ConfDict):
  pass


# Controllers
class AppConfig(node.ConfAttr):
  pass

class AppItemsList(node.ConfList):
  conf_struct = AppItemList

class AppItemsDict(node.ConfDict):
  pass


# Main application
class App(node.Base):
  
  conf_struct = {
      "config": AppConfig,
      "items_list": AppItemsList,
      "items_dict": AppItemsDict,
    }

# Execute program
config = anyconfig.load("config1.yml")

# Let check program by default
app = App()
app.dump()

# Now inspect once config is loaded
app.deserialize(config)
app.dump()

```

Which returns:
```
Blahhhh ....
```


### Alternatives:

* configobj - INI file parser with validation.
* configparser - (Python standard library) INI file parser.
* hydra - Hydra is a framework for elegantly configuring complex applications.
* profig - Config from multiple formats with value conversion.
* python-decouple - Strict separation of settings from code.

