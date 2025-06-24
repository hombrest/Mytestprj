import win32com.client
import os
import sys
import time


def extract_vba_code(xlsm_file, output_dir, xlsx_output=None):
    """
    Extract VBA code from an XLSM file, save each module, sheet, and workbook code to separate files,
    and create a separate XLSX file without VBA code. Includes detailed logging for debugging.

    Args:
        xlsm_file (str): Path to the XLSM file
        output_dir (str): Directory to save the extracted VBA code files
        xlsx_output (str, optional): Path for the XLSX file without VBA code; defaults to input file name with .xlsx extension
    """
    try:
        # Validate input XLSM file
        if not os.path.exists(xlsm_file):
            raise FileNotFoundError(f"Input XLSM file not found: {xlsm_file}")

        # Ensure output directory exists
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)
            print(f"Created output directory: {output_dir}")

        # Set default XLSX output path if not provided
        if xlsx_output is None:
            xlsx_output = os.path.splitext(xlsm_file)[0] + ".xlsx"

        # Validate XLSX output path
        xlsx_dir = os.path.dirname(os.path.abspath(xlsx_output))
        if not os.path.exists(xlsx_dir):
            os.makedirs(xlsx_dir)
            print(f"Created directory for XLSX output: {xlsx_dir}")

        # Start Excel application
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False  # Run Excel in the background
        excel.DisplayAlerts = False  # Suppress alerts

        # Add a small delay to ensure Excel COM stability
        time.sleep(1)

        # Open the workbook
        print(f"Opening workbook: {xlsm_file}")
        wb = excel.Workbooks.Open(os.path.abspath(xlsm_file))


        # Access the VBA project
        try:
            vba_project = wb.VBProject
            print("Successfully accessed VBA project")
        except AttributeError:
            excel.Quit()
            raise Exception(
                "VBA Project is inaccessible. Please enable 'Trust access to the VBA project object model' in Excel:\n"
                "1. Open Excel > File > Options > Trust Center > Trust Center Settings > Macro Settings.\n"
                "2. Check 'Trust access to the VBA project object model'.\n"
                "3. Click OK, close Excel, and rerun the script."
            )

        # Check if VBA project has components
        try:
            component_count = vba_project.VBComponents.Count
            if component_count == 0:
                print("No VBA components found in the project. No source files will be extracted.")
                wb.Close(SaveChanges=False)
                excel.Quit()
                return
            print(f"Found {component_count} VBA components")
        except Exception as e:
            print(f"Error accessing VBA components: {str(e)}")
            wb.Close(SaveChanges=False)
            excel.Quit()
            return

        # Create a dictionary to map VBA component names to worksheet names
        sheet_name_map = {}
        for sheet in wb.Worksheets:
            try:
                component = vba_project.VBComponents(sheet.CodeName)
                sheet_name_map[component.Name] = sheet.Name
                print(f"Mapped sheet: {sheet.Name} (CodeName: {component.Name})")
            except:
                print(f"Skipping sheet {sheet.Name}: No VBA code or inaccessible")
                continue

        # Iterate through VBA components
        for component in vba_project.VBComponents:
            component_name = component.Name
            print(f"Processing component: {component_name} (Type: {component.Type})")
            try:
                code_module = component.CodeModule
                # Check if the component has any code
                if code_module.CountOfLines == 0:
                    print(f"Skipping empty component: {component_name} (Type: {component.Type})")
                    continue

                # Extract code lines
                try:
                    code_lines = code_module.Lines(1, code_module.CountOfLines)
                except Exception as e:
                    print(f"Error extracting code from component {component_name} (Type: {component.Type}): {str(e)}")
                    continue

                # Determine file name and extension
                if component.Type == 1:  # Standard Module
                    file_name = component_name
                    file_ext = ".bas"
                elif component.Type == 2:  # Class Module
                    file_name = component_name
                    file_ext = ".cls"
                elif component.Type == 3:  # UserForm
                    file_name = component_name
                    file_ext = ".frm"
                elif component.Type == 100:  # Document (Sheet or ThisWorkbook)
                    if component_name == "ThisWorkbook":
                        file_name = "ThisWorkbook"
                        file_ext = ".cls"
                    else:
                        # Use component_name (sheet_name) if they differ, else just component_name
                        sheet_name = sheet_name_map.get(component_name, component_name)
                        file_name = f"{component_name} ({sheet_name})" if component_name != sheet_name else component_name
                        file_ext = ".cls"
                else:
                    file_name = component_name
                    file_ext = ".vba"

                # Sanitize file name to avoid invalid characters
                file_name = "".join(c for c in file_name if c.isalnum() or c in ("_", "-", "(", ")", " ")).rstrip()

                # Define output file path
                output_file = os.path.join(output_dir, f"{file_name}{file_ext}")

                # Save the code to a file
                with open(output_file, "w", encoding="utf-8") as f:
                    f.write(code_lines)
                print(f"Extracted: {output_file}")

            except Exception as e:
                print(f"Error processing component {component_name} (Type: {component.Type}): {str(e)}")
                continue

        # Save a copy as XLSX (without VBA)
        try:
            wb.SaveAs(os.path.abspath(xlsx_output), FileFormat=51)  # 51 = xlOpenXMLWorkbook (XLSX, no macros)
            print(f"Saved XLSX file without VBA: {xlsx_output}")
        except Exception as e:
            raise Exception(
                f"Failed to save XLSX file: {str(e)}\n"
                f"Possible causes:\n"
                f"1. Invalid or inaccessible path: {xlsx_output}\n"
                f"2. File is open in Excel or another program.\n"
                f"3. Insufficient write permissions for the directory: {xlsx_dir}\n"
                f"4. Workbook contains features incompatible with XLSX format.\n"
                f"Suggestions:\n"
                f"- Ensure the path is valid and writable.\n"
                f"- Close any open instances of the file or Excel.\n"
                f"- Try saving the file manually in Excel as XLSX to verify compatibility."
            )

        # Clean up
        wb.Close(SaveChanges=False)
        excel.Quit()
        print("Extraction completed")

    except Exception as e:
        print(f"Error: {str(e)}")
        if 'excel' in locals():
            wb.Close(SaveChanges=False)
            excel.Quit()
        sys.exit(1)


if __name__ == "__main__":
    # Example usage
    xlsm_file_path = r"d:\Projects\Python\VBA\TestApp.xlsm"
    output_directory = r"d:\Projects\Python\VBA\output"
    # xlsx_output_path = "path/to/your/file_no_vba.xlsx"  # Replace with desired XLSX output path (optional)
    extract_vba_code(xlsm_file_path, output_directory)