#!/bin/bash

APP_NAME=paasify
APP_ARGS=--version

main ()
{
  echo "Python code version:                     $($APP_NAME $APP_ARGS | sed 's/.*: //' )"
  echo "Semantic Release version:                $(semantic-release print-version --current)"
  echo "Next beta   (task release_beta):         $(semantic-release print-version --next --prerelease)"
  echo "Next stable (task release_prod):         $(semantic-release print-version --next 2>&1 )"

  echo "---"
  echo "Next beta patch: $(semantic-release print-version --next --prerelease --patch )"
  echo "Next beta minor: $(semantic-release print-version --next --prerelease --minor )"
  echo "Next beta major: $(semantic-release print-version --next --prerelease --major )"
  echo "---"

  echo "Next stable patch: $(semantic-release print-version --next --patch )"
  echo "Next stable minor: $(semantic-release print-version --next --minor )"
  echo "Next stable major: $(semantic-release print-version --next --major )"
  echo "---"


  echo "Current changelog (semantic-release changelog --unreleased)"
  semantic-release changelog --unreleased | tail -n 20
}

main $@
