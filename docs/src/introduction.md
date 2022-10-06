# Introduction



## Overview

Paasify try to make docker compose files deployment easier and more reproducible. The whole point is to deploy
docker containers:

* docker container: Actual workload
* docker-compose: Create docker containers
* paasify: Manage many docker-compose

So paasify is built over the concept of project, where is defined a sequential list of stacks. Each stacks corresponds to
a docker-compose file to be deployed. The whole is configured via a `paasify.yml` config file along a predetermined
file hierarchy.

Below a ten thousand foot overview.

#### Project configuration

There is a simple config file that illustrate all componants:
```
source:
    default:
        url: http://gthub.com/mrjk/...git
    internal:
        url: http://internal.org/mrjk/...git
config:
    vars:
        app_domain: domain.com
stacks:
  - name: traefik
    vars:
        app_fqdn: front.domain-admin.com
  - name: wordpress
    tags:
        mysql-sidecar
  - name: hello
    source: internal
    tags:
        mysql-sidecar
```

A source is a list of git repo collections. The config contains all settings that will
apply to the project and its stacks. The stacks is a list of sequential stacks to be applied.
Each stack is configurable and allow a fine grained configuration override dependings the user needs.
To each stack can be applied vars or a list of tags.


#### Project structure:

Example of organisation collections:

* project1/
    * paasify.yml: Main configuration config
    * .paasify/
        * collections/: Managed paasify sources dir ! (TMP dir)
        * plugins/
            * <tag_name>.jsonnet
    * stack1/
        * vars.yml
        * docker-compose.yml: Default docker-compose file, overrides from source
        * docker-compose.run.yaml: Generated docker compose file !
        * docker-compose.<tag_name>.yml: Custom tags
    * stack2/
    * stack3/
* project2/


#### Collection structure:

* collection_ident1:
    * .paasify/
        * plugins/
            * <tag_name>.jsonnet: Common stack plugins
    * stack1/
        * vars.yml
        * docker-compose.yml
        * docker-compose.<tag_name>.yml
            * docker-compose.debug.yml
            * docker-compose.mysql.yml
            * docker-compose.smtp.yml
        * <tag_name>.jsonnet: Local stack plugin
    * stack2/
* collection_ident2:


Eech collection is contained in a git repo. A git repo can have many collections. Many app are available
inside each collection. A collection can alos provides plugins, like stacks.



## Glossary


* Project
* Project Config
* Project Config
* Project Config Vars
* Project Config Tags
* Project Source
* Project Stacks

* Stack
* Stack Config
* Stack Vars
* Stack Tags
* Stack Collection App

* Collection Repository
* Collection App
* Collection Plugin



