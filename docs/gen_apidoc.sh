#!/bin/bash

set -eu

python -m bash_kernel.install

BUILD_DIR=./build
BUILD_DIR=./src/schema_doc
BUILD_DIR=./src/paasify_apidoc
mkdir -p $BUILD_DIR

paasify2 schema --format=json > $BUILD_DIR/paasify_yml_schema.json
paasify2 schema --format=yaml > $BUILD_DIR/paasify_yml_schema.yml

generate-schema-doc --config-file doc_schema_html.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR
generate-schema-doc --config-file doc_schema_md.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR

#mkdir -p $BUILD_DIR/html $BUILD_DIR/md
#generate-schema-doc --config-file doc_schema_html.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR/html
#generate-schema-doc --config-file doc_schema_md.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR/md


# Temporary project example !

# Generate plugin documentation
paasify2 --config ../examples/ex3/devbox_core/paasify.yml  explain --mode src/plugins_apidoc
