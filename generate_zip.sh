#!/bin/bash

rm KiCad_Pinout.zip
mv metadata.json metadata_.json
jq --arg today "$(date +%Y.%m.%d)" '.versions[0].version |= $today' metadata_.json > metadata.json

git ls-files  -- 'metadata.json' 'resources/*.png' | xargs zip KiCad_Pinout.zip

mkdir -p plugins
git ls-files -- 'KiCad_Pinout/*.png' 'KiCad_Pinout/*.py' 'KiCad_Pinout/plugin.json' 'KiCad_Pinout/requirements.txt' '__init__.py' 'plugins/kicad_advanced' | xargs -I {} cp {} plugins/

zip -r KiCad_Pinout.zip plugins
rm -r plugins

mv metadata_.json metadata.json
