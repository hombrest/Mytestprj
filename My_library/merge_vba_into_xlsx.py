import win32com.client
import os
import sys
import re
import time


def merge_vba_into_xlsx(xlsx_file, source_dir, output_xlsm):
    """
    Enhanced VBA merger that:
    - For ThisWorkbook.cls: Replaces code in workbook module
    - For Module*.bas: Replaces existing modules or imports new ones
    - For Module*.cls: Replaces entire modules in VBA project
    - For Sheet*.cls: Replaces code in existing sheet modules
    """
    try:
        # Start Excel
        excel = win32com.client.Dispatch("Excel.Application")
        excel.Visible = False  # Set to True for debugging
        excel.DisplayAlerts = False

        # Open workbook
        wb = excel.Workbooks.Open(os.path.abspath(xlsx_file))

        # Access VBA project
        try:
            vba_project = wb.VBProject
        except AttributeError:
            excel.Quit()
            raise Exception(
                "Enable 'Trust access to the VBA project object model' in Excel Options."
            )

        # Process VBA files
        vba_files = [f for f in os.listdir(source_dir) if f.endswith(('.bas', '.cls'))]

        for vba_file in vba_files:
            file_path = os.path.join(source_dir, vba_file)
            file_name, file_ext = os.path.splitext(vba_file)
            base_name = file_name.split(' (')[0]

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    vba_code = f.read()
            except UnicodeDecodeError:
                with open(file_path, 'r', encoding='latin-1') as f:
                    vba_code = f.read()

            if file_name == 'ThisWorkbook' and file_ext == '.cls':
                # Handle ThisWorkbook.cls replacement
                try:
                    replace_workbook_code(vba_project, vba_code)
                    print("Successfully replaced ThisWorkbook code")
                except Exception as e:
                    print(f"Failed to update ThisWorkbook: {str(e)}")
                    try:
                        replace_workbook_code_fallback(wb, vba_code)
                        print("Used fallback method for ThisWorkbook successfully")
                    except Exception as alt_e:
                        print(f"Fallback method also failed: {str(alt_e)}")

            elif file_ext == '.bas' and base_name.startswith('Module'):
                # Handle .bas files - replace or import
                module_name = base_name
                try:
                    replace_or_import_module(vba_project, module_name, file_path, vba_code)
                    print(f"Processed module: {module_name}")
                except Exception as e:
                    print(f"Failed to process module {module_name}: {str(e)}")

            elif file_ext == '.cls' and base_name.startswith('Module'):
                # Handle Module.cls replacement
                module_name = base_name
                try:
                    replace_entire_module(vba_project, module_name, vba_code)
                    print(f"Successfully replaced module: {module_name}")
                except Exception as e:
                    print(f"Failed to replace module {module_name}: {str(e)}")

            elif file_ext == '.cls' and base_name.startswith('Sheet'):
                # Handle Sheet code replacement
                sheet_name = file_name.split(' (')[1].rstrip(')') if ' (' in file_name else base_name
                component_name = base_name

                sheet = None
                for s in wb.Worksheets:
                    if s.Name == sheet_name:
                        sheet = s
                        break

                if not sheet:
                    print(f"Sheet '{sheet_name}' not found, skipping {vba_file}")
                    continue

                try:
                    replace_sheet_code(sheet, vba_project, component_name, vba_code)
                    print(f"Successfully replaced code for sheet: {sheet_name}")
                except Exception as e:
                    print(f"Failed to update sheet '{sheet_name}': {str(e)}")
                    try:
                        replace_sheet_code_fallback(sheet, vba_code)
                        print("Used fallback method successfully")
                    except Exception as alt_e:
                        print(f"Fallback method also failed: {str(alt_e)}")

        # Save as macro-enabled workbook
        wb.SaveAs(os.path.abspath(output_xlsm), FileFormat=52)
        print(f"Saved: {output_xlsm}")

        # Clean up
        wb.Close(SaveChanges=False)
        excel.Quit()

    except Exception as e:
        print(f"Fatal error: {str(e)}")
        if 'excel' in locals():
            excel.Quit()
        sys.exit(1)


def replace_workbook_code(vba_project, new_code):
    """Replace code in the ThisWorkbook module"""
    # Find the ThisWorkbook component
    workbook_component = None
    for component in vba_project.VBComponents:
        if component.Name == "ThisWorkbook" and component.Type == 100:  # vbext_ct_Document
            workbook_component = component
            break

    if not workbook_component:
        raise Exception("Could not find ThisWorkbook component")

    # Clear existing code
    code_module = workbook_component.CodeModule
    if code_module.CountOfLines > 0:
        code_module.DeleteLines(1, code_module.CountOfLines)

    # Add new code
    code_module.AddFromString(new_code.strip())


def replace_workbook_code_fallback(wb, new_code):
    """Alternative method to update ThisWorkbook code"""
    # Make Excel and VBE visible
    excel = wb.Application
    excel.Visible = True
    excel.VBE.MainWindow.Visible = True

    # Open VBA editor and select ThisWorkbook
    excel.VBE.CommandBars.FindControl(ID := 2578).Execute()  # Alt+F11
    time.sleep(1)

    # Find and activate ThisWorkbook module
    for window in excel.VBE.Windows:
        if window.Caption.endswith("ThisWorkbook (Code)"):
            window.SetFocus()
            break

    # Select all and replace
    excel.VBE.ActiveCodePane.CodeModule.SelectAll()
    excel.VBE.ActiveCodePane.CodeModule.DeleteLines(1, excel.VBE.ActiveCodePane.CodeModule.CountOfLines)
    excel.VBE.ActiveCodePane.CodeModule.AddFromString(new_code.strip())

    # Clean up
    excel.VBE.MainWindow.Visible = False
    excel.Visible = False


def replace_or_import_module(vba_project, module_name, file_path, vba_code):
    """Replace existing module or import new one"""
    # Check if module exists
    module_exists = False
    for component in vba_project.VBComponents:
        if component.Name == module_name and component.Type == 1:  # vbext_ct_StdModule
            module_exists = True
            break

    if module_exists:
        # Replace existing module
        replace_entire_module(vba_project, module_name, vba_code)
        print(f"Replaced existing module: {module_name}")
    else:
        # Import new module
        vba_project.VBComponents.Import(file_path)
        print(f"Imported new module: {module_name}")


def replace_entire_module(vba_project, module_name, new_code):
    """Completely replace a standard module"""
    # Remove existing module if it exists
    for component in vba_project.VBComponents:
        if component.Name == module_name and component.Type == 1:  # vbext_ct_StdModule
            vba_project.VBComponents.Remove(component)
            break

    # Add new module
    new_module = vba_project.VBComponents.Add(1)  # vbext_ct_StdModule
    new_module.Name = module_name
    new_module.CodeModule.AddFromString(new_code.strip())


def replace_sheet_code(sheet, vba_project, component_name, new_code):
    """Replace code in a worksheet module"""
    # Ensure we're working with the correct component
    sheet_component = None
    for component in vba_project.VBComponents:
        if component.Name == component_name and component.Type == 100:  # vbext_ct_Document
            sheet_component = component
            break

    if not sheet_component:
        raise Exception(f"Could not find component {component_name} for sheet {sheet.Name}")

    # Clear existing code
    code_module = sheet_component.CodeModule
    if code_module.CountOfLines > 0:
        code_module.DeleteLines(1, code_module.CountOfLines)

    # Add new code
    code_module.AddFromString(new_code.strip())

    # Ensure proper code name
    try:
        sheet.CodeName = component_name
    except:
        pass  # Some Excel versions restrict changing CodeName


def replace_sheet_code_fallback(sheet, new_code):
    """Alternative method to update sheet code"""
    # Make Excel and VBE visible
    excel = sheet.Application
    excel.Visible = True
    excel.VBE.MainWindow.Visible = True

    # Activate the sheet
    sheet.Activate()

    # Open VBA editor and select the sheet's module
    excel.VBE.CommandBars.FindControl(ID := 2578).Execute()  # Alt+F11
    time.sleep(1)

    # Find and activate the sheet's module
    for window in excel.VBE.Windows:
        if window.Caption.endswith(f"(Code)") and sheet.Name in window.Caption:
            window.SetFocus()
            break

    # Select all and replace
    excel.VBE.ActiveCodePane.CodeModule.SelectAll()
    excel.VBE.ActiveCodePane.CodeModule.DeleteLines(1, excel.VBE.ActiveCodePane.CodeModule.CountOfLines)
    excel.VBE.ActiveCodePane.CodeModule.AddFromString(new_code.strip())

    # Clean up
    excel.VBE.MainWindow.Visible = False
    excel.Visible = False


if __name__ == "__main__":
    # Example usage
    xlsx_file_path = r"d:\Projects\Python\VBA\TestApp.xlsx"
    source_directory = r"d:\Projects\Python\VBA\output"
    output_xlsm_path = r"d:\Projects\Python\VBA\TestApp_copy.xlsm"
    merge_vba_into_xlsx(xlsx_file_path, source_directory, output_xlsm_path)