#!/bin/bash
AFL_MAP_SIZE=$(cat /tmp/mapsize) python3 run.py postgresql /home/squirrel/data/fuzz_root/pqsql_input/
