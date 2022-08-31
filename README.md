# Acknowledgements

This tool could not be made without great tools [sqlancer](https://github.com/sqlancer/sqlancer) and [squirrel](https://github.com/s3team/Squirrel).

# Why

Generational fuzzing automatization for postgresql

- Squirrel - afl wih custom sql [mutator](https://github.com/s3team/Squirrel). 
- sqlancer - multiprocess sql queries [generator](https://github.com/sqlancer/sqlancer)

Try to find bugs in new versions of postgres.

# How it works

For this project you just need to clone or fork original postgresql project.

This tool takes a pg repo, grabs all branches listed in settings, build containers ready for fuzzing and starts them.

For squirrel timeout flag was made. This flag actually is not needed, but if you have no crashes with your corpus, you need to stop fuzzing automatically. In the end you'll get afl++ logs and server logfile an tar archive from container.

By my observations sqlancer was more efficient the squirrel. When the query crashes the server we collect: 
 - query itself
 - unique state, which led to crash (sequence of queries)
 - postgres process dump
 - backtrace for postgres process
 - postgres logfile

sqlancer has no timeout flag. By my observations all sqlancer processes termiate themselfs. If this haven't happen you should just go to sqlancer container and kill java process. After that all artefacts would generate automatically.

## How to start

Clone postgres repo:

`git clone https://github.com/postgres/postgres.git`

Tune the tool:
```
BasePath: AbsPath to this tool
ArtefactsPath: AbsPath to artefacts location (owned by root:root)
SquirrelTimeout: Timeout for squirrel in seconds
CheckTimeout: Timeout for artefacts checking in seconds
Email:
  senderlogin: email bot which sends results to email
  senderpassword: email bot pass
  receivers: email recievers (separeted with a comma without spaces)
  smtp: email smtp server
  port: email smpt port
PostgresSettings:
  IsGit: true - pointer to git repo
  Branches: - branches and versions mapping.
    REL_14_STABLE: 14
  PostgresSource: path to postgres cloned directory
```

After tunning just run `start.sh` in background. This script would make an env, build images and start containers with parameters specified in settings. for example - `nohup ./start.sh &> /dev/null &`. If any errors occured You can check tool log `fuzz.log`.