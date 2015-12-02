FROM ubuntu:14.04
MAINTAINER Francesco Siddi <francesco@blender.org>

RUN apt-get update && apt-get install -y \
python \
python-dev \
python-pip \
nano \
zlib1g-dev \
libjpeg-dev \
python-crypto \
python-openssl \
libmysqlclient-dev \
libssl-dev \
libffi-dev \
software-properties-common

RUN mkdir -p /data/git/server \
&& mkdir -p /data/storage/shared \
&& mkdir -p /data/storage/server \
&& mkdir -p /data/config

RUN pip install virtualenv \
&& virtualenv /data/venv

ENV PIP_PACKAGES_VERSION 2
ADD requirements.txt /requirements.txt

RUN . /data/venv/bin/activate && pip install -r /requirements.txt \
&& rm /requirements.txt

VOLUME /data/git/server
VOLUME /data/config
VOLUME /data/storage/shared
VOLUME /data/storage/server

ENV IS_DOCKER True

EXPOSE 9999

ADD runserver.sh /runserver.sh
ADD manage.sh /manage.sh

ENTRYPOINT ["bash", "/runserver.sh"]
