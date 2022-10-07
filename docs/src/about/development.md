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


## Quality Process

Run automatic linting:
```
black passify
```

Run linting report:
```
pylint paasify
```

Run tests:
```
pytest tests
```

Create commit:
```
git add <modified files>
git commit -m ""
```


## Commit message standards

TODO: