#!/bin/bash

set -eu

BUILD_DIR=./build
mkdir -p $BUILD_DIR

paasify2 schema --format=json > $BUILD_DIR/paasify_yml_schema.json

mkdir -p $BUILD_DIR/html $BUILD_DIR/md
generate-schema-doc --config-file doc_schema_html.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR/html
generate-schema-doc --config-file doc_schema_md.yml $BUILD_DIR/paasify_yml_schema.json $BUILD_DIR/md

