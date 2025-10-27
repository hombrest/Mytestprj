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
import random
from typing import List, Dict, Tuple, Any, Optional
import logging
from dataclasses import dataclass
from contextlib import contextmanager
from func_timeout import func_timeout, FunctionTimedOut
from sqlalchemy import create_engine  # New import for connection pooling

# Configure logging with separate console log file
log_directory = os.path.join(os.getcwd(), 'logs')
os.makedirs(log_directory, exist_ok=True)
console_log_file = os.path.join(log_directory, f'console_{datetime.datetime.now().strftime("%Y%m%d-%H%M%S")}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(console_log_file),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

@dataclass
class FunctionInfo:
    module_name: str
    function_name: str
    parameter: str
    interval_seconds: float
    throughput: int
    timeout_seconds: float

@dataclass
class DatabaseConfig:
    server: str
    database: str
    username: str
    password: str
    driver: str  # New field for configurable database driver

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
    default_thinking_time: int
    default_inner_interval: float
    default_wait_time_seconds: int
    default_timeout_seconds: float

@dataclass
class LoadTestConfig:
    database: DatabaseConfig
    logging: LoggingConfig
    execution: ExecutionConfig

class LoadTestFramework:
    def __init__(self):
        self.config = self.load_configuration()
        self.duration_min: int = self.config.execution.default_duration_min
        self.num_iterations: int = self.config.execution.default_num_iterations
        self.second_duration_min: int = self.config.execution.default_second_duration_min
        self.second_num_iterations: int = self.config.execution.default_second_num_iterations
        self.thinking_time: int = self.config.execution.default_thinking_time
        self.default_inner_interval: float = self.config.execution.default_inner_interval
        self.default_timeout_seconds: float = self.config.execution.default_timeout_seconds
        self.second_iteration_count: int = 0
        self.second_next_run: datetime.datetime = datetime.datetime.min
        self.iteration_count: int = 0
        self.should_stop: bool = False
        self.test_id: str = os.environ.get('eVTCS_TestId', '')
        self.user_role: str = os.environ.get('eVTCS_UserRole', '')
        self.ip_address: str = self.get_ip_address()
        if not self.ip_address:
            self.ip_address = "UNKNOWN"
        self.xl_app = None
        self.wb = None
        self.script_dir: str = ""
        self.xlsm_file: str = ""
        self.log_file: str = ""
        self.start_time: datetime.datetime = datetime.datetime.min
        self.end_time: datetime.datetime = datetime.datetime.min
        self.start_functions: List[FunctionInfo] = []
        self.inner_functions: List[FunctionInfo] = []
        self.end_functions: List[FunctionInfo] = []
        self.second_end_functions: List[FunctionInfo] = []
        self.pso_functions: List[FunctionInfo] = []
        self.psc_functions: List[FunctionInfo] = []
        self.inner_function_last_run: Dict[Tuple[str, str, str], datetime.datetime] = {}
        self.wait_time: int = self.config.execution.default_wait_time_seconds
        # Initialize SQLAlchemy engine for connection pooling
        self.db_engine = self.create_db_engine()
        self.setup_logging()
    
    def create_db_engine(self):
        """Create SQLAlchemy engine for connection pooling"""
        try:
            driver = self.config.database.driver or "SQL Server"
            conn_str = (
                f"mssql+pyodbc://{self.config.database.username}:{self.config.database.password}"
                f"@{self.config.database.server}/{self.config.database.database}?driver={driver}"
            )
            engine = create_engine(conn_str, pool_size=5, max_overflow=10)
            logger.info(f"[DB] Created SQLAlchemy engine with driver: {driver}")
            return engine
        except Exception as e:
            logger.error(f"[DB ERROR] Failed to create database engine: {str(e)}")
            sys.exit(1)
    
    def load_configuration(self) -> LoadTestConfig:
        """Load configuration from file with multiple fallback locations"""
        config_paths = [
            os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'config.json'),
            os.path.join(os.path.dirname(sys.executable if getattr(sys, 'frozen', False) else __file__), 'config', 'config.json'),
            os.path.join(os.getcwd(), 'config.json'),
            os.path.join(os.path.expanduser('~'), 'AppData', 'Roaming', 'LoadTestFramework', 'config.json'),
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
            
            db_config = DatabaseConfig(
                server=config_data['database']['server'],
                database=config_data['database']['database'],
                username=config_data['database']['username'],
                password=config_data['database']['password'],
                driver=config_data['database'].get('driver', 'SQL Server')  # Default to SQL Server
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
                default_second_num_iterations=config_data['execution']['default_second_num_iterations'],
                default_thinking_time=config_data['execution']['default_thinking_time'],
                default_inner_interval=config_data['execution'].get('default_inner_interval', 3.0),
                default_wait_time_seconds=config_data['execution'].get('default_wait_time_seconds', 10),
                default_timeout_seconds=config_data['execution'].get('default_timeout_seconds', 10.0)
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
        
        logging.getLogger().handlers = []
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(os.path.join(log_dir, f'loadtest_{self.test_id}.log')),
                logging.FileHandler(console_log_file),
                logging.StreamHandler()
            ]
        )
    
    def initialize_script(self):
        """Initialize the script with environment variables and setup"""
        logger.info("[INIT] Initializing Python script...")
        
        self.xlsm_file = os.environ.get('eVTCS_Program', '')
        if not self.xlsm_file:
            logger.error("[ERROR] EXCEL_FILE not defined!")
            sys.exit(1)
        
        if self.xlsm_file.startswith('"'):
            self.xlsm_file = self.xlsm_file[1:]
        if self.xlsm_file.endswith('"'):
            self.xlsm_file = self.xlsm_file[:-1]
        
        logfile_time = datetime.datetime.now().strftime("%Y%m%d-%H")
        self.log_file = f"{self.config.logging.log_directory}\\{self.test_id}-{self.ip_address}-jmeter_logfile_{logfile_time}.log"
        
        log_dir = os.path.dirname(self.log_file)
        os.makedirs(log_dir, exist_ok=True)
        
        with open(self.log_file, 'w', encoding='utf-8') as f:
            f.write("Timestamp,Result,Parameter\n")
        
        logger.info(f"[LOG] Writing to: {self.log_file}")
    
    def get_ip_address(self) -> str:
        """Get the hostname of the machine since internet is unavailable"""
        try:
            return socket.gethostname()
        except Exception as e:
            logger.warning(f"Failed to get hostname: {str(e)}")
            return "UNKNOWN"
    
    def load_configuration_from_database(self):
        """Load configuration from database using config values"""
        logger.info("[SQL] Loading configuration from database...")
        
        try:
            with self.db_engine.connect() as conn:
                cursor = conn.execute(
                    "SELECT TOP 1 VTDurationMin, NumOfVTPeriod, CSDurationMin, NumOfCSPeriod, WaitTimeSeconds FROM TestControl WHERE TestId = ?",
                    (self.test_id,)
                )
                
                row = cursor.fetchone()
                
                self.duration_min = self.config.execution.default_duration_min
                self.num_iterations = self.config.execution.default_num_iterations
                self.second_duration_min = self.config.execution.default_second_duration_min
                self.second_num_iterations = self.config.execution.default_second_num_iterations
                self.wait_time = self.config.execution.default_wait_time_seconds
                
                if row:
                    self.duration_min = int(row[0])
                    self.num_iterations = int(row[1])
                    self.second_duration_min = int(row[2])
                    self.second_num_iterations = int(row[3])
                    self.wait_time = int(row[4]) if row[4] is not None else self.config.execution.default_wait_time_seconds
                
                if self.wait_time < 0:
                    self.wait_time = random.randint(0, 30)
                
                logger.info(f"[SQL] Loaded config: MainDurationMin={self.duration_min}, MainIterations={self.num_iterations}, SecondDurationMin={self.second_duration_min}, SecondIterations={self.second_num_iterations}, WaitTimeSeconds={self.wait_time}")
                
        except Exception as e:
            logger.error(f"[SQL ERROR] Cannot query config: {str(e)}")
            sys.exit(1)
    
    def load_vba_functions(self):
        """Load VBA functions from database"""
        logger.info("[SQL] Loading VBA functions from database...")
        
        try:
            with self.db_engine.connect() as conn:
                cursor = conn.execute(
                    """
                    SELECT Phase, ModuleName, FunctionName, Parameter, 
                           COALESCE(IntervalSeconds, ?) AS IntervalSeconds,
                           COALESCE(Throughput, 1) AS Throughput,
                           COALESCE(TimeoutSeconds, ?) AS TimeoutSeconds
                    FROM TestCase 
                    WHERE UserRole = ? OR UserRole = SUBSTRING(?, 1, 1) 
                    ORDER BY Phase, Sequence
                    """,
                    (self.default_inner_interval, self.default_timeout_seconds, self.user_role, self.user_role)
                )
                
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
                    interval_seconds = float(row[4])
                    throughput = int(row[5])
                    timeout_seconds = float(row[6])
                    
                    if timeout_seconds <= 0:
                        logger.warning(f"Invalid timeout {timeout_seconds} for {module_name}.{function_name}. Using default {self.default_timeout_seconds}.")
                        timeout_seconds = self.default_timeout_seconds
                    
                    func_info = FunctionInfo(module_name, function_name, parameter, interval_seconds, throughput, timeout_seconds)
                    
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
            pythoncom.CoInitialize()
            self.xl_app = win32com.client.Dispatch("Excel.Application")
            self.xl_app.Visible = True
            
            self.wb = self.xl_app.Workbooks.Open(self.xlsm_file)
            self.wb.Activate()
            
            logger.info(f"    [OPEN] Excel opened: {self.wb.Name}")
            
        except Exception as e:
            logger.error(f"[FATAL] Cannot open workbook: {str(e)}")
            sys.exit(1)
    
    def run_vba_functions(self, phase: str) -> List[Tuple[datetime.datetime, float, str]]:
        """Run VBA functions for the specified phase with timeout"""
        results = []
        
        if not self.wb:
            logger.info(f"    [{phase}] [ERROR] Workbook lost! Reopening...")
            self.initialize_excel()
        
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
            unique_key = f"{phase}.{func_info.function_name}"
            logger.info(f"    [KEY] Executing with key: {unique_key}")
            
            for _ in range(func_info.throughput):
                logger.info(f"    Thinking for {self.thinking_time} seconds")
                time.sleep(self.thinking_time)
                logger.info(f"    {self.get_log_data_dt(datetime.datetime.now())} [{phase}] {func_info.module_name}.{func_info.function_name}( \"{func_info.parameter}\" )")
                
                try:
                    result = func_timeout(
                        func_info.timeout_seconds,
                        self.wb.Application.Run,
                        args=(f"{func_info.module_name}.{func_info.function_name}", func_info.parameter)
                    )
                    results.append((datetime.datetime.now(), float(result), func_info.parameter))
                    logger.info(f"    [SUCCESS] {int(result)}")
                except FunctionTimedOut:
                    logger.error(f"    [TIMEOUT] {func_info.module_name}.{func_info.function_name} timed out after {func_info.timeout_seconds} seconds")
                except Exception as e:
                    logger.error(f"    [ERROR] {func_info.module_name}.{func_info.function_name}: {str(e)}")
                    continue
        
        return results
    
    def log_results(self, results: List[Tuple[datetime.datetime, float, str]], phase: str):
        """Log results to file, excluding errors"""
        log_entries = []
        
        for timestamp, value, parameter in results:
            if value >= 0:
                log_line = f"{self.get_log_data_dt(timestamp)},{int(value)},{parameter}"
                log_entries.append(log_line)
        
        if log_entries:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                for entry in log_entries:
                    f.write(entry + "\n")
    
    def update_job_status(self, job_status: str, job_details: str):
        """Update job status in database"""
        try:
            with self.db_engine.connect() as conn:
                cursor = conn.execute(
                    "SELECT TOP 1 TestId FROM Testcontrol WHERE testid = ? AND (GETDATE() > EndTime OR Status IN ('Aborted', 'Completed'))",
                    (self.test_id,)
                )
                
                if cursor.fetchone():
                    self.should_stop = True
                    logger.info("[CONTROL] Test End Signaled.")
                
                cursor.execute("{CALL UpdateJobStatusWithHistory (?, ?, ?)}", 
                             (self.ip_address, job_status, job_details))
                
                logger.info(f"[SQL] Stored proc called: IP={self.ip_address}, Status={job_status}")
                
        except Exception as e:
            logger.error(f"[SQL ERROR] Stored proc failed: {str(e)}")
            error_results = [(datetime.datetime.now(), -1.0, f"SQL ERROR: {str(e)}")]
            self.log_results(error_results, "SQL")

    def get_log_data_dt(self, timestamp: datetime.datetime) -> str:
        """Get formatted timestamp for log data in 'yyyy/mm/dd hh:mi:ss' format"""
        if not timestamp:
            return "Invalid Date"
        return timestamp.strftime("%Y/%m/%d %H:%M:%S.%f")[:-3]
    
    def execute_main_loop(self):
        """Execute the main testing loop"""
        last_sql_update = datetime.datetime.now()
        
        self.update_job_status("Running", "Test START")
        
        while self.iteration_count < self.num_iterations:
            self.iteration_count += 1
            logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [VT PERIOD] {self.iteration_count} START")
            self.update_job_status("Running", f"[VT PERIOD] {self.iteration_count} START")
            
            start_results = self.run_vba_functions("START")
            self.log_results(start_results, "START")
            
            self.execute_inner_loop(last_sql_update)
            
            end_results = self.run_vba_functions("END")
            self.log_results(end_results, "END")
            
            logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [VT PERIOD] {self.iteration_count} END")
            
            if datetime.datetime.now() >= self.end_time or self.should_stop:
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [DONE] Total main end time reached!")
                break
    
    def execute_inner_loop(self, last_sql_update: datetime.datetime):
        """Execute the inner testing loop with function-specific intervals"""
        iteration_end_time = datetime.datetime.now() + datetime.timedelta(minutes=self.duration_min)
        
        for func in self.inner_functions:
            key = (func.module_name, func.function_name, func.parameter)
            self.inner_function_last_run[key] = datetime.datetime.min
        
        while datetime.datetime.now() < iteration_end_time:
            if datetime.datetime.now() >= self.end_time or self.should_stop:
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [DONE] Main end time reached or stop signaled!")
                break
            
            inner_results = []
            current_time = datetime.datetime.now()
            for func in self.inner_functions:
                unique_key = f"INNER.{func.function_name}"
                logger.info(f"    [KEY] Checking with key: {unique_key}")
                
                key = (func.module_name, func.function_name, func.parameter)
                last_run = self.inner_function_last_run.get(key, datetime.datetime.min)
                time_since_last_run = (current_time - last_run).total_seconds()
                
                if time_since_last_run >= func.interval_seconds:
                    logger.info(f"    Thinking for {self.thinking_time} seconds before {func.module_name}.{func.function_name}")
                    time.sleep(self.thinking_time)
                    logger.info(f"    {self.get_log_data_dt(current_time)} [INNER] {func.module_name}.{func.function_name}( \"{func.parameter}\" )")
                    
                    try:
                        result = func_timeout(
                            func.timeout_seconds,
                            self.wb.Application.Run,
                            args=(f"{func.module_name}.{func.function_name}", func.parameter)
                        )
                        inner_results.append((current_time, float(result), func.parameter))
                        logger.info(f"    [SUCCESS] {int(result)}")
                        self.inner_function_last_run[key] = current_time
                    except FunctionTimedOut:
                        logger.error(f"    [TIMEOUT] {func.module_name}.{func.function_name} timed out after {func.timeout_seconds} seconds")
                    except Exception as e:
                        logger.error(f"    [ERROR] {func.module_name}.{func.function_name}: {str(e)}")
            
            self.log_results(inner_results, "INNER")
            
            if self.second_iteration_count < self.second_num_iterations and datetime.datetime.now() >= self.second_next_run:
                self.second_iteration_count += 1
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [CS PERIOD] {self.second_iteration_count} CUT-OFF")
                
                second_end_results = self.run_vba_functions("SECOND_END")
                self.log_results(second_end_results, "SECOND_END")
                
                logger.info(f"{self.get_log_data_dt(datetime.datetime.now())} [CS PERIOD] {self.second_iteration_count} END")
                self.second_next_run = self.second_next_run + datetime.timedelta(minutes=self.second_duration_min)
            
            if (datetime.datetime.now() - last_sql_update).total_seconds() >= 60:
                self.update_job_status("Running", "Heart beat")
                last_sql_update = datetime.datetime.now()
            
            time.sleep(0.1)
    
    def cleanup_script(self):
        """Clean up resources"""
        logger.info("[CLEANUP] Cleaning up resources...")
        
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
        
        pythoncom.CoUninitialize()
        if self.db_engine:
            self.db_engine.dispose()  # Dispose of SQLAlchemy engine
        logger.info("[CLEANUP] Script completed successfully")
    
    def run(self):
        """Main execution method"""
        try:
            self.initialize_script()
            self.load_configuration_from_database()
            self.load_vba_functions()
            self.initialize_excel()
            
            logger.info(f"[WAIT] Waiting for {self.wait_time} seconds before starting test...")
            time.sleep(self.wait_time)
            
            self.start_time = datetime.datetime.now()
            self.end_time = self.start_time + datetime.timedelta(minutes=self.duration_min * self.num_iterations)
            
            logger.info(f"[START TEST] {self.start_time.strftime('%c')}")
            
            logger.info(f"[PSO] {self.start_time.strftime('%c')}")
            pso_results = self.run_vba_functions("PSO")
            self.log_results(pso_results, "PSO")
            
            logger.info(f"[MAIN LOOP] {self.num_iterations} iterations of {self.duration_min} min")
            logger.info(f"[SECOND LOOP] {self.second_num_iterations} iterations of {self.second_duration_min} min")
            logger.info(f"[MAIN END] {self.end_time.strftime('%c')}")
            logger.info(f"[SECOND END] {(self.start_time + datetime.timedelta(minutes=self.second_duration_min * self.second_num_iterations)).strftime('%c')}")
            logger.info("")
            
            self.iteration_count = 0
            self.second_iteration_count = 0
            self.second_next_run = self.start_time + datetime.timedelta(minutes=self.second_duration_min)
            
            self.execute_main_loop()
            
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