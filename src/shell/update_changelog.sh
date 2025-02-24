#!/bin/bash

###################################################################
#Script Name	: update_changelog.sh
#Description	: Updates the CHANGELOG.md with lists of updated/added files in the commit
#Args         : None
###################################################################

git add images/\*
git add data/\*
git add exports/\*
printf -- "\r\n" >> CHANGELOG.md
printf -- "## $(date '+%Y%m%d-%H%M%S')\r\n" >> CHANGELOG.md
printf -- "\r\n" >> CHANGELOG.md
printf -- "### Added\r\n" >> CHANGELOG.md
printf -- "\r\n" >> CHANGELOG.md
changed_files=$(git diff --name-status HEAD)
IFS=$'\n'
for line in $changed_files; do
  status=$(echo "$line" | cut -f1)
  file=$(echo "$line" | cut -f2)
  if [[ "$file" == images/tiles/* ]]; then
    if [[ "$status" == "A" ]]; then
      echo "- Added PNG from Google Drive '$(basename "$file")'"  >> CHANGELOG.md
    else
      echo "- Updated PNG from Google Drive '$(basename "$file")'"  >> CHANGELOG.md
    fi
  elif [[ "$file" == images/tiles-svg/* ]]; then
    if [[ "$status" == "A" ]]; then
      echo "- Added SVG from Google Drive '$(basename "$file")'"  >> CHANGELOG.md
    else
      echo "- Updated SVG from Google Drive '$(basename "$file")'"  >> CHANGELOG.md
    fi
  elif [[ "$file" == data/*.json ]]; then
    if [[ "$status" == "A" ]]; then
      echo "- Create data export '$(basename "$file")'"  >> CHANGELOG.md
    else
      echo "- Updated data export '$(basename "$file")'"  >> CHANGELOG.md
    fi
  elif [[ "$file" == exports/* ]]; then
    if [[ "$status" == "A" ]]; then
      echo "- Create weekly exports '$(basename "$file")'"  >> CHANGELOG.md
    else
      echo "- Updated weekly exports '$(basename "$file")'"  >> CHANGELOG.md
    fi
  fi
done
printf -- ""  >> CHANGELOG.md