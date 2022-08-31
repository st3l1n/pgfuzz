#!/bin/bash
sudo -u postgres /opt/postgres/docker-entrypoint.sh
d=$(date +'%d.%m.%Y')
cp /opt/artefacts.tar.gz /opt/arts/sqlancer-{$d}-$VERSION.tar.gz
sudo chmod 777 /opt/arts/sqlancer-{$d}-$VERSION.tar.gz
/bin/bash