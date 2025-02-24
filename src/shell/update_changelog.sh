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
# Restrict to folders withed with generated content
changed_files=$(git diff --name-status HEAD ./data ./exports ./images)
# Count the number of lines in the diff output
line_count=$(echo "$changed_files" | sed '/^\s*$/d' | wc -l)
# Only generate CHANGELOG.md when Google content was pulled
if [ "$line_count" -eq 0 ]; then
  echo "No changes detected."
else
  echo "Changes detected: $line_count"
  echo "$changed_files"
  printf -- "\r\n" >> CHANGELOG.md
  printf -- "## $(date '+%Y%m%d-%H%M%S')\r\n" >> CHANGELOG.md
  printf -- "\r\n" >> CHANGELOG.md

  added_section=""
  changed_section=""

  IFS=$'\n'
  for line in $changed_files; do
    status=$(echo "$line" | cut -f1)
    file=$(echo "$line" | cut -f2)

    if [[ "$file" == images/tiles/* ]]; then
      if [[ "$status" == "A" ]]; then
        added_section+="- Added PNG from Google Drive '$(basename "$file")'\r\n"
      else
        changed_section+="- Updated PNG from Google Drive '$(basename "$file")'\r\n"
      fi
    elif [[ "$file" == images/tiles-svg/* ]]; then
      if [[ "$status" == "A" ]]; then
        added_section+="- Added SVG from Google Drive '$(basename "$file")'\r\n"
      else
        changed_section+="- Updated SVG from Google Drive '$(basename "$file")'\r\n"
      fi
    elif [[ "$file" == data/*.json ]]; then
      if [[ "$status" == "A" ]]; then
        added_section+="- Create data export '$(basename "$file")'\r\n"
      else
        changed_section+="- Updated data export '$(basename "$file")'\r\n"
      fi
    elif [[ "$file" == exports/* ]]; then
      if [[ "$status" == "A" ]]; then
        added_section+="- Create weekly exports '$(basename "$file")'\r\n"
      else
        changed_section+="- Updated weekly exports '$(basename "$file")'\r\n"
      fi
    fi
  done

  if [ -n "$added_section" ]; then
    printf -- "### Added\r\n" >> CHANGELOG.md
    printf -- "\r\n" >> CHANGELOG.md
    printf -- "$added_section" >> CHANGELOG.md
  fi

  if [ -n "$changed_section" ]; then
    printf -- "### Changed\r\n" >> CHANGELOG.md
    printf -- "\r\n" >> CHANGELOG.md
    printf -- "$changed_section" >> CHANGELOG.md
  fi
fi
