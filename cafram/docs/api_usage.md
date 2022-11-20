# API Usage


## Model

Cafram provides diferent classes to modelize complexe data config. Each kind
of classes works quite the same way.

Workflow:
* deserialize:
    * Fetch config from `conf_schema` if present
        * Fall back on `conf_default` value
        * If it's a dict, the default value is updated with payload
        * If it's a list, the default value is set to payload 
    * Configuration is validated against jsonschema
        * Or do nothing if jsonschema is not set
    * Node ident is created from `conf_ident`, if the later is a string
    * Hook: `node_hook_conf` is executed, it MUST return the payload
        * It is only a payload modifier helper
        * No application logic can live there
        * Only parent node can be accessed, no children
            * If you need to traverse upper nodes, be sure you set a correct loading order in `conf_children` list (Dict Only)
    * Children nodes are created
        * Then start again a deserialization with the corresponding payload
    * Hook: `node_hook_children` is executed.
        * Payload modifications are not allowed
        * Parents and children nodes can be accessed
            * If you need to traverse upper nodes, be sure you set a correct loading order in `conf_children` list (Dict Only)

## Hooks