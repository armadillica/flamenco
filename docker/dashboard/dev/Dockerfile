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
software-properties-common \
nodejs \
nodejs-legacy \
npm

RUN mkdir -p /data/git/dashboard \
&& mkdir -p /data/storage/shared \
&& mkdir -p /data/storage/dashboard \
&& mkdir -p /data/config

RUN pip install virtualenv \
&& virtualenv /data/venv

ENV PIP_PACKAGES_VERSION 1
ADD requirements.txt /requirements.txt

RUN . /data/venv/bin/activate && pip install -r /requirements.txt

VOLUME /data/git/dashboard
VOLUME /data/config
VOLUME /data/storage/shared
VOLUME /data/storage/dashboard

ENV IS_DOCKER True

EXPOSE 8888

ADD runserver.sh /runserver.sh
ADD setup.sh /setup.sh

ENTRYPOINT ["bash", "/runserver.sh"]
