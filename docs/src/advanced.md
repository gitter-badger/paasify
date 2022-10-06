# Advanced


## Stack Build Process

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

## Two kinds of plugins

There are two kinds of plugins:

* a docker-compose: `docker-compose.<tag_name>.yml` YAML file
* a jsonnet script: `<tag_name>.jsonnet` jsonnet file

A plugin can be used for:

* Providing extra variables
* Transform docker-compose final file

How to choose between both?

|  | docker-compose | jsonnet |
|---|---|---|
| Pros | <ul> <li>Well known merge mecanism, supported by docker</li><li>Easy to learn</li></ul> | <ul> <li>Allow to create variables</li> <li>Very powerful turing language to manupulate docker-compose content</li> <li>Provides a convenient API/plugin system </li></ul> |
| Cons | <ul> <li>Quite limited on advanced use case, such as rewrite or modification</li></ul> | <ul> <li>Need to learn jsonnet language</li><li>Hard to learn and debug</li></ul> |

See how to [create plugins](extend/extend_plugins.md) for further infos.