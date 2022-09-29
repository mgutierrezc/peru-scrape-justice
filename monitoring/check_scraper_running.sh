#!/usr/bin/env bash
set -e

# check for running scraper container, if not start one
check_output=`docker ps -f status=running | { grep scrape.py || true; }`
if test -z "$check_output"
then
  echo "No running scraper container found. Restarting..."
  docker run -d --volume peru-data:/code/data peru_scrape:latest python scrape.py -y 2020
fi
