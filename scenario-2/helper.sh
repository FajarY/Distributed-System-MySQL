mysql -u root << EOF
SELECT MEMBER_HOST, MEMBER_STATE FROM performance_schema.replication_group_members;
EOF

mysql -u root << EOF
INSERT INTO testing.main_table(data) VALUES ("Insert testing");
EOF

mysql -u root << EOF
START GROUP_REPLICATION;
EOF

mysql -u root << EOF
SET GLOBAL group_replication_bootstrap_group=ON;
START GROUP_REPLICATION;
SET GLOBAL group_replication_bootstrap_group=OFF;
EOF

mysql -u root << EOF
STOP GROUP_REPLICATION;
EOF

mysql -u root << EOF
CREATE USER 'node'@'%' IDENTIFIED WITH mysql_native_password BY 'password';
GRANT ALL PRIVILEGES ON *.* TO 'node'@'%' WITH GRANT OPTION;
EOF