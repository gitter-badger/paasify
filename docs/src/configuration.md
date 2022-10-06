# Configuration


## Project and stacks

A project is the top level configuration for a list of given stacks.

### stacks

A stack is a simple set of dependant services, it would be comparable
to a kubernetes pod.

The simplest stack form is
```
stacks:
  - name: traefik
```

### Stacks vars

To assign vars to stack:
```
stacks:
  - name: traefik
```

But globally:
```
config:
  vars:
    myvar: my_value_default
stacks:
  - name: traefik
    vars:
      myvar: my_value_override
```


### Stacks tags


A tag can either corresponds to:

* a docker-compose: `docker-compose.<tag_name>.yml` YAML file
* a jsonnet script: `<tag_name>.jsonnet` jsonnet file

Both mechanisms allow to achieve different things, while the former
provide a well-known docker-compose merge mechanism, it may not
sufficient to provide advanced functionnality, and this is where the 
later become useful, leveraging the jsonnet language support to modify
docker-compose structure. 


How to choose between both?

* docker-compose pro:
    * Well known merge mecanism, supported by docker, easy to use
* docker-compose con:
    * Quite limited on advanced use case, such as rewrite or modification
* Jsonnet pro:
    * Allow to create variables
    * Very powerful turing language to manupulate docker-compose content
    * Provides a convenient API/plugin system
* Jsonnet con:
    * Need to learn jsonnet language
    * Sometime hard to debug


How is processed a stack?

* Read variables:
    * Generate default stack vars (paasify)
    * Read all tags default_variables (<tags>.jsonnet)
    * Read upstream app vars (vars.yml)
    * Read local app vars (vars.yml)
    * Read global conf variables (conf.vars)
    * Read stack variables (stack.vars)
    * Read all tags override_variables (<tags>.jsonnet)
* Get docker-files:
    * Find all docker-files matching tags in local app (docker-compose.<tags>.yaml)
    * Fallback on found all docker-files matching tags in upstream app (docker-compose.<tags>.yaml)
* Build docker-compose file:
    * Assemble all found docker-files with all vars
* On the `docker-compose config` output
    * Read all tags with jsonnet and apply transform hook (<tags>.jsonnet)
        * All vars defined in a tag config are local
* Write final docker-compose:
    * Write into: <stack_dir>/docker-compose.run.yml


To assign vars to stack:
```
stacks:
  - name: traefik
    tags:
      - tag1
      - tag2
```

To assign vars to jsonnet tag:
```
config:
  tags_prefix:
      - tag1
      - tag2
stacks:
  - name: traefik
    tags:
      - tag3
      - tag4:
          tag_var1: value1
          tag_var2: value2
```

### Upstream stacks (sources)

Paasify provides a way to make your code DRY be exposing a app repository
feature. You can use any git repo to create a stack collection

```
sources:
    myapps:
      url: http://github.com/mrjk/paasify_collection.git
stacks:
  - name: traefik
    app_source: myapps
  - app: myapps:traefik
```

## Building stack

How is processed a stack?

* Read variables:
    * Generate default stack vars (paasify)
    * Read all tags default_variables (<tags>.jsonnet)
    * Read upstream app vars (vars.yml)
    * Read local app vars (vars.yml)
    * Read global conf variables (conf.vars)
    * Read stack variables (stack.vars)
    * Read all tags override_variables (<tags>.jsonnet)
* Get docker-files:
    * Find all docker-files matching tags in local app (docker-compose.<tags>.yaml)
    * Fallback on found all docker-files matching tags in upstream app (docker-compose.<tags>.yaml)
* Build docker-compose file:
    * Assemble all found docker-files with all vars
* On the `docker-compose config` output
    * Read all tags with jsonnet and apply transform hook (<tags>.jsonnet)
        * All vars defined in a tag config are local
* Write final docker-compose:
    * Write into: <stack_dir>/docker-compose.run.yml



## Managing many projects