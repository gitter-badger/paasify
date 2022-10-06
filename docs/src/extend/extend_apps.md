# Extend apps


## Introduction

Paasify provides a way to extend apps, via collections and apps.

A repo:
* is collection or a set of collections hierarchically organized

A collection can include:

* A set of apps definitions (/<app_name>/)
* A set of plugins (.paasify/plugins/*.jsonnet)

An app can include:

* a set of default variables (vars.yml)
* An app definitions (docker-compose.yml)
* Tags definitions (docker-compose.<tag>.yml)
* A set of plugin for this app (<tag>.jsonnet)

## Create a repo

This is a simple git repository where files are commited.


## Create a collection

## Create an app

TODO:

* explain: vars.yml
