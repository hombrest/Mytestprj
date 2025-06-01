import sqlite3
import tkinter as tk
from tkinter import ttk
from datetime import datetime
import json
import glob
import os

# Create and populate sample SQLite database
def create_sample_db():
    conn = sqlite3.connect('node_monitor.db')
    cursor = conn.cursor()
    
    # Create table with specified structure
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS nodes (
            node_name TEXT PRIMARY KEY,
            node_status TEXT NOT NULL,
            jobname TEXT,
            user TEXT,
            start_time TEXT,
            end_time TEXT,
            duration TEXT
        )
    ''')
    
    # Insert sample data with new structure, including running with jobname=None
    sample_data = [
        ('Node1', 'running', 'JobA', 'alice', '2025-06-01 08:00:00', '2025-06-01 08:15:30', '00:15:30'),
        ('Node2', 'down', 'JobB', 'bob', '2025-06-01 08:30:00', '2025-06-01 08:40:45', '00:10:45'),
        ('Node3', 'running', None, 'charlie', '2025-06-01 09:00:00', '2025-06-01 09:20:00', '00:20:00'),
        ('Node4', 'down', 'JobC', 'diana', '2025-06-01 09:15:00', '2025-06-01 09:20:20', '00:05:20')
    ]
    
    cursor.executemany('INSERT OR IGNORE INTO nodes VALUES (?, ?, ?, ?, ?, ?, ?)', sample_data)
    conn.commit()
    conn.close()

# Process JSON files from D:\Temp
def process_json_files():
    conn = sqlite3.connect('node_monitor.db')
    cursor = conn.cursor()
    
    # Get list of node*.json files in D:\Temp
    json_files = glob.glob(r'D:\Temp\node*.json')
    
    for json_file in json_files:
        try:
            with open(json_file, 'r') as f:
                data = json.load(f)
                
                # Extract fields, use None for optional fields if missing
                node_name = data.get('node_name')
                node_status = data.get('node_status', 'down')  # Default to 'down' if missing
                jobname = data.get('jobname')
                user = data.get('user')
                start_time = data.get('start_time')
                end_time = data.get('end_time')
                duration = data.get('duration')
                
                # Validate required fields
                if not node_name or not node_status:
                    continue
                
                # Check if node_name exists
                cursor.execute('SELECT node_name FROM nodes WHERE node_name = ?', (node_name,))
                exists = cursor.fetchone()
                
                if exists:
                    # Update existing record
                    cursor.execute('''
                        UPDATE nodes 
                        SET node_status = ?, jobname = ?, user = ?, start_time = ?, end_time = ?, duration = ?
                        WHERE node_name = ?
                    ''', (node_status, jobname, user, start_time, end_time, duration, node_name))
                else:
                    # Insert new record
                    cursor.execute('''
                        INSERT INTO nodes (node_name, node_status, jobname, user, start_time, end_time, duration)
                        VALUES (?, ?, ?, ?, ?, ?, ?)
                    ''', (node_name, node_status, jobname, user, start_time, end_time, duration))
        except (json.JSONDecodeError, FileNotFoundError, PermissionError):
            # Skip invalid or inaccessible files
            continue
    
    conn.commit()
    conn.close()

# Function to fetch data from database
def fetch_data():
    conn = sqlite3.connect('node_monitor.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM nodes')
    rows = cursor.fetchall()
    conn.close()
    return rows

# Create GUI
class DatabaseTableApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Node Status Viewer")
        self.root.geometry("900x450")  # Width for all columns

        # Auto-refresh variables
        self.auto_refresh_id = None
        self.auto_refresh_interval = 0  # In milliseconds

        # Create traffic light icons (small colored squares)
        self.green_icon = tk.PhotoImage(width=16, height=16)
        self.green_icon.put("green", to=(0, 0, 15, 15))
        self.red_icon = tk.PhotoImage(width=16, height=16)
        self.red_icon.put("red", to=(0, 0, 15, 15))
        self.yellow_icon = tk.PhotoImage(width=16, height=16)
        self.yellow_icon.put("yellow", to=(0, 0, 15, 15))

        # Create control frame
        control_frame = ttk.Frame(root)
        control_frame.pack(fill=tk.X, pady=5)

        # Refresh button
        ttk.Button(control_frame, text="Refresh Now", command=self.load_data).pack(side=tk.LEFT, padx=5)

        # Auto-refresh interval input
        ttk.Label(control_frame, text="Auto-refresh interval (seconds):").pack(side=tk.LEFT, padx=5)
        self.interval_entry = ttk.Entry(control_frame, width=5)
        self.interval_entry.pack(side=tk.LEFT, padx=5)
        self.interval_entry.insert(0, "0")  # Default: no auto-refresh

        # Set auto-refresh button
        ttk.Button(control_frame, text="Set Auto-refresh", command=self.set_auto_refresh).pack(side=tk.LEFT, padx=5)

        # Timestamp label
        self.timestamp_var = tk.StringVar()
        self.timestamp_var.set("Last fetched: N/A")
        ttk.Label(control_frame, textvariable=self.timestamp_var).pack(side=tk.LEFT, padx=5)

        # Create Treeview
        self.tree = ttk.Treeview(root, show="tree headings")  # Show both tree and headings
        self.tree["columns"] = ("Node Name", "Node Status", "Job Name", "User", "Start Time", "End Time", "Duration")
        
        # Format columns
        self.tree.column("#0", width=50, anchor=tk.CENTER)  # Icon column
        self.tree.column("Node Name", anchor=tk.W, width=120)
        self.tree.column("Node Status", anchor=tk.CENTER, width=100)
        self.tree.column("Job Name", anchor=tk.W, width=120)
        self.tree.column("User", anchor=tk.W, width=100)
        self.tree.column("Start Time", anchor=tk.W, width=150)
        self.tree.column("End Time", anchor=tk.W, width=150)
        self.tree.column("Duration", anchor=tk.W, width=100)
        
        # Create headings
        self.tree.heading("#0", text="Icon")
        self.tree.heading("Node Name", text="Node Name")
        self.tree.heading("Node Status", text="Node Status")
        self.tree.heading("Job Name", text="Job Name")
        self.tree.heading("User", text="User")
        self.tree.heading("Start Time", text="Start Time")
        self.tree.heading("End Time", text="End Time")
        self.tree.heading("Duration", text="Duration")
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(root, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        # Layout
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Load initial data
        self.load_data()
        
    def load_data(self):
        # Process JSON files before loading data
        process_json_files()
        
        # Clear existing data
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        # Fetch and display data
        rows = fetch_data()
        for row in rows:
            # Determine which icon to use based on node_status and jobname
            if row[1].lower() == 'running' and row[2] is None:
                status_icon = self.yellow_icon
            elif row[1].lower() == 'running':
                status_icon = self.green_icon
            else:
                status_icon = self.red_icon
            # Insert row with icon in the #0 column and other fields
            self.tree.insert("", tk.END, image=status_icon, values=(row[0], row[1], row[2], row[3], row[4], row[5], row[6]))
        
        # Update timestamp
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.timestamp_var.set(f"Last fetched: {current_time}")

    def set_auto_refresh(self):
        # Cancel existing auto-refresh if any
        if self.auto_refresh_id is not None:
            self.root.after_cancel(self.auto_refresh_id)
            self.auto_refresh_id = None
        
        # Get interval from entry
        try:
            interval_seconds = float(self.interval_entry.get())
            if interval_seconds < 0:
                raise ValueError("Interval cannot be negative")
            self.auto_refresh_interval = int(interval_seconds * 1000)  # Convert to milliseconds
            
            # Start auto-refresh if interval > 0
            if self.auto_refresh_interval > 0:
                self.schedule_auto_refresh()
        except ValueError:
            self.timestamp_var.set("Last fetched: Invalid interval")
            self.auto_refresh_interval = 0

    def schedule_auto_refresh(self):
        self.load_data()
        if self.auto_refresh_interval > 0:
            self.auto_refresh_id = self.root.after(self.auto_refresh_interval, self.schedule_auto_refresh)

# Main program
if __name__ == "__main__":
    # Create database and sample data
    create_sample_db()
    
    # Create Tkinter window
    root = tk.Tk()
    app = DatabaseTableApp(root)
    root.mainloop()