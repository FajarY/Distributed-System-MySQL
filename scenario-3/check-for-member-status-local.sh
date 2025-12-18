#!/bin/bash

while true; do
    echo "MySQL Group Replication Local Status - $(date)"
    mysql -u root << EOF
    SELECT MEMBER_HOST, MEMBER_STATE, MEMBER_ROLE FROM performance_schema.replication_group_members
EOF
    echo ""

    sleep 0.5
done