# Concepts


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

Checkout [Advanced topics](advanced.md) to learn more.

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

## Managing many projects

TODO