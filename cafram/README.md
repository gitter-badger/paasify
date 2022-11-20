# CAFRAM - Config as Framework


Cafram is a hierarchical configuration framework for Python. It provides classes to map a hierarchical configuration (usually loaded from YAML files) to Python objects. Then it provides a foundation to organize your application code. 

## Quickstart

On it's simplest form, it can load a simple yaml file and create a NodeObject:

```
import yaml
from cafram.nodes import ConfAuto

yaml_config = """
config:
  namespace: "my_ns"
  create_file: True
  backups: 3
  backup_prefix: null
files:
  - name: hello
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

app = ConfAuto(ident="app", payload=config, autoconf=-1)
print ("List of files: ", app.files.get())
app.dump()
```

This is quite convenient, but it's quite useless.



## Meta

Author: MrJK
License: GPLv3


