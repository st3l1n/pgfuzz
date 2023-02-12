#!/bin/bash
screen -dmS squirrel ./screen.sh
sleep $TIMEOUT
screen -S squirrel -p 0 -X stuff "^C"
sleep 60
d=$(date +'%d.%m.%Y')
tar -zcf artefacts.tar.gz --directory=/tmp/fuzz .
sudo mv artefacts.tar.gz /opt/share/squirrel-$d-$BRANCH.tar.gz
sudo chmod 666 /opt/share/squirrel-$d-$BRANCH.tar.gz