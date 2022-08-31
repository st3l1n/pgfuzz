import os

prefix = '/opt/postgres/sqlancer/target/logs/postgres/'
query = os.popen('grep -ih "Failed process was running:" /opt/postgres/logfile').read().split("Failed process was running: ")[-1].strip()
if query:
    valid_logs = list([prefix+log for log in os.listdir(prefix)])
    for log in valid_logs:
        with open(log, 'rt') as l:
            if query in l.read():
                print(log)
                break
    with open('/opt/share/crash_query.log', 'w') as fp:
        fp.write(query)
else:
    print("Didn't find any crash bugs =(")