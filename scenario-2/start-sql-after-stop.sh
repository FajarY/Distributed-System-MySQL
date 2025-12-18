#!/bin/bash

service mysql start

mysql -u root << EOF
START GROUP_REPLICATION;
EOF