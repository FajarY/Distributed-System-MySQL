import mysql.connector
import time
import random
import string
import sys

def generate_random_string(n):
    characters = string.ascii_letters + string.digits
    result = ''.join(random.choices(characters, k=n))
    
    return result

def info(str):
    print(f"[INFO] {str}")

def failover(str):
    print(f"[FAILOVER] {str}")

def warning(str):
    print(f"[WARNING] {str}")

local_ip = None
nodes = {
    "192.168.100.2": {
        "nodename": "node1",
        "user": "root",
        "password": "password",
        "host": "192.168.100.2",
        "port": 3306,
        "database": "testing"
    },
    "192.168.100.3": {
        "nodename": "node2",
        "user": "root",
        "password": "password",
        "host": "192.168.100.3",
        "port": 3306,
        "database": "testing"
    },
    "192.168.100.4": {
        "nodename": "node3",
        "user": "root",
        "password": "password",
        "host": "192.168.100.4",
        "port": 3306,
        "database": "testing"
    }
}

def create_connection(node_host):
    try:
        config = nodes[node_host]
        config_pruned = {
            "user": config["user"],
            "password": config["password"],
            "host": config["host"],
            "port": config["port"],
            "database": config["database"],
            "connection_timeout": 2
        }
        return mysql.connector.connect(**config_pruned)
    except Exception as e:
        raise e
    
def create_local_connection():
    global local_ip
    try:
        config = nodes[local_ip]
        config_pruned = {
            "user": config["user"],
            "password": config["password"],
            "host": "127.0.0.1",
            "port": config["port"],
            "database": config["database"],
            "connection_timeout": 2,
            "auth_plugin": "mysql_native_password"
        }
        return mysql.connector.connect(**config_pruned)
    except Exception as e:
        raise e

lost_connection_start_time = None

def check_for_connectivity():
    global lost_connection_start_time, local_ip

    for key, val in nodes.items():
        try:
            if(key == local_ip):
                continue

            connection = create_connection(key)

            if(connection.is_connected() == False):
                raise Exception("Not connected")
            
            connection.close()
        except Exception as e:
            if(lost_connection_start_time == None):
                lost_connection_start_time = time.time()
                warning(f"Isolation detected, Lost connectivity to connect to {key}")

def is_still_primary():
    global lost_connection_start_time, local_ip

    try:
        connection = create_local_connection()
        cursor = connection.cursor(dictionary=True)

        query = """
        SELECT MEMBER_HOST, MEMBER_STATE, MEMBER_ROLE FROM performance_schema.replication_group_members
        """
        cursor.execute(query)
        rows = cursor.fetchall()

        cursor.close()
        connection.close()

        for row in rows:
            if(row["MEMBER_HOST"] == local_ip and row["MEMBER_ROLE"] == "PRIMARY"):
                return 1
            if(row["MEMBER_HOST"] == local_ip and row["MEMBER_STATE"] == "ERROR"):
                warning("Error detected for local node")
                return 2

    except Exception as e:
        info(f"There was an error when checking primary status {e}")
        return 0

    return 0

def try_write_to_db():
    global local_ip

    insert_data = []
    for i in range(1000):
        insert_data.append((generate_random_string(512),))

    try:
        connection = create_local_connection()
        cursor = connection.cursor()

        query = """
        INSERT INTO main_table(data) VALUES (%s)
        """

        cursor.executemany(query, insert_data)
        connection.commit()

        cursor.close()
        connection.close()
    except Exception as e:
        info(f"There was an error when creating local connection, {e}")
        pass

def run():
    global lost_connection_start_time, local_ip
    last_primary = True

    while True:
        check_for_connectivity()

        if(lost_connection_start_time != None):
            break

        info("Connectivity is still okay, node is still not isolated")
        time.sleep(0.5)

    while True:
        if(last_primary):
            if(is_still_primary() == 2):
                last_primary = False
                warning(f"Node is now not a primary after {time.time() - lost_connection_start_time}")

        try_write_to_db()
        time.sleep(0.5)

if __name__ == "__main__":
    if(len(sys.argv) <= 1):
        print("Usage is python3 isolate-run.py [LOCAL_ADDRESS]")
    else:
        local_ip = sys.argv[1]
        run()