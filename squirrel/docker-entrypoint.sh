#!/bin/bash
source /etc/profile.d/postgres.sh
pg_ctl -D /opt/data/ -l /opt/postgres/logfile start
cd /opt/src
cd /opt/fuzzing/fuzz_root
screen -dmS squirrel /opt/screen_fuzzing.sh
sleep 10
screen -S squirrel -p 0 -X stuff "^M"
sleep $TIMEOUT
screen -S squirrel -p 0 -X stuff "^C"
sleep 10
