import win32com.client
import win32api
import pythoncom
import pywintypes
import time
import datetime
import os
import sys
import json
import pyodbc
import socket
import subprocess
from typing import List, Dict, Tuple, Any, Optional
import logging
from dataclasses import dataclass
from contextlib import contextmanager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@dataclass
class FunctionInfo:
    module_name: str
    function_name: str
    parameter: str

@dataclass
class DatabaseConfig:
    server: str
    database: str
    username: str
    password: str

@dataclass
class LoggingConfig:
    log_directory: str
    log_level: str

@dataclass
class ExecutionConfig:
    dev_mode: bool
    default_duration_min: int
    default_num_iterations: int
    default_second_duration_min: int
    default_second_num_iterations: int

@dataclass
class LoadTestConfig:
    database: DatabaseConfig
    logging: LoggingConfig
    execution: ExecutionConfig

class LoadTestFramework:
    def __init__(self):
        # Load configuration first
        self.config = self.load_configuration()
        
        # Initialize other variables
        self.duration_min: int = self.config.execution.default_duration_min
        self.num_iterations: int = self.config.execution.default_num_iterations
        self.second_duration_min: int = self.config.execution.default_second_duration_min
        self.second_num_iterations: int = self.config.execution.default_second_num_iterations
        self.second_iteration_count: int = 0
        self.second_next_run: datetime.datetime = datetime.datetime.min
        self.iteration_count: int = 0
        self.should_stop: bool = False
        self.test_id: str = os.environ.get('eVTCS_TestId', '')
        self.user_role: str = os.environ.get('eVTCS_User_Script', '')
        self.ip_address: str = self.get_ip_address()
        
        if not self.ip_address:
            self.ip_address = "UNKNOWN"
        
        # Excel objects
        self.xl_app = None
        self.wb = None
        
        # File system objects
        self.script_dir: str = ""
        self.xlsm_file: str = ""
        self.log_file: str = ""
        
        # Timing variables
        self.start_time: datetime.datetime = datetime.datetime.min
        self.end_time: datetime.datetime = datetime.datetime.min
        
        # Function arrays
        self.start_functions: List[FunctionInfo] = []
        self.inner_functions: List[FunctionInfo] = []
        self.end_functions: List[FunctionInfo] = []
        self.second_end_functions: List[FunctionInfo] = []
        self.pso_functions: List[FunctionInfo] = []
        self.psc_functions: List[FunctionInfo] = []
        
        # Setup logging based on config
        self.setup_logging()
    
    def load_configuration(self) -> LoadTestConfig:
        """Load configuration from file with multiple fallback locations"""
        # Define possible config file locations in order of preference
        config_paths = [
            # 1. Same directory as executable
            os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'config.json'),
            
            # 2. Subdirectory in executable directory
            os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'config', 'config.json'),
            
            # 3. Current working directory
            os.path.join(os.getcwd(), 'config.json'),
            
            # 4. User's roaming app data
            os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'LoadTestFramework', 'config.json'),
            
            # 5. System-wide app data
            os.path.join(os.environ.get('PROGRAMDATA', ''), 'LoadTestFramework', 'config.json'),
        ]
        
        config_file = None
        for path in config_paths:
            if os.path.exists(path):
                config_file = path
                break
        
        if not config_file:
            print("[ERROR] Configuration file not found in any expected location!")
            print("Expected locations:")
            for path in config_paths:
                print(f"  - {path}")
            print("\nPlease create config.json in one of these locations.")
            sys.exit(1)
        
        try:
            with open(config_file, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # Create configuration objects
            db_config = DatabaseConfig(
                server=config_data['database']['server'],
                database=config_data['database']['database'],
                username=config_data['database']['username'],
                password=config_data['database']['password']
            )
            
            logging_config = LoggingConfig(
                log_directory=config_data['logging']['log_directory'],
                log_level=config_data['logging']['log_level']
            )
            
            execution_config = ExecutionConfig(
                dev_mode=config_data['execution']['dev_mode'],
                default_duration_min=config_data['execution']['default_duration_min'],
                default_num_iterations=config_data['execution']['default_num_iterations'],
                default_second_duration_min=config_data['execution']['default_second_duration_min'],
                default_second_num_iterations=config_data['execution']['default_second_num_iterations']
            )
            
            config = LoadTestConfig(
                database=db_config,
                logging=logging_config,
                execution=execution_config
            )
            
            print(f"[CONFIG] Loaded from: {config_file}")
            return config
            
        except Exception as e:
            print(f"[ERROR] Failed to load configuration from {config_file}: {str(e)}")
            sys.exit(1)
    
    def setup_logging(self):
        """Setup logging based on configuration"""
        log_level = getattr(logging, self.config.logging.log_level.upper(), logging.INFO)
        log_dir = self.config.logging.log_directory
        os.makedirs(log_dir, exist_ok=True)
        
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f'loadtest_{self.test_id}.log')),
                logging.StreamHandler()
            ]
        )
    
    def initialize_script(self):
        """Initialize the script with environment variables and setup"""
        logger.info("[INIT] Initializing Python script...")
        
        # Get environment variables
        self.xlsm_file = os.environ.get('eVTCS_Program', '')
        
        # Validate required variables
        if not self.xlsm_file:
            logger.error("[ERROR] EXCEL_FILE not defined!")
            sys.exit(1)
        
        # Strip quotes from xlsm_file if present
        if self.xlsm_file.startswith('"'):
            self.xlsm_file = self.xlsm_file[1:]
        if self.xlsm_file.endswith('"'):
            self.xlsm_file = self.xlsm_file[:-1]
        
        # Setup log file
        formatted_now_str = self.get_log_file_dt()
        self.log_file = f"{self.config.logging.log_directory}\\{self.test_id}-{self.ip_address}-jmeter_logfile_{formatted_now_str}.log"
        
        # Create log directory if it doesn't exist
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log file with header
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("Timestamp,Result,Parameter\n")
        
        logger.info(f"[LOG] Writing to: {self.log_file}")
    
    def get_ip_address(self) -> str:
        """Get the primary IP address of the machine"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip_address = s.getsockname()[0]
            s.close()
            return ip_address
        except:
            return ""
    
    def load_configuration_from_database(self):
        """Load configuration from database using config values"""
        logger.info("[SQL] Loading configuration from database...")
        
        try:
            # Use configuration values for connection
            conn_str = f"DRIVER={{SQL Server}};SERVER={self.config.database.server};DATABASE={self.config.database.database};UID={self.config.database.username};PWD={self.config.database.password}"
            
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                
                query = "SELECT TOP 1 VTDurationMin, NumOfVTPeriod, CSDurationMin, NumOfCSPeriod FROM TestControl WHERE TestId = ?"
                cursor.execute(query, (self.test_id,))
                
                row = cursor.fetchone()
                
                # Set values from config as defaults
                self.duration_min = self.config.execution.default_duration_min
                self.num_iterations = self.config.execution.default_num_iterations
                self.second_duration_min = self.config.execution.default_second_duration_min
                self.second_num_iterations = self.config.execution.default_second_num_iterations
                
                if row:
                    self.duration_min = int(row[0])
                    self.num_iterations = int(row[1])
                    self.second_duration_min = int(row[2])
                    self.second_num_iterations = int(row[3])
                
                logger.info(f"[SQL] Loaded config: MainDurationMin={self.duration_min}, MainIterations={self.num_iterations}, SecondDurationMin={self.second_duration_min}, SecondIterations={self.second_num_iterations}")
                
        except Exception as e:
            logger.error(f"[SQL ERROR] Cannot query config: {str(e)}")
            sys.exit(1)
    
    def load_vba_functions(self):
        """Load VBA functions from database"""
        logger.info("[SQL] Loading VBA functions from database...")
        
        try:
            # Create connection string
            conn_str = f"DRIVER={{SQL Server}};SERVER={self.config.database.server};DATABASE={self.config.database.database};UID={self.config.database.username};PWD={self.config.database.password}"
            
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                
                # Build query with parameterized approach
                query = "SELECT Phase, ModuleName, FunctionName, Parameter FROM TestCase WHERE UserRole = ? OR UserRole = SUBSTRING(?, 1, 1) ORDER BY Phase, Sequence"
                cursor.execute(query, (self.user_role, self.user_role))
                
                # Initialize arrays
                pso_list = []
                psc_list = []
                start_list = []
                inner_list = []
                end_list = []
                second_end_list = []
                
                for row in cursor.fetchall():
                    phase = row[0]
                    module_name = row[1]
                    function_name = row[2]
                    parameter = row[3]
                    
                    func_info = FunctionInfo(module_name, function_name, parameter)
                    
                    if phase == "PSO":
                        pso_list.append(func_info)
                    elif phase == "PSC":
                        psc_list.append(func_info)
                    elif phase == "START":
                        start_list.append(func_info)
                    elif phase == "INNER":
                        inner_list.append(func_info)
                    elif phase == "END":
                        end_list.append(func_info)
                    elif phase == "SECOND_END":
                        second_end_list.append(func_info)
                
                # Assign to instance variables
                self.pso_functions = pso_list
                self.psc_functions = psc_list
                self.start_functions = start_list
                self.inner_functions = inner_list
                self.end_functions = end_list
                self.second_end_functions = second_end_list
                
                logger.info(f"[SQL] Loaded functions: START={len(self.start_functions)}, INNER={len(self.inner_functions)}, END={len(self.end_functions)}, SECOND_END={len(self.second_end_functions)}, PSO={len(self.pso_functions)}, PSC={len(self.psc_functions)}")
                
        except Exception as e:
            logger.error(f"[SQL ERROR] Cannot query functions: {str(e)}")
            sys.exit(1)
    
    def initialize_excel(self):
        """Initialize Excel application and workbook"""
        logger.info("[OPEN] Connecting to Excel...")
        
        try:
            # Try to get existing Excel application
            pythoncom.CoInitialize()
            self.xl_app = win32com.client.Dispatch("Excel.Application")
            self.xl_app.Visible = True
            
            # Open the workbook
            self.wb = self.xl_app.Workbooks.Open(self.xlsm_file)
            self.wb.Activate()
            
            logger.info(f"    [OPEN] Excel opened: {self.wb.Name}")
            
        except Exception as e:
            logger.error(f"[FATAL] Cannot open workbook: {str(e)}")
            sys.exit(1)
    
    def run_vba_functions(self, phase: str) -> List[Tuple[datetime.datetime, float, str]]:
        """Run VBA functions for the specified phase"""
        results = []
        
        # Ensure Excel is ready
        if not self.wb:
            logger.info(f"    [{phase}] [ERROR] Workbook lost! Reopening...")
            self.initialize_excel()
        
        # Select function array based on phase
        functions = {
            "PSO": self.pso_functions,
            "PSC": self.psc_functions,
            "START": self.start_functions,
            "END": self.end_functions,
            "SECOND_END": self.second_end_functions
        }.get(phase, self.inner_functions)
        
        if not functions:
            return results
        
        for func_info in functions:
            logger.info(f"    {self.get_log_data_dt(datetime.datetime.now())} [{phase}] {func_info.module_name}.{func_info.function_name}( \"{func_info.parameter}\" )")
            
            try:
                # Run the VBA function
                result = self.wb.Application.Run(f"{func_info.module_name}.{func_info.function_name}", func_info.parameter)
                results.append((datetime.datetime.now(), float(result), func_info.parameter))
                logger.info(f"    [SUCCESS] {int(result)}")
            except Exception as e:
                results.append((datetime.datetime.now(), -1.0, f"{func_info.parameter} ERROR: {str(e)}"))
                logger.error(f"    [ERROR] {str(e)}")
        
        return results
    
    def log_results(self, results: List[Tuple[datetime.datetime, float, str]], phase: str):
        """Log results to file"""
        log_entries = []
        
        for timestamp, value, parameter in results:
            log_line = f"{self.get_log_data_dt(timestamp)},{int(value)},{parameter}"
            log_entries.append(log_line)
        
        if log_entries:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                for entry in log_entries:
                    f.write(entry + "\n")
    
    def update_job_status(self, job_status: str, job_details: str):
        """Update job status in database"""
        try:
            # Create connection string
            conn_str = f"DRIVER={{SQL Server}};SERVER={self.config.database.server};DATABASE={self.config.database.database};UID={self.config.database.username};PWD={self.config.database.password}"
            
            with pyodbc.connect(conn_str) as conn:
                cursor = conn.cursor()
                
                # Check control table
                control_query = "SELECT TOP 1 TestId FROM Testcontrol WHERE testid = ? AND (GETDATE() > EndTime OR Status IN ('Aborted', 'Completed'))"
                cursor.execute(control_query, (self.test_id,))
                
                if cursor.fetchone():
                    self.should_stop = True
                    logger.info("[CONTROL] Test End Signaled.")
                
                # Call stored procedure
                cursor.execute("{CALL UpdateJobStatusWithHistory (?, ?, ?)}", 
                             (self.ip_address, job_status, job_details))
                
                logger.info(f"[SQL] Stored proc called: IP={self.ip_address}, Status={job_status}")
                
        except Exception as e:
            logger.error(f"[SQL ERROR] Stored proc failed: {str(e)}")
            error_results = [(datetime.datetime.now(), -1.0, f"SQL ERROR: {str(e)}")]
            self.log_results(error_results, "SQL")
    
    def get_log_file_dt(self) -> str:
        """Get formatted date for log file name using built-in datetime formatting"""
        dt = datetime.datetime.now()
        # Format: yyyymmdd-hh (e.g., 20251023-14)
        return dt.strftime("%Y%m%d-%H")
    
    def get_log_data_dt(self, timestamp: datetime.datetime) -> str:
        """Get formatted timestamp for log data in 'yyyy/mm/dd hh:mi:ss' format using built-in datetime formatting"""
        if not timestamp:
            return "Invalid Date"
        
        # Use Python's built-in datetime formatting
        # Format: yyyy/mm/dd hh:mi:ss (24-hour format)
        return timestamp.strftime("%Y/%m/%d %H:%M:%S")
    
    def execute_main_loop(self):
        """Execute the main testing loop"""
        last_sql_update = datetime.datetime.now()
        
        self.update_job_status("Running", "Test START")
        
        while self.iteration_count < self.num_iterations:
            self.iteration_count += 1
            logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [VT PERIOD] {self.iteration_count} START")
            self.update_job_status("Running", f"[VT PERIOD] {self.iteration_count} START")
            
            # Run START functions
            start_results = self.run_vba_functions("START")
            self.log_results(start_results, "START")
            
            # Execute inner loop
            self.execute_inner_loop(last_sql_update)
            
            # Run END functions
            end_results = self.run_vba_functions("END")
            self.log_results(end_results, "END")
            
            logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [VT PERIOD] {self.iteration_count} END")
            
            if datetime.datetime.now() >= self.end_time or self.should_stop:
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [DONE] Total main end time reached!")
                break
    
    def execute_inner_loop(self, last_sql_update: datetime.datetime):
        """Execute the inner testing loop"""
        iteration_end_time = datetime.datetime.now() + datetime.timedelta(minutes=self.duration_min)
        
        while datetime.datetime.now() < iteration_end_time:
            if datetime.datetime.now() >= self.end_time or self.should_stop:
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [DONE] Main end time reached or stop signaled!")
                break
            
            # Run INNER functions
            inner_results = self.run_vba_functions("INNER")
            self.log_results(inner_results, "INNER")
            
            # Check for second loop execution
            if self.second_iteration_count < self.second_num_iterations and datetime.datetime.now() >= self.second_next_run:
                self.second_iteration_count += 1
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [CS PERIOD] {self.second_iteration_count} CUT-OFF")
                
                # Run SECOND_END functions
                second_end_results = self.run_vba_functions("SECOND_END")
                self.log_results(second_end_results, "SECOND_END")
                
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [CS PERIOD] {self.second_iteration_count} END")
                self.second_next_run = self.second_next_run + datetime.timedelta(minutes=self.second_duration_min)
            
            # SQL update every minute
            if (datetime.datetime.now() - last_sql_update).total_seconds() >= 60:
                self.update_job_status("Running", "Heart beat")
                last_sql_update = datetime.datetime.now()
            
            time.sleep(3)  # Sleep for 3 seconds
    
    def cleanup_script(self):
        """Clean up resources"""
        logger.info("[CLEANUP] Cleaning up resources...")
        
        # Close Excel
        if self.wb:
            try:
                self.wb.Close(SaveChanges=False)
                self.wb = None
            except:
                logger.warning("Error closing workbook")
        
        if self.xl_app:
            try:
                self.xl_app.Quit()
                self.xl_app = None
            except:
                logger.warning("Error quitting Excel")
        
        logger.info("[CLEANUP] Script completed successfully")
    
    def run(self):
        """Main execution method"""
        try:
            # Initialize script
            self.initialize_script()
            
            # Load configuration and functions
            self.load_configuration_from_database()
            self.load_vba_functions()
            
            # Initialize Excel
            self.initialize_excel()
            
            # Start timing
            self.start_time = datetime.datetime.now()
            self.end_time = self.start_time + datetime.timedelta(minutes=self.duration_min * self.num_iterations)
            
            logger.info(f"[START TEST] {self.start_time.strftime('%c')}")
            
            # Pre-Test Setup Operations
            logger.info(f"[PSO] {self.start_time.strftime('%c')}")
            pso_results = self.run_vba_functions("PSO")
            self.log_results(pso_results, "PSO")
            
            logger.info(f"[MAIN LOOP] {self.num_iterations} iterations of {self.duration_min} min")
            logger.info(f"[SECOND LOOP] {self.second_num_iterations} iterations of {self.second_duration_min} min")
            logger.info(f"[MAIN END] {self.end_time.strftime('%c')}")
            logger.info(f"[SECOND END] {(self.start_time + datetime.timedelta(minutes=self.second_duration_min * self.second_num_iterations)).strftime('%c')}")
            logger.info("")
            
            # Initialize loop counters
            self.iteration_count = 0
            self.second_iteration_count = 0
            self.second_next_run = self.start_time + datetime.timedelta(minutes=self.second_duration_min)
            
            # Execute main loop
            self.execute_main_loop()
            
            # Post-Test Cleanup Operations
            logger.info(f"[PSC] {datetime.datetime.now().strftime('%c')}")
            psc_results = self.run_vba_functions("PSC")
            self.log_results(psc_results, "PSC")
            
            self.update_job_status("Completed", "Test Completed")
            logger.info(f"[COMPLETED] {datetime.datetime.now().strftime('%c')}")
            
        except Exception as e:
            logger.error(f"Script failed with error: {str(e)}")
            logger.error(f"Stack trace: {e.__traceback__}")
        finally:
            self.cleanup_script()

def main():
    """Main function to run the load test framework"""
    framework = LoadTestFramework()
    framework.run()

if __name__ == "__main__":
    main()