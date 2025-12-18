import mysql.connector
from mysql.connector import Error

nodes = {
    "node1": {
        "user": "root",
        "password": "password",
        "host": "192.168.100.2",
        "port": 3306,
        "database": "testing"
    },
    "node2": {
        "user": "root",
        "password": "password",
        "host": "192.168.100.3",
        "port": 3306,
        "database": "testing"
    },
    "node3": {
        "user": "root",
        "password": "password",
        "host": "192.168.100.4",
        "port": 3306,
        "database": "testing"
    }
}

def create_connection(node_name):
    try:
        config = nodes[node_name]
        return mysql.connector.connect(**config)
    except Error as e:
        print(f"Gagal koneksi ke {node_name} ({nodes[node_name]['host']}): {e}")
        return None

def check_current_primary():
    for key, val in nodes.items():
        try:
            connection = create_connection(key)
            cursor = connection.cursor(dictionary=True)

            query = """
            SELECT MEMBER_HOST, MEMBER_STATE, MEMBER_ROLE FROM performance_schema.replication_group_members;
            WHERE MEMBER_ROLE="PRIMARY";
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            print(rows)

            if(len(rows) >= 1):
                return rows[0]["MEMBER_HOST"]
            
            cursor.close()
            connection.close()
        except:
            pass
    return None


if __name__ == "__main__":
    print(check_current_primary())