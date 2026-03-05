#!/bin/bash

mkdir -p autostars
cp readme.md manifest.json test.py -t autostars/
cp -r src autostars/
find autostars -name "*__pycache__*" -exec rm -rf {} +
zip -r plugin.zip autostars
rm -rf autostars