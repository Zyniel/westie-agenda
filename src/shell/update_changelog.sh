#!/bin/bash

###################################################################
#Script Name	: update_changelog.sh
#Description	: Updates the CHANGELOG.md with lists of updated/added files in the commit
#Args         : None
###################################################################

git add images/\*
git add data/\*
git add exports/\*
# Get the list of modifications
changed_files=$(git diff --name-status HEAD)
# Count the number of lines in the diff output
line_count=$(echo "$diff_output" | wc -l)
# Only generate CHANGELOG.md when Google content was pulled
if [ "$line_count" -eq 0 ]; then
  echo "No changes detected."
else
  echo "Changes detected: $line_count"
  printf -- "\r\n" >> CHANGELOG.md
  printf -- "## $(date '+%Y%m%d-%H%M%S')\r\n" >> CHANGELOG.md
  printf -- "\r\n" >> CHANGELOG.md
  printf -- "### Added\r\n" >> CHANGELOG.md
  printf -- "\r\n" >> CHANGELOG.md
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
fi


printf -- ""  >> CHANGELOG.md