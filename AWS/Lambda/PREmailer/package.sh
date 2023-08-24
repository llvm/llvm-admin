#!/usr/bin/env bash
 
# Builds a lambda package from a single Python 3 module with pip dependencies.
# This is a modified version of the AWS packaging instructions:
# https://docs.aws.amazon.com/lambda/latest/dg/lambda-python-how-to-create-deployment-package.html#python-package-dependencies
 
# https://stackoverflow.com/a/246128
SCRIPT_DIRECTORY="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
 
pushd $SCRIPT_DIRECTORY > /dev/null
 
rm -rf .package function.zip
mkdir .package
 
pip3.8 install --target .package --requirement requirements.txt
 
pushd .package > /dev/null
zip --recurse-paths ${SCRIPT_DIRECTORY}/function.zip .
popd > /dev/null
 
zip --grow function.zip pr_emailer.py
 
popd > /dev/null
