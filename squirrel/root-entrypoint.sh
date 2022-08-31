#!/bin/bash
su postgres -s /opt/docker-entrypoint.sh
d=$(date +'%d.%m.%Y')
mv /opt/artefacts.tar.gz /opt/arts/squirrel-{$d}-$VERSION.tar.gz
sudo chmod 777 /opt/arts/squirrel-{$d}-$VERSION.tar.gz
/bin/bash