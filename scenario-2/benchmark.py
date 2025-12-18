import mysql.connector
import time
import threading
import concurrent.futures
import random
import string

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
            "database": config["database"]
        }
        return mysql.connector.connect(**config_pruned)
    except Exception as e:
        raise e

def check_cluster_status():
    for key, val in nodes.items():
        try:
            connection = create_connection(key)
            cursor = connection.cursor(dictionary=True)

            query = """
            SELECT MEMBER_HOST, MEMBER_STATE, MEMBER_ROLE FROM performance_schema.replication_group_members
            """

            cursor.execute(query)
            rows = cursor.fetchall()

            cursor.close()
            connection.close()

            for row in rows:
                if(row["MEMBER_ROLE"] == "PRIMARY"):
                    return row["MEMBER_HOST"], rows
            
        except Exception as e:
            # info(f"Failed to check current primary on connection {key}, {e}")
            pass
    return None

last_success_host = None
last_failed_host = None
last_failed_insert_time = None
target_check_count = 0

def check_replication_execute(row, start_time):
    try:
        while True:
            connection = create_connection(row["MEMBER_HOST"])
            cursor = connection.cursor()

            query = """
            SELECT COUNT(*) as total FROM main_table;
            """

            cursor.execute(query)
            result = cursor.fetchone()
            total_rows = result[0]

            delay_time = time.time() - start_time

            info(f"Replication {row['MEMBER_HOST']} has syncronized {total_rows}/{target_check_count}, with delay {delay_time} seconds")

            if(total_rows >= target_check_count):
                return {
                    "host": row["MEMBER_HOST"],
                    "latency": delay_time,
                    "status": "success"
                }

    except Exception as e:
        info(f"Failed when checking for replication syncronize status {e}")
    
    return {
        "host": row["MEMBER_HOST"],
        "latency": time.time() - start_time,
        "status": "failed"
    }

def check_for_replication(rows):
    checks = []
    executor = concurrent.futures.ThreadPoolExecutor(max_workers=2)

    for row in rows:
        if(row["MEMBER_ROLE"] == "PRIMARY"):
            continue

        future = executor.submit(check_replication_execute, row, time.time())
        checks.append(future)

    return checks

def run_continous_insert():
    global last_failed_host, last_failed_insert_time, target_check_count, last_success_host

    last_total = 0

    while True:
        insert_data = []
        for i in range(1000):
            insert_data.append((generate_random_string(512),))

        status = check_cluster_status()
        checking = None

        try:
            if(status == None):
                raise Exception("There was a problem when trying to insert data, checking cluster status returns None")

            primary_host, rows = status
            info(f"Current primary is {primary_host}, trying to insert {len(insert_data)} rows")

            transaction_check_start_time = time.time()
            transaction_total_time = 0

            connection = create_connection(primary_host)
            cursor = connection.cursor()

            query = """
            INSERT INTO main_table(data) VALUES (%s)
            """

            cursor.executemany(query, insert_data)
            transaction_total_time += time.time() - transaction_check_start_time

            count_query = """
            SELECT COUNT(*) as total FROM main_table;
            """
            cursor.execute(count_query)
            result = cursor.fetchone()
            total_rows = result[0]

            target_check_count = total_rows
            info(f"Insert to primary {primary_host} success, current total in primary database {total_rows}")

            checking = check_for_replication(rows)

            transaction_check_start_time = time.time()
            connection.commit()
            transaction_total_time += time.time() - transaction_check_start_time
            info(f"Insert to primary {primary_host} transaction succeded in {transaction_total_time} seconds")

            last_total = total_rows

            cursor.close()
            connection.close()

            if(last_failed_host == primary_host):
                last_failed_host = None
                last_failed_insert_time = None

                failover(f"Failover beginning cleared for {last_failed_host}, last time may just a slight network error")
            
            if(last_success_host == None):
                last_success_host = primary_host

            if(last_success_host != primary_host):
                failover(f"Failover instantly cleared for {last_success_host}, the new primary is {primary_host}")
                last_success_host = primary_host

        except Exception as e:
            target_check_count = last_total

            if(status != None and last_failed_host == None):
                primary_host, rows = status
                last_failed_host = primary_host
                last_failed_insert_time = time.time()

                failover(f"Detected failover beginning for {last_failed_host}")

            info(f"Failed when continous inserting operation to primary, {e}")
            pass

        if(checking != None):
            total_success_count = 0
            total_failure_count = 0

            total_success_time = 0
            total_failure_time = 0
            max_success_time = 0
            max_failure_time = 0

            for future in checking:
                future_val = future.result()

                if(future_val["status"] == 'success'):
                    total_success_time += future_val['latency']
                    info(f"Replication {future_val['host']} succesfully get the replication with delay {future_val['latency']}")
                    total_success_count += 1
                    max_success_time = max(max_success_time, future_val['latency'])

                elif(future_val["status"] == 'failed'):
                    total_failure_time += future_val['latency']
                    info(f"Replication {future_val['host']} failed to get the replication with delay {future_val['latency']}")
                    total_failure_count += 1
                    max_failure_time = max(max_failure_time, future_val['latency'])

            if(total_success_count > 0):
                info(f"Success count {total_success_count}, avg {total_success_time / total_success_count}, max {max_success_time} seconds")

            if(total_failure_count > 0):
                info(f"Failure count {total_failure_count}, avg {total_failure_time / total_failure_count}, max {max_failure_time} seconds")

        time.sleep(1)

def failover_check():
    global last_failed_host, last_failed_insert_time, last_success_host
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
                warning(f"There was a change of members in the group, from {last_replication_count} to {len(rows)}")
                last_replication_count = len(rows)

            if(last_failed_host == None):
                time.sleep(1)
                continue

            if(primary_host != last_failed_host):
                failover(f"Detected failover on node {last_failed_host}, failover time is {time.time() - last_failed_insert_time}, and the new primary node is {primary_host}")

                last_success_host = None
                last_failed_insert_time = None
                last_failed_host = None

        except Exception as e:
            failover(f"Failed when checking failover {e}")

        time.sleep(0.5)

if __name__ == "__main__":
    insert_check_thread = threading.Thread(target=run_continous_insert)
    insert_check_thread.start()

    failover_check_thread = threading.Thread(target=failover_check)
    failover_check_thread.start()

    insert_check_thread.join()
    failover_check_thread.join()