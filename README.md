# Peru Case Data Scraper

This project contains script to scrape case data from https://cej.pj.gob.pe/cej/forms/busquedaform.html

## Development

### Requirements

- python 3
- ChromeDriver
- [Git Large File Storage](https://git-lfs.github.com/): for versioning the data model file as it is over 100MB
- virtualenv (optional)
- textract native dependencies. Please follow OS specific instructions: https://textract.readthedocs.io/en/latest/installation.html

```
# To install textract native dependencies on macos:
brew cask install xquartz
brew install poppler antiword unrtf tesseract swig
```

### Setup

```
# optional:
mkvirtualenv peru_scrape
workon peru_scrape

# required:
pip install -r requirements.txt
```

### Running Scripts Locally (for Development/Testing)

To download data:

```
python scrape.py
```

Note: this requires solving captchas, for which we use code from https://github.com/clovaai/deep-text-recognition-benchmark

To extract data from the downloaded HTML and pdf/doc files:

```
# Process pdf/doc files in data/**/downloaded_files, producing data_cleaned/DF_DOWNLOADS.csv
python extract_from_downloads.py

# Process html files in data/**/raw_html folders, producing the rest of the csv files in data_cleaned
python extract_from_html.py
```

### Running Scripts in Docker (on Server)

**Setting up a new instance**

Instance type: t2.medium, Amazone Linux 2
Storage: 200GB, general purpose EBS

```
# install dependencies
sudo yum update -y
sudo amazon-linux-extras install docker -y
sudo service docker start
sudo usermod -a -G docker ec2-user
sudo yum install git -y
curl -s https://packagecloud.io/install/repositories/github/git-lfs/script.rpm.sh | sudo bash
sudo yum install git-lfs -y
git lfs install

# If you do not have sudo power to install git-lfs here's a workaround:
wet https://github.com/github/git-lfs/releases/download/v1.2.0/git-lfs-linux-amd64-1.2.0.tar.gz
tar -xf git-lfs-linux-amd64-1.2.0.tar.gz
cd git-lfs-1.2.0
# edit install.sh
# change the value of prefix variable to: prefix="$HOME/bin"
bash install.sh
# if and when neccessary, instead of git lfs pull, use
~/bin/bin/git-lfs pull

# get source code
git clone https://github.com/dime-worldbank/peru-scrape.git

# build docker image & create volume
cd peru_scrape
docker build -t peru_scrape .
docker volume create peru-data

docker volume inspect peru-data
# output:
# [
#     {
#         "CreatedAt": "2020-06-12T11:49:11Z",
#         "Driver": "local",
#         "Labels": {},
#         "Mountpoint": "/var/lib/docker/volumes/peru-data/_data",
#         "Name": "peru-data",
#         "Options": {},
#         "Scope": "local"
#     }
# ]

# create directory for cleaning/extraction scripts
sudo mkdir -p /var/lib/docker/volumes/peru-data/_data_cleaned
```

**Running scraping script**

For docker version 17.06 or later
```
docker run -d \
  --name=peru_scrape_run \
  --mount source=peru-data,destination=/code/data \
  peru_scrape:latest python scrape.py -y 2020
```

For old docker versions:
```
docker run -d --volume peru-data:/code/data peru_scrape:latest python scrape.py -y 2020
```


**Running cleaning/extraction script**

```
# run cleaning scripts: html
docker run -d \
  --mount type=bind,source="/var/lib/docker/volumes/peru-data/_data",target=/code/data,readonly \
  --mount type=bind,source="/var/lib/docker/volumes/peru-data/_data_cleaned",target=/code/data_cleaned \
  peru_scrape:latest python extract_from_html.py

# run cleaning scripts: downloaded files
docker run -d \
  --mount type=bind,source="/var/lib/docker/volumes/peru-data/_data",target=/code/data,readonly \
  --mount type=bind,source="/var/lib/docker/volumes/peru-data/_data_cleaned",target=/code/data_cleaned \
  peru_scrape:latest python extract_from_downloads.py
```

For old docker versions, say on a different data volume directory peru-data-2019:
```
docker run -d \
  -v /Data/docker/volumes/peru-data-2019/_data:/code/data:ro \
  -v /Data/docker/volumes/peru-data-2019/_data_cleaned:/code/data_cleaned \
  peru_scrape:latest python extract_from_html.py

docker run -d \
  -v /Data/docker/volumes/peru-data-2019/_data:/code/data:ro \
  -v /Data/docker/volumes/peru-data-2019/_data_cleaned:/code/data_cleaned \
  peru_scrape:latest python extract_from_downloads.py
```


### Setting up cron job to monitor scraping (on Server)

Monitoring scripts are in the `monitoring` folder. They can be easily setup using `crontab`:

```
# Edit cron job:
crontab -e

# press i (enter edit mode in vi)
# copy the content in monitoring/sample_crontab, right click should paste it
# update the file paths to point to your git tracked version of the monitoring scripts
# press :wq to save crontab
```

To test your cronjob setup, you can try this: https://unix.stackexchange.com/a/602690/11180

To edit email notification recipients, edit them in the relevant bash script files (.sh) and send a PR for review & merge.
Please keep the monitoring scripts in git up-to-date with what's used for crontab on server.

Note: `check_scraper_running.sh` restarts the scraper task if it detects no scraper container is running,
but it hardcodes scraping task to do 2020.
If we were to ever move to a different year, remember to update this.

### Uploading to & downloading data from WB server

Since the WB EC2 instance is only accessible through putty on dedicated windows VDI, `rsync` from PC is not an option.
Here's one way to get data in and out of the server.
Since the following procedure requires data temporarily exposed to public access, make sure there's no sensitive data before doing this!

#### Requirements

- An AWS S3 bucket that's publicly readable
- A pair of AWS Access Key ID and Secret Access Key

#### Local to Server

1. zip data & upload to your S3 bucket
2. Copy the Object URL of the uploaded zip
3. Change the https to http in the URL, e.g. https://mybucket.s3.amazonaws.com/data.zip becomes http://mybucket.s3.amazonaws.com/data.zip
4. ssh into WB server and wget the URL, e.g. `wget http://mybucket.s3.amazonaws.com/data.zip`

#### Server to Local/Dropbox

1. Install aws cli if it's not already installed (you can test it with `which aws`, empty output means not installed). This project uses docker so if the data directory is only accessible through docker then aws needs to be installed and configured inside docker. You can do something like `docker run  -v /Data/docker/volumes/peru-data-2019/_data_cleaned:/code/data_cleaned:ro -it peru_scrape:latest bash` to start an ad-hoc docker container with the data volume attached & accessible, and install aws in there.
2. Configure aws with your access key ID & secret: `aws configure`
3. Upload data to your S3 bucket, e.g. `aws s3 cp /code/data_cleaned s3://mybucket/ --recursive`
4. Download data to your PC

### running using nohup
nohup python scrape.py -y 2022 -l ANCASH > scrape.log 2>&1 &
#### stoping the script
ps aux | grep scrape.py 

kill <process id>

### location string
```
'AMAZONAS','ANCASH','APURIMAC','AREQUIPA','AYACUCHO','CAJAMARCA','CALLAO','CAÑETE','DEL SANTA','HUANCAVELICA','HUANUCO','HUAURA','ICA','JUNIN','LA LIBERTAD','LAMBAYEQUE','LIMA','LIMA ESTE','LIMA NORTE','LIMA SUR','LORETO','MADRE DE DIOS','MOQUEGUA','PASCO','PIURA','PUNO','SAN MARTIN','SELVA CENTRAL','SULLANA','TACNA','TUMBES','UCAYALI','VENTANILLA - LIMA NOROESTE'
```
