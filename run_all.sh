#!/bin/bash
# This script downloads only the page lists for every single category.

echo "###  APP(LEVEL 1) ###"
python downloader_ultimate.py apps --all-pages --fetch-slugs --fetch-links

ECHO ###   GAME(LEVEL 1) ###"

python downloader_ultimate.py games --all-pages --fetch-slugs --fetch-links

ECHO ### ALL TASKS COMPLETE ###
pause