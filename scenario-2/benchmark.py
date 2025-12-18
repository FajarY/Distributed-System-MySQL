import mysql.connector
import time
import threading

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
        return mysql.connector.connect(**config)
    except Exception as e:
        print(f"Failed to connect to {node_host} ({nodes[node_host]['nodename']}): {e}")
        return None

def check_cluster_status():
    for key, val in nodes.items():
        try:
            connection = create_connection(key)
            cursor = connection.cursor(dictionary=True)

            query = """
            SELECT MEMBER_HOST, MEMBER_STATE, MEMBER_ROLE FROM performance_schema.replication_group_members
            WHERE MEMBER_STATE="ONLINE" AND MEMBER_ROLE="PRIMARY"
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            cursor.close()
            connection.close()

            for row in rows:
                if(row["MEMBER_ROLE"] == "PRIMARY"):
                    return row["MEMBER_HOST"], rows
            
        except Exception as e:
            print(f"Failed to check current primary on connection {key}, {e}")
            pass
    return None

last_failed_host = None
last_failed_insert_time = None

def run_continous_insert():
    global last_failed_host, last_failed_insert_time
    
    insert_data = []
    for i in range(10):
        insert_data.append((f"Data batch replicate {i}",))

    last_total = 0

    while True:
        status = check_cluster_status()

        try:
            if(status == None):
                raise Exception("There was a problem when trying to insert data, checking cluster status returns None")

            primary_host, rows = status
            print(f"Current primary is {primary_host}, trying to insert {len(insert_data)} rows")
            
            connection = create_connection(primary_host)
            cursor = connection.cursor()

            query = """
            INSERT INTO main_table(data) VALUES (%s)
            """

            cursor.executemany(query, insert_data)
            connection.commit()

            count_query = """
            SELECT COUNT(*) as total FROM main_table;
            """
            cursor.execute(count_query)
            result = cursor.fetchone()
            total_rows = result[0]

            print(f"Insert to primary {primary_host} success, current total in primary database {total_rows}")
            last_total = total_rows

            cursor.close()
            connection.close()

            if(last_failed_host == primary_host):
                last_failed_host = None
                last_failed_insert_time = None

        except Exception as e:
            if(status != None and last_failed_host == None):
                primary_host, rows = status
                last_failed_host = primary_host
                last_failed_insert_time = time.time()

            print(f"Failed when continous inserting operation to primary, {e}")
            pass

        try:
            if(status == None):
                raise Exception("There was a problem when checking replication sync, status of cluster is none")
            
            primary_host, rows = status
            print(f"Checking syncronization for {len(rows)} databases")

            failed_check = dict()
            completed_check = dict()
            start_time = time.time()

            target_count_check = len(rows)

            while(target_count_check > (len(failed_check) + len(completed_check))):
                for row in rows:
                    try:
                        if(row["MEMBER_ROLE"] == "PRIMARY" or row["MEMBER_HOST"] in completed_check or row["MEMBER_HOST"] in failed_check):
                            continue

                        connection = create_connection(row["MEMBER_HOST"])
                        cursor = connection.cursor()

                        count_query = """
                        SELECT COUNT(*) as total FROM main_table;
                        """
                        cursor.execute(count_query)
                        result = cursor.fetchone()
                        total_rows = result[0]

                        latency = time.time() - start_time
                        print(f"Replica {row["MEMBER_HOST"]} has syncronized about {total_rows}/{last_total} rows from primary, ms from last insert : {latency}")

                        if(total_rows == last_total):
                            completed_check.add(row["MEMBER_HOST"], {
                                "latency": latency,
                            })

                        cursor.close()
                        connection.close()

                    except Exception as e:
                        print(f"There was a problem when checksumming on replica {row["MEMBER_HOST"]}, {e}")
                        latency = time.time() - start_time
                        failed_check.add(row["MEMBER_HOST"], {
                            "latency": latency,
                        })

            total_fail_latency = 0
            max_fail_latency = 0
            for key, val in completed_check:
                print(f"Node {key} failed, with latency {val["latency"]}")
                total_fail_latency += val["latency"]
                max_fail_latency = max(max_fail_latency, val["latency"]);
            
            if(len(failed_check) > 0):
                print(f"Failed syncronization count: {len(failed_check)}, avg ms {total_fail_latency / len(failed_check)}, max ms {max_fail_latency}")

            total_success_latency = 0
            max_success_latency = 0
            for key, val in completed_check:
                print(f"Node {key} success, with latency {val["latency"]}")
                total_success_latency += val["latency"]
                max_success_latency = max(max_success_latency, val["latency"]);
            
            if(len(completed_check) > 0):
                print(f"Success syncronization count: {len(completed_check)}, avg ms {total_success_latency / len(completed_check)}, max ms {max_success_latency}")

        except Exception as e:
            print(f"Failed when checking continous replica syncronization {e}")

        time.sleep(1)

def failover_check():
    global last_failed_host, last_failed_insert_time
    last_replication_count = None

    while True:
        try:
            status = check_cluster_status()

            if(status == None):
                raise Exception("There was a problem when checking cluster status, returns None")
            
            primary_host, rows = status
            if(last_replication_count == None):
                last_replication_count = len(rows)

            if(last_replication_count != len(rows)):
                print(f"There was a change of members in the group, from {last_replication_count} to {len(rows)}")
                last_replication_count = len(rows)

            if(last_failed_host == None):
                time.sleep(1)
                continue

            if(primary_host != last_failed_host):
                print(f"Detected failover on node {last_failed_host}, failover time is {time.time() - last_failed_insert_time}, and the new primary node is {primary_host}")

                last_failed_insert_time = None
                last_failed_host = None

            time.sleep(0.5)

        except Exception as e:
            print(f"Failed when checking failover {e}")

if __name__ == "__main__":
    insert_check_thread = threading.Thread(target=run_continous_insert)
    insert_check_thread.start()

    failover_check_thread = threading.Thread(target=failover_check)
    failover_check_thread.start()

    insert_check_thread.join()
    failover_check_thread.join()