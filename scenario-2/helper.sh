mysql -u root << EOF
SELECT MEMBER_HOST, MEMBER_STATE FROM performance_schema.replication_group_members;
EOF

mysql -u root << EOF
INSERT INTO testing.main_table(data) VALUES ("Insert testing");
EOF