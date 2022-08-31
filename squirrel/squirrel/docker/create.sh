#!/bin/bash
/opt/pgpro/bin/postgres --single -D /opt/data << EOF
create database x
EOF
