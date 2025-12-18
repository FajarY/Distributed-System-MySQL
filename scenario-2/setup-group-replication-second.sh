#!/bin/bash

apt-get update -y
apt-get install mysql-server -y

cat << EOF | tee /etc/mysql/my.cnf
#
# The MySQL database server configuration file.
#
# You can copy this to one of:
# - "/etc/mysql/my.cnf" to set global options,
# - "~/.my.cnf" to set user-specific options.
#
# One can use all long options that the program supports.
# Run program with --help to get a list of available options and with
# --print-defaults to see which it would actually understand and use.
#
# For explanations see
# http://dev.mysql.com/doc/mysql/en/server-system-variables.html

#
# * IMPORTANT: Additional settings that can override those from this file!
#   The files must end with '.cnf', otherwise they'll be ignored.
#

!includedir /etc/mysql/conf.d/
!includedir /etc/mysql/mysql.conf.d/

[mysqld]

# General replication settings
disabled_storage_engines="MyISAM,BLACKHOLE,FEDERATED,ARCHIVE,MEMORY"
gtid_mode = ON
enforce_gtid_consistency = ON
master_info_repository = TABLE
relay_log_info_repository = TABLE
binlog_checksum = NONE
log_slave_updates = ON
log_bin = binlog
binlog_format = ROW
transaction_write_set_extraction = XXHASH64
loose-group_replication_bootstrap_group = OFF
loose-group_replication_start_on_boot = OFF
loose-group_replication_ssl_mode = DISABLED
loose-group_replication_recovery_use_ssl = 0
loose-group_replication_single_primary_mode = ON
loose-group_replication_enforce_update_everywhere_checks = OFF

# Shared replication group configuration
loose-group_replication_group_name = "8f6aa414-8097-4809-b209-db7bd286d347"
loose-group_replication_ip_allowlist = "0.0.0.0/0"
loose-group_replication_group_seeds = "192.168.100.2:33061,192.168.100.3:33061,192.168.100.4:33061"

# Host specific replication configuration
server_id = 2
bind-address = "0.0.0.0"
report_host = "192.168.100.3"
loose-group_replication_local_address = "192.168.100.3:33061"
EOF

service mysql restart

mysql -u root << EOF
SET SQL_LOG_BIN=0;
CREATE USER 'repl'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT REPLICATION SLAVE ON *.* TO 'repl'@'%';
FLUSH PRIVILEGES;
SET SQL_LOG_BIN=1;

CHANGE REPLICATION SOURCE TO SOURCE_USER='repl', SOURCE_PASSWORD='password' FOR CHANNEL 'group_replication_recovery';

INSTALL PLUGIN group_replication SONAME 'group_replication.so';
SHOW PLUGINS;

START GROUP_REPLICATION;

SELECT * FROM performance_schema.replication_group_members;
SHOW STATUS LIKE '%primary%';

SELECT * FROM testing.main_table;
EOF