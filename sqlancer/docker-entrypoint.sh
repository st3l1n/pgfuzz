#!/bin/bash
source /etc/profile.d/postgres.sh
sudo su - root -c "echo '/opt/core.%e.%p.%s.%t' | sudo tee /proc/sys/kernel/core_pattern"
echo "[+] Starting postgres instance"
pg_ctl -D /opt/data/ -l /opt/pgpro/logfile start
echo "[+] Creating test database"
psql -U postgres -c 'create database test;'
echo "[+] Let the fun begins =)"
cd /opt/src
make installcheck-world
make coverage-html && cp -r coverage /opt/share/coverage1 && rm -r coverage
cd /opt/pgpro
cd /opt/pgpro/sqlancer/target
echo "[+] Start sqlancer..."
java -jar sqlancer-*.jar --host localhost --username postgres --port 5432 postgres > /opt/pgpro/sqlancer/target/logs/sqlancer.log
echo "[+] Find a logfile with crash query"
file=$(python3 /opt/pgpro/find_state.py)
echo "[+] Now you can repeat the crash with psql and ${file}" > /opt/pgpro/sqlancer/target/logs/crash.log
echo "[+] Command is 'psql -U postgres -e -f ${file} -o psql.out'" > /opt/pgpro/sqlancer/target/logs/crash.log
cd /opt/src
make coverage-html && cp -r coverage /opt/share/coverage2
cp /opt/pgpro/logfile /opt/share/logfile
cp -r /opt/pgpro/sqlancer/target/logs /opt/share/sqlancer_logs
gdb -q --command=/opt/pgpro/gdb_commands -c /opt/core* /opt/pgpro/bin/postgres > /opt/share/trace.txt
cp /opt/core* /opt/share/
cd /opt
tar -zcf /opt/artefacts.tar.gz --directory=/opt/share .