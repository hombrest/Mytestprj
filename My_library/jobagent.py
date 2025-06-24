import os
import time
import subprocess
from datetime import datetime

JOBS_DIR = r'C:\jobs'
STOP_FILE = os.path.join(JOBS_DIR, 'Stop_controller.txt')
POLL_INTERVAL = 10  # seconds

def should_stop():
    """Check if the stop file exists"""
    return os.path.exists(STOP_FILE)

def launch_detached_process(cmd_file):
    """Launch a completely detached process without any handles"""
    try:
        # Configure to hide the console window
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # Launch the process with no console window and no handles
        subprocess.Popen(
            ['cmd.exe', '/c', cmd_file],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NO_WINDOW,
            startupinfo=startupinfo
        )
        print(f"Successfully launched detached process: {cmd_file}")
    except Exception as e:
        print(f"Failed to launch {cmd_file}: {e}")

def process_bat_files():
    """Process all bat files in the directory"""
    for filename in os.listdir(JOBS_DIR):
        if filename.lower().endswith('.bat'):
            bat_file = os.path.join(JOBS_DIR, filename)
            
            try:
                # Generate new filename with timestamp
                base_name = os.path.splitext(filename)[0]
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                new_name = os.path.join(JOBS_DIR, f"{base_name}_{timestamp}.cmd")
                
                # Rename first to prevent reprocessing
                os.rename(bat_file, new_name)
                print(f"Renamed: {filename} → {os.path.basename(new_name)}")

                # Launch detached process
                launch_detached_process(new_name)
                
            except Exception as e:
                print(f"Error processing {bat_file}: {e}")

def main():
    # Create jobs directory if needed
    if not os.path.exists(JOBS_DIR):
        os.makedirs(JOBS_DIR)
        print(f"Created directory: {JOBS_DIR}")
    
    print(f"Job controller started. Monitoring {JOBS_DIR} every {POLL_INTERVAL} seconds...")
    print(f"Controller will stop immediately if {STOP_FILE} exists.")

    try:
        while True:
            if should_stop():
                print("Stop file detected - terminating controller immediately")
                break
                
            process_bat_files()
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nJob controller stopped by user.")
    finally:
        # Clean up stop file if it exists
        try:
            if os.path.exists(STOP_FILE):
                os.remove(STOP_FILE)
                print("Stop file removed")
        except Exception as e:
            print(f"Error removing stop file: {e}")

if __name__ == "__main__":
    main()