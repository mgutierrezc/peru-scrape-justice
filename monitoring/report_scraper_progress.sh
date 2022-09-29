#!/usr/bin/env bash
set -e

docker_container_id=`docker ps -f status=running | { grep scrape.py || true; } | cut -d ' ' -f 1`
if test -z "$docker_container_id"
then
  body="Scraper not running. If this is expected please turn off this progress reporting cron job, otherwise, something is wrong. Manual investigation is required."
else
  last_done=`docker logs $docker_container_id 2>&1 | { grep 'Done processing' || true; } | tail -1`
  total_size=`cat /tmp/peru_scraper_downloaded`
  body=" ${last_done}. \nTotal data size downloaded: ${total_size}"
fi

subject="[Peru Scraper] Progress update"
to="elias.serrani@gmail.com,wlu4@worldbank.org,daniel.li.chen@gmail.com,mramosmaqueda@worldbank.org"
echo -e "Subject:${subject}\n${body}" | sendmail -t "${to}"


