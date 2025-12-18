#!/bin/bash

touch /etc/mysql/my.cnf
cat <<EOF > /etc/mysql/my.cnf
[mysqld]
server-id=2
relay-log=relay-bin
read_only=ON
gtid_mode=ON
enforce_gtid_consistency=ON
bind-address=0.0.0.0
EOF

service mysql restart

mysql -u root <<EOF
DROP USER IF EXISTS 'root'@'%';
CREATE USER 'root'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT ALL PRIVILEGES ON *.* TO 'root'@'%' WITH GRANT OPTION;
FLUSH PRIVILEGES;
EOF

mysql -u root -p'password' -e "STOP SLAVE; RESET MASTER;"
mysql -u root -p'password' -e "CHANGE MASTER TO \
    MASTER_HOST='192.168.100.2', \
    MASTER_USER='repl_user', \
    MASTER_PASSWORD='password', \
    MASTER_AUTO_POSITION=1, \
    GET_MASTER_PUBLIC_KEY=1;"
mysql -u root -p'password' -e "START SLAVE;"

echo "Replica 1 Ready (Server ID: 2)"