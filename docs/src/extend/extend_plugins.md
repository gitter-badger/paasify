# Tags and plugins




## Introduction

A plugin can be used for:

* Providing extra variables
* Transform docker-compose final file


### docker-compose tag

This is the easiest and simplest form of modularity to use. Just create
your `docker-compose.<tag_name>.yml` fragments, like explained
[here](https://docs.docker.com/compose/extends/).

### Jsonnet tag

This is a full turing compliant language avaialable to modify the
docker-compose internal structure. Jsonnet language is 
documented [here](https://jsonnet.org/learning/tutorial.html)




## Developping docker-compose plugins

This example taken from example dir presents how to modularize config.

Example:
```
$ ls -1  docker-compose.*
docker-compose.debug.yml
docker-compose.ep_https.yml
docker-compose.yml

$ head -n 999 docker-compose.*
==> docker-compose.debug.yml <==
services:
  traefik:
    environment:
      - TRAEFIK_LOG_LEVEL=debug
      - TRAEFIK_ACCESSLOG=true
      - TRAEFIK_API_DEBUG=true
      - TRAEFIK_ACCESSLOG_FILEPATH=

==> docker-compose.ep_https.yml <==
services:
  traefik:
    ports:
      - "$app_expose_ip:443:443"
    environment:
      # Entrypoints
      - TRAEFIK_ENTRYPOINTS_front-https_ADDRESS=:443 # <== Defining an entrypoint for port :80 named front
      # Forced Http redirect to https
      - TRAEFIK_ENTRYPOINTS_front-http_HTTP_REDIRECTIONS_ENTRYPOINT_PERMANENT=true
      - TRAEFIK_ENTRYPOINTS_front-http_HTTP_REDIRECTIONS_ENTRYPOINT_SCHEME=https
      - TRAEFIK_ENTRYPOINTS_front-http_HTTP_REDIRECTIONS_ENTRYPOINT_TO=front-https

```


## Developping jsonnet plugins

Start here to extend paasify functionnalities with a jsonnet plugin.

### Paasify Plugins API

TODO: Link and explain link to paasify.libjsonnet


Actions:

* metadata
* vars_default(vars)
* vars_override(vars)
* docker_transform(vars, docker_compose)

LINK: To variable processing order

### Base Plugins

This what looks like a basic plugin:
```
local paasify = import 'paasify.libsonnet';

local plugin = {

  // Provides plugin metadata
  metadata: {
      name: "Example plugins",
      description: 'Example plugin',

      author: "My Name",
      email: '',
      license: '',
      version: '',

      require: '',
      api: 1,
      schema: {},
    },

};

paasify.main(plugin)
```

### Vars Plugins

Notes:

* There must be function that accept vars argument as object.

```
local plugin = {

  // Return default vars
  default_vars(vars)::
    {
        default_var1: 'part1',
        default_var2: 'part2',
    },

  // Provides processed vars
  override_vars(vars):: 
    {
        config: vars.default_var1 + '.' + vars.default_var2,
    },
};
```



### Transform Plugins

This exemple will add custom networks and services:
```
local plugin = {

  // Transform docker compose structure
  docker_override (vars, docker_file)::
    docker_file + {

      //["x-debug"]: vars,

      # Append stack network
      networks+: {
        "new_network": null,
      },

      # Append new service
      services+: {
        "new_service": null,
      },


};
```

### Documenting Plugins

TODO: jsonschema

### Test and debug Plugins

TODO: Add features to support plugin development
