#!/usr/bin/env bash
set -e

# check data download progress, if no progress made in the last hour, send out email notifications
# This command is extremely slow on bank's aws, take around 4 minutes
data_size=`docker system df -v | { grep "peru-data " || true; } | tr -s ' ' | cut -d ' ' -f 3-4`

FILE=/tmp/peru_scraper_downloaded
if test -f "$FILE"; then
  last_data_size=`cat $FILE`
  if [ "$data_size" = "$last_data_size" ]; then
    subject="[Peru Scraper] Error Notification"
    body="Peru scraper failed to make progress. Total data downloaded: $data_size. Please login to server at `hostname -s` to investigate."
    to="elias.serrani@gmail.com,wlu4@worldbank.org"
    echo -e "Subject:${subject}\n${body}" | sendmail -t "${to}"
  else
    echo "More data downloaded - before: $last_data_size, now: $data_size"
  fi
fi

# always update data size on file
echo $data_size > $FILE


