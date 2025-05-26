import argparse
import os
import time
import win32com.client
import pythoncom
import logging
from typing import List, Dict, Optional

# Set up logging
logging.basicConfig(
    filename='vba_processor.log',
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger()


def is_excel_file_open(file_path: str) -> bool:
    """Check if the Excel file is currently open."""
    try:
        excel = win32com.client.GetActiveObject("Excel.Application")
        for workbook in excel.Workbooks:
            if os.path.abspath(workbook.FullName) == os.path.abspath(file_path):
                return True
        return False
    except Exception as e:
        logger.error(f"Error checking if Excel file is open: {e}")
        return False


def process_config_file(config_path: str) -> List[Dict[str, str]]:
    """Process the config file and return a list of commands."""
    commands = []
    try:
        with open(config_path, 'r') as file:
            for line in file:
                line = line.strip()
                # Skip empty lines and comments
                if not line or line.startswith('#'):
                    continue

                # Split by TAB
                parts = line.split('\t')
                command = parts[0].strip()

                if command == 'Flow_Begin':
                    commands.append({'command': 'flow_begin'})
                elif command == 'Flow_End':
                    break
                elif command == 'RunOnce':
                    commands.append({'command': 'run_once', 'value': 'Y'})
                elif command == 'Log':
                    if len(parts) > 1:
                        commands.append({'command': 'log', 'message': '\t'.join(parts[1:]).strip()})
                elif command == 'Call':
                    if len(parts) >= 3:
                        commands.append({
                            'command': 'call',
                            'sheet_name': parts[1].strip(),
                            'sub_name': parts[2].strip()
                        })
                elif command == 'Update':
                    if len(parts) >= 5:
                        commands.append({
                            'command': 'update',
                            'sheet_name': parts[1].strip(),
                            'cell_x': parts[2].strip(),
                            'cell_y': parts[3].strip(),
                            'value': '\t'.join(parts[4:]).strip()
                        })
                elif command == 'Wait':
                    if len(parts) > 1:
                        try:
                            wait_time = int(parts[1].strip())
                            commands.append({'command': 'wait', 'seconds': wait_time})
                        except ValueError:
                            logger.warning(f"Invalid wait time: {parts[1].strip()}")
    except Exception as e:
        logger.error(f"Error processing config file: {e}")
        raise
    return commands


def check_control_file(control_file_path: str) -> bool:
    """Check the control file to see if we should end the flow."""
    try:
        if not os.path.exists(control_file_path):
            return False

        with open(control_file_path, 'r') as file:
            first_line = file.readline().strip()
            return first_line.upper() == "ENDTHEFLOW Y"
    except Exception as e:
        logger.error(f"Error checking control file: {e}")
        return False

def execute_flow(excel_file_path: str, commands: List[Dict[str, str]], control_file_path: Optional[str] = None) -> None:
    """Execute the workflow commands on the Excel file."""
    try:
        # Initialize Excel COM object
        pythoncom.CoInitialize()
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = True  # Make Excel visible (optional)

        # Open the workbook
        workbook = excel.Workbooks.Open(excel_file_path)

        run_once = False
        should_end_flow = False

        # Check if flow should run once
        for cmd in commands:
            if cmd['command'] == 'run_once' and cmd['value'].upper() == 'Y':
                run_once = True
                break

        while True:
            for cmd in commands:
                if should_end_flow:
                    break

                try:
                    if cmd['command'] == 'log':
                        message = cmd.get('message', '')
                        logger.info(message)
                        print(f"LOG: {message}")

                    elif cmd['command'] == 'call':
                        sheet_name = cmd.get('sheet_name', '')
                        sub_name = cmd.get('sub_name', '')
                        if sheet_name and sub_name:
                            # sheet = find_worksheet(workbook, sheet_name)
                            sheet = workbook.sheets(sheet_name)
                            if sheet:
                                sheet.Activate()
                                excel.Run(f"{sheet.CodeName}.{sub_name}")
                                logger.info(f"Called subroutine {sub_name} on sheet {sheet.Name}")
                            else:
                                logger.error(f"Worksheet {sheet_name} not found")
                                raise ValueError(f"Worksheet {sheet_name} not found")

                    elif cmd['command'] == 'update':
                        sheet_name = cmd.get('sheet_name', '')
                        cell_x = cmd.get('cell_x', '')
                        cell_y = cmd.get('cell_y', '')
                        value = cmd.get('value', '')
                        if sheet_name and cell_x and cell_y:
                            # sheet = find_worksheet(workbook, sheet_name)
                            sheet = workbook.sheets(sheet_name)
                            if sheet:
                                sheet.Activate()
                                # Assuming cell_x is column and cell_y is row (e.g., "A", "1")
                                cell = sheet.Range(f"{cell_x}{cell_y}")
                                cell.Value = value
                                logger.info(f"Updated cell {cell_x}{cell_y} on {sheet_name} with value: {value}")
                            else:
                                logger.error(f"Worksheet {sheet_name} not found")
                                raise ValueError(f"Worksheet {sheet_name} not found")

                    elif cmd['command'] == 'wait':
                        seconds = cmd.get('seconds', 0)
                        if seconds > 0:
                            logger.info(f"Waiting for {seconds} seconds...")
                            time.sleep(seconds)

                    elif cmd['command'] == 'flow_end':
                        should_end_flow = True
                        break

                    # Check if we should end the flow by either method
                    if control_file_path:
                        if check_control_file(control_file_path):
                            logger.info("Control file indicates flow should end")
                            should_end_flow = True
                            break

                    # Also check the Excel method if no control file or it didn't indicate to end
                    # if not should_end_flow:
                    #     try:
                    #         result = excel.Run("Endtheflow")
                    #         if result == "Y":
                    #             should_end_flow = True
                    #             break
                    #     except:
                    #         pass

                except Exception as e:
                    logger.error(f"Error executing command {cmd}: {e}")
                    continue

            if run_once or should_end_flow:
                break

        # Close the workbook without saving
        # workbook.Close(False)
        # excel.Quit()

    except Exception as e:
        logger.error(f"Error executing flow: {e}")
        raise
    finally:
        pythoncom.CoUninitialize()


def main():
    parser = argparse.ArgumentParser(description='Run VBA processes in an Excel file based on a config file.')
    parser.add_argument('-excel_file_path', required=True, help='Path to the Excel file')
    parser.add_argument('-config_file', required=True, help='Path to the config file')
    parser.add_argument('-control_file', required=False, help='Optional path to control file that can end the flow')

    args = parser.parse_args()

    # Check if files exist
    if not os.path.exists(args.excel_file_path):
        logger.error(f"Excel file not found: {args.excel_file_path}")
        print(f"Error: Excel file not found: {args.excel_file_path}")
        return

    if not os.path.exists(args.config_file):
        logger.error(f"Config file not found: {args.config_file}")
        print(f"Error: Config file not found: {args.config_file}")
        return

    # Check if Excel file is open
    if not is_excel_file_open(args.excel_file_path):
        logger.error(f"Excel file is not open: {args.excel_file_path}")
        print(f"Error: Excel file is not open. Please open it first: {args.excel_file_path}")
        return

    # Process config file
    try:
        commands = process_config_file(args.config_file)
        if not commands:
            logger.error("No valid commands found in config file")
            print("Error: No valid commands found in config file")
            return

        logger.info(f"Starting processing for {args.excel_file_path}")
        print(f"Starting processing for {args.excel_file_path}")

        execute_flow(args.excel_file_path, commands, args.control_file)

        logger.info("Processing completed successfully")
        print("Processing completed successfully")

    except Exception as e:
        logger.error(f"Processing failed: {e}")
        print(f"Error: Processing failed: {e}")


if __name__ == "__main__":
    main()