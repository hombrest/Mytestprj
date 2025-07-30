import pyodbc
import subprocess
import time
import threading
from datetime import datetime, timedelta
import os
import psutil

# SQL Server configuration
DB_CONFIG = {
    'server': 'WIN-SERVER01',
    'database': 'master',
    'user': 'sa',
    'password': 'Mima!@#2022',
    'driver': 'SQL Server'
}

# Constants
CHECK_INTERVAL = 10  # seconds
TIMEOUT_LIMIT = 60  # seconds


def get_db_connection():
    """Create and return a new database connection"""
    conn_str = f"DRIVER={DB_CONFIG['driver']};SERVER={DB_CONFIG['server']};DATABASE={DB_CONFIG['database']};UID={DB_CONFIG['user']};PWD={DB_CONFIG['password']}"
    return pyodbc.connect(conn_str)

def verify_connection():
    try:
        conn = get_db_connection()
        print("✔ Connection successful")
        conn.close()
        return True
    except Exception as e:
        print(f"✖ Connection failed: {e}")
        return False

def get_next_job():
    """Get the next job with the least sequence number and status NULL"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Start transaction
        # Add this before your SELECT statements
        cursor.execute("BEGIN TRANSACTION")

        # Find the next available job
        query = """
        SELECT TOP 1 * FROM job_table 
        WHERE job_status IS NULL 
        ORDER BY job_sequence ASC
        """
        cursor.execute(query)
        columns = [column[0] for column in cursor.description]
        # job = dict(zip(columns, cursor.fetchone())) if cursor.rowcount > 0 else None
        for row in cursor:
            job = dict(zip(columns, row))  # Convert to dictionary
            print(job['job_command'])  # Access by name

            if job:
                # Update the job status to "Running"
                update_query = """
                UPDATE job_table 
                SET job_status = 'Running', 
                    job_start_time = GETDATE(), 
                    job_runner = ?,
                    job_last_update = GETDATE()
                WHERE job_id = ?
                """
                cursor.execute(update_query, (os.getpid(), job['job_id']))
                conn.commit()
                return job
            else:
                conn.commit()
                return None
    except Exception as e:
        conn.rollback()
        raise e
    finally:
        cursor.close()
        conn.close()


def update_job_status(job_id, status, error=None):
    """Update the job status in the database"""
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        query = """
        UPDATE job_table 
        SET job_status = ?, 
            job_end_time = GETDATE(),
            job_last_update = GETDATE()
        WHERE job_id = ?
        """
        cursor.execute(query, (status, job_id))
        conn.commit()
    except Exception as e:
        print(f"Error updating job status: {e}")
        conn.rollback()
    finally:
        cursor.close()
        conn.close()


def execute_job(command):
    """Execute the job command in a subprocess"""
    try:
        # Use shell=True for Windows to handle commands properly
        process = subprocess.Popen(
            command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        return process
    except Exception as e:
        print(f"Error starting job: {e}")
        return None


def monitor_job(job_id, process):
    """Monitor the job process and update status accordingly"""
    start_time = datetime.now()
    timeout_reached = False

    while True:
        # Check if process has completed
        return_code = process.poll()

        if return_code is not None:
            # Process has completed
            if return_code == 0:
                update_job_status(job_id, "Completed")
            else:
                update_job_status(job_id, "Failed")
            break

        # Check for timeout
        elapsed_time = (datetime.now() - start_time).total_seconds()
        if elapsed_time > TIMEOUT_LIMIT and not timeout_reached:
            timeout_reached = True
            # Terminate the process
            try:
                parent = psutil.Process(process.pid)
                for child in parent.children(recursive=True):
                    child.kill()
                parent.kill()
                update_job_status(job_id, "Timeout")
            except Exception as e:
                print(f"Error terminating process: {e}")
                update_job_status(job_id, "Error")
            break

        # Wait before checking again
        time.sleep(CHECK_INTERVAL)


def process_jobs():
    """Main function to process all jobs"""
    while True:
        job = get_next_job()
        if not job:
            print("No more jobs to process.")
            break

        print(f"Processing job ID {job['job_id']} with command: {job['job_command']}")
        process = execute_job(job['job_command'])

        if process:
            # Start a thread to monitor the job
            monitor_thread = threading.Thread(
                target=monitor_job,
                args=(job['job_id'], process)
            )
            monitor_thread.start()

            # Wait for the monitoring to complete before moving to next job
            monitor_thread.join()
        else:
            update_job_status(job['job_id'], "Failed")


def check_table_exists():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # Check if table exists
        cursor.execute("""
                       SELECT *
                       FROM INFORMATION_SCHEMA.TABLES
                       WHERE TABLE_NAME = 'job_table'
                       """)

        if cursor.fetchone():
            print("✔ Table exists")

            # Check columns
            cursor.execute("""
                           SELECT COLUMN_NAME, DATA_TYPE
                           FROM INFORMATION_SCHEMA.COLUMNS
                           WHERE TABLE_NAME = 'job_table'
                           """)
            print("\nTable columns:")
            for row in cursor:
                print(f"- {row.COLUMN_NAME}: {row.DATA_TYPE}")
        else:
            print("✖ Table doesn't exist")

        conn.close()
    except Exception as e:
        print(f"Error checking table: {e}")


def retrieve_jobs():
    try:

        conn = get_db_connection()
        cursor = conn.cursor()

        print("\nAttempting to retrieve jobs...")

        # Method 1: Basic fetch
        cursor.execute("SELECT * FROM job_table")
        rows = cursor.fetchall()

        if not rows:
            print("No rows found in job_table")
        else:
            print(f"Found {len(rows)} jobs:")
            for row in rows:
                print(f"ID: {row.job_id}, Command: {row.job_command}")

        # Method 2: Dictionary cursor (more readable)
        print("\nAlternative method with column names:")
        cursor.execute("SELECT * FROM job_table")
        columns = [column[0] for column in cursor.description]

        for row in cursor.fetchall():
            job = dict(zip(columns, row))
            print(f"Job {job['job_id']}: {job['job_command']} (Status: {job['job_status']})")

        conn.close()

    except pyodbc.Error as e:
        print(f"Database error: {e}")
    except Exception as e:
        print(f"General error: {e}")


def get_jobs():
    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Execute query
        cursor.execute("SELECT * FROM job_table")

        # Verify we got results
        if cursor.description is None:
            print("Query returned no results (cursor.description is None)")
            return

        # Method 1: Fetch all rows at once
        rows = cursor.fetchall()
        print(f"Found {len(rows)} rows")
        for row in rows:
            print(row)  # Access as tuple

        # Method 2: Fetch one by one (better for large results)
        cursor.execute("SELECT * FROM job_table")  # Re-execute
        while True:
            row = cursor.fetchone()
            if row is None:
                break
            print(f"Job ID: {row.job_id}, Command: {row.job_command}")

    except pyodbc.Error as e:
        print(f"Database error: {str(e)}")
    finally:
        cursor.close()
        conn.close()

if __name__ == "__main__":
    # verify_connection()
    # check_table_exists()
    # retrieve_jobs()
    get_jobs()
    print("Starting job processor...")
    process_jobs()
    print("Job processing completed.")