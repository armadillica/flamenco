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
npm \
apache2-mpm-event \
libapache2-mod-wsgi \
libapache2-mod-xsendfile

RUN mkdir -p /data/git/dashboard \
&& mkdir -p /data/storage/shared \
&& mkdir -p /data/storage/dashboard \
&& mkdir -p /data/config

ENV APACHE_RUN_USER=www-data \
APACHE_RUN_GROUP=www-data \
APACHE_LOG_DIR=/var/log/apache2 \
APACHE_PID_FILE=/var/run/apache2.pid \
APACHE_RUN_DIR=/var/run/apache2 \
APACHE_LOCK_DIR=/var/lock/apache2

RUN mkdir -p $APACHE_RUN_DIR $APACHE_LOCK_DIR $APACHE_LOG_DIR

RUN pip install virtualenv \
&& virtualenv /data/venv

ENV PIP_PACKAGES_VERSION 2
ADD requirements.txt /requirements.txt

RUN . /data/venv/bin/activate && pip install -r /requirements.txt

VOLUME /data/git/dashboard
VOLUME /data/config
VOLUME /data/storage/shared
VOLUME /data/storage/dashboard

ENV IS_DOCKER=True \
USE_X_SENDFILE=True

EXPOSE 8888

ADD rs.sh /usr/local/bin/rs
RUN chmod +x /usr/local/bin/rs
ADD 000-default.conf /etc/apache2/sites-available/000-default.conf
ADD runserver.sh /runserver.sh
ADD setup.sh /setup.sh

ENTRYPOINT ["bash", "/runserver.sh"]
