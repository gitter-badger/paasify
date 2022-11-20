#!/bin/bash

black .
pytest --cov=cafram  --cov-branch --cov-report term-missing -vv tests
pylint  -f colorized  cafram

