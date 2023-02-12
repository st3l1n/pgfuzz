#!/bin/bash
sudo -u postgres /opt/pg/docker-entrypoint.sh
d=$(date +'%d.%m.%Y')
cp /opt/artefacts.tar.gz /opt/arts/sqlancer-$d-$BRANCH.tar.gz
sudo chmod 777 /opt/arts/sqlancer-$d-$BRANCH.tar.gz
/bin/bash