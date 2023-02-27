FROM python:3.10-slim-buster

ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# RUN apt-get install build-essential libgtk-3-dev libdbus-glib-1-dev libpulse-dev libxt-dev yasm
RUN apt-get update && \
 apt-get install -y wget

RUN wget -O /tmp/firefox-109.0.tar.bz2 https://download-installer.cdn.mozilla.net/pub/firefox/releases/109.0/linux-i686/en-US/firefox-109.0.tar.bz2
RUN ls
RUN tar -C /opt -xvf /tmp/firefox-109.0.tar.bz2 
RUN cd /opt/firefox-109.0 && ./mach build && ./mach install

# Install Geckodriver
RUN wget -O /tmp/geckodriver.tar.gz https://github.com/mozilla/geckodriver/releases/download/v0.32.2/geckodriver-v0.32.2-linux64.tar.gz && \
    tar -C /opt -xzf /tmp/geckodriver.tar.gz && \
    chmod +x /opt/geckodriver && \
    ln -fs /opt/geckodriver /usr/bin/geckodriver


WORKDIR /usr/peru_scrapper

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

