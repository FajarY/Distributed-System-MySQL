#!/bin/bash

cat <<EOF > /etc/mysql/my.cnf
[mysqld]
server-id=1
log-bin=mysql-bin
binlog-format=ROW
gtid_mode=ON
enforce_gtid_consistency=ON
bind-address=0.0.0.0
EOF

service mysql restart

mysql -u root <<EOF
DROP USER IF EXISTS 'repl_user'@'%';
CREATE USER 'repl_user'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT REPLICATION SLAVE ON *.* TO 'repl_user'@'%';

DROP USER IF EXISTS 'root'@'%';
CREATE USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;

FLUSH PRIVILEGES;
EOF

echo "Primary Ready. Server ID: 1"
