#!/bin/bash
/opt/fuzzing/afl-fuzz -t 2000 -m 2000 -i /opt/fuzzing/fuzz_root/crashes -o /opt/fuzzing/output /opt/pgpro/bin/postgres --single -D /opt/data main
echo "[+] creating artefacts in share dir"
cp /opt/postgres/logfile /opt/share/logfile
echo "[+] creating artefacts in share dir"
cp -r /opt/fuzzing/output /opt/share/squirrel_output
cd /opt
echo "[+] creating tar of artefacts in opt dir"
tar -zcf artefacts.tar.gz --directory=/opt/share .