# Developpement


This is the general workflow:

1. Code Development
    * Update the code
    * Update the tests
    * Update the doc
    * Update release
        * Generate release notes
2. Documentation:
    * Generate jsonschema documentation
    * Generate mkdocs:
        * Include other files of the project
        * Import jsonschema documentation
        * Generate python code reference
3. Code Quality:
    * Run autolinter `black`
    * Run linting report `pylint`
    * Run tests:
        * Run unit tests
        * Run code-coverage
        * Run functional tests
        * Run examples tests
4. Delivery:
    * Documentation:
        * Build static documentation
    * Release Pypi:
        * Build package
        * Push package
    * Release Container:
        * Build Docker Build env
        * Build Paasify App Image
        * Build Paasify Documentation Image
        * Push images
5. Contributing:
    * Create a git commit
    * Create a pull request
    * Review of the commit
    * Merge to upstream if accepted

Once you developped or changed things, you need to test

## Recommended tools

Recommended tools:

* [Poetry](https://python-poetry.org/): Python project management
* [Task](https://taskfile.dev/): MakeFile replacement
* [direnv](https://direnv.net/): Allow to enable 

Troubleshooting:

* [jq](https://stedolan.github.io/jq/): Process JSON files
* [yq](https://mikefarah.gitbook.io/yq/): Process YAML files


## Quickstart

The main steps as been implemented as task files.

### Development

Run code linting:
```
task run_qa
```

Run tests:
```
task run_tests
```

Build docuementation:
```
task doc:build_doc
```

Build docker image:
```
task docker_build_image
```

Build python package:
```
task pkg_build
``` 

### Test and Review

Try directly:
```
paasify --version
```

Try you current code version in docker:
```
task docker_run -- --version
```

Try package installation:
```
pip3 install dist/paasify-0.1.1a2.tar.gz
```

Show documentation:
```
task doc:serve_doc: 
```



### Commit reviewable code

Bumping versions workflow:
```
poetry version prepatch  # Idempotent
poetry version prerelease
poetry version patch
poetry version minor
poetry version major

# Reset version
poetry version <expected version>

# Reset to default git version
task 
git checkout paasify.version.py
poetry version $(python -m paasify.version)

```

Create commit:
```
git add <modified files>
git commit -m ""
```

### Release

TODO

## Commit message standards

TODO:
