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
apache2-mpm-event \
libapache2-mod-wsgi \
libapache2-mod-xsendfile


RUN mkdir -p /data/git/manager \
&& mkdir -p /data/storage/shared \
&& mkdir -p /data/storage/manager \
&& mkdir -p /data/bins/ \
&& mkdir -p /data/config

ENV APACHE_RUN_USER www-data
ENV APACHE_RUN_GROUP www-data
ENV APACHE_LOG_DIR /var/log/apache2
ENV APACHE_PID_FILE /var/run/apache2.pid
ENV APACHE_RUN_DIR /var/run/apache2
ENV APACHE_LOCK_DIR /var/lock/apache2

RUN mkdir -p $APACHE_RUN_DIR $APACHE_LOCK_DIR $APACHE_LOG_DIR

RUN pip install virtualenv \
&& virtualenv /data/venv

ENV PIP_PACKAGES_VERSION 2
ADD requirements.txt /requirements.txt

RUN . /data/venv/bin/activate && pip install -r /requirements.txt

VOLUME /data/git/manager
VOLUME /data/config
VOLUME /data/storage/shared
VOLUME /data/storage/manager

ENV IS_DOCKER True
ENV USE_X_SENDFILE True

EXPOSE 7777

ADD 000-default.conf /etc/apache2/sites-available/000-default.conf
ADD runserver.sh /runserver.sh
ADD manage.sh /manage.sh

ENTRYPOINT ["bash", "/runserver.sh"]

