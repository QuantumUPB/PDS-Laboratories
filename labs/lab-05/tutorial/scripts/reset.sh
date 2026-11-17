#!/bin/sh
set -eu
cd "$(dirname "$0")/.."

echo 'Stopping the Lab 05 containers...'
docker compose --profile incident down --remove-orphans
# This directory is created exclusively by setup.sh. Its contents include
# generated lab private keys, so reset deliberately removes them completely.
echo 'Removing ONLY labs/lab-05/tutorial/state (including generated lab keys)...'
rm -rf ./state

echo 'To recreate the lab, run: sh scripts/setup.sh'
