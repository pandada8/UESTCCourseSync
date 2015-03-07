#!/bin/bash
if [ ! -d '.env' ]; then
    # if there is no existed virtualenv Env. just create one
    virtualenv .env
fi
# Entering the virtualenv Env
source .env/bin/activate
# Install the required dependency
if [ -e 'requirements.txt' ]; then
    pip3 install -r requirements.txt
fi

