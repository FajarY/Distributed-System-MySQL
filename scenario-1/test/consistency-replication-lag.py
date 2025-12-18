import mysql.connector
import time
import concurrent.futures
import random
import string

nodes = {
    'primary':  {'host': '192.168.100.2', 'name': 'Primary'},
    'replica1': {'host': '192.168.100.3', 'name': 'Replica 1'},
    'replica2': {'host': '192.168.100.4', 'name': 'Replica 2'}
}

DB_NAME = "testing"
TABLE_NAME = "main_table"
TOTAL_ROWS = 1000

def generate_random_string(n):
    characters = string.ascii_letters + string.digits
    result = ''.join(random.choices(characters, k=n))
    
    return result

def get_connection(host_ip):
    try:
        return mysql.connector.connect(
            host=host_ip,
            user="root",
            password="password",
            auth_plugin='mysql_native_password',
            autocommit=True,
            connection_timeout=5
        )
    except mysql.connector.Error:
        return None

def setup_database():
    print("[SETUP] Preparing Database Environment...")
    p_conn = get_connection(nodes['primary']['host'])
    if not p_conn:
        print("FATAL: Cannot connect to Primary")
        return False

    cursor = p_conn.cursor()
    cursor.execute(f"DROP DATABASE IF EXISTS {DB_NAME}")
    cursor.execute(f"CREATE DATABASE {DB_NAME}")
    cursor.execute(f"USE {DB_NAME}")
    cursor.execute(f"CREATE TABLE {TABLE_NAME} (id INT AUTO_INCREMENT PRIMARY KEY, data TEXT)")
    
    time.sleep(2)
    p_conn.close()
    return True

def check_replication_execute(node_key, start_time):
    host = nodes[node_key]['host']
    
    try:
        connection = None
        for _ in range(3):
            connection = get_connection(host)
            if connection: break
            time.sleep(1)

        if not connection:
             return {
                "key": node_key,
                "latency": -999,
                "count": 0,
                "read_status": "CONN_FAIL",
                "status": "failed"
            }

        cursor = connection.cursor()
        cursor.execute(f"USE {DB_NAME}")
        
        timeout_start = time.time()
        attempt = 0 
        first_read_status = "UNKNOWN"

        while (time.time() - timeout_start) < 10:
            attempt += 1 
            
            connection.commit() 

            cursor.execute(f"SELECT COUNT(*) as total FROM {TABLE_NAME};")
            total_rows = cursor.fetchone()[0]

            if attempt == 1:
                if total_rows >= TOTAL_ROWS:
                    first_read_status = "CONSISTENT"
                else:
                    first_read_status = "INCONSISTENT" 

            delay_time = time.time() - start_time
            if delay_time < 0: 
                delay_time = 0

            if total_rows >= TOTAL_ROWS:
                cursor.close()
                connection.close()
                return {
                    "key": node_key,
                    "latency": delay_time * 1000,
                    "count": total_rows,
                    "read_status": first_read_status, 
                    "status": "success"
                }
            
            time.sleep(0.005)

        cursor.close()
        connection.close()

    except Exception as e:
        print(f"Error on {node_key}: {e}")
    
    return {
        "key": node_key,
        "latency": None,
        "count": 0,
        "read_status": "TIMEOUT",
        "status": "failed"
    }

def run():
    if not setup_database():
        return

    print(f"[SCENARIO 1] Inserting {TOTAL_ROWS} rows. Measuring Lag & Consistency.")

    p_conn = get_connection(nodes['primary']['host'])
    cursor = p_conn.cursor()
    cursor.execute(f"USE {DB_NAME}")

    print("[SCENARIO 1] Starting Workload on Primary...")
    
    workload_start = time.time()
    
    sql = f"INSERT INTO {TABLE_NAME} (data) VALUES (%s)"
    val = [(generate_random_string(512),) for _ in range(TOTAL_ROWS)]

    cursor.executemany(sql, val)
        
    p_conn.commit()
    workload_end = time.time()
    
    print(f"[SCENARIO 1] Workload Complete. Time taken: {(workload_end - workload_start):.4f}s")
    
    print("[SCENARIO 1] Checking Replicas...")
    
    futures = []
    results = {} 

    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
        f1 = executor.submit(check_replication_execute, 'replica1', workload_end)
        f2 = executor.submit(check_replication_execute, 'replica2', workload_end)
        
        futures = [f1, f2]
        
        for future in concurrent.futures.as_completed(futures):
            res = future.result()
            results[res['key']] = res

    cursor.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}")
    primary_count = cursor.fetchone()[0]
    p_conn.close()

    tx_latency = (workload_end - workload_start) * 1000
    
    print(f"\n{'METRIC':<25} | {'PRIMARY':<18} | {'REPLICA 1':<18} | {'REPLICA 2':<18}")
    print("-" * 85)
    print(f"{'Tx Latency (Total)':<25} | {f'{tx_latency:.2f} ms':<18} | {'-':<18} | {'-':<18}")
    
    def fmt_lag(val):
        if val is None: return "TIMEOUT"
        if val == -999: return "CONN FAIL"
        return f"{val:.2f} ms"

    r1_lag = results.get('replica1', {}).get('latency')
    r2_lag = results.get('replica2', {}).get('latency')
    
    r1_count = results.get('replica1', {}).get('count', 0)
    r2_count = results.get('replica2', {}).get('count', 0)

    r1_status = results.get('replica1', {}).get('read_status', '-')
    r2_status = results.get('replica2', {}).get('read_status', '-')
    
    print(f"{'Replication Lag':<25} | {'-':<18} | {fmt_lag(r1_lag):<18} | {fmt_lag(r2_lag):<18}")
    print(f"{'Row Count':<25} | {str(primary_count):<18} | {str(r1_count):<18} | {str(r2_count):<18}") 
    print(f"{'First Read Status':<25} | {'CONSISTENT':<18} | {r1_status:<18} | {r2_status:<18}")
    
    print("-" * 85)
    print(f"FINAL STATE: {'EVENTUALLY CONSISTENT' if (primary_count == r1_count == r2_count) else 'DATA LOSS / SYNC FAIL'}")

if __name__ == "__main__":
    run()