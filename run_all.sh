#!/bin/bash
# This script downloads only the page lists for every single category.

echo "### APP (LEVEL 1) ###"
python3 downloader_ultimate.py apps --all-pages --fetch-slugs --fetch-links

echo "### GAME (LEVEL 1) ###"
python3 downloader_ultimate.py games --all-pages --fetch-slugs --fetch-links

echo "### ALL TASKS COMPLETE ###"
