import jpype
import asposecells
# This starts the Java engine required for the conversion
if not jpype.isJVMStarted():
    jpype.startJVM()

from asposecells.api import Workbook, PdfSaveOptions

def convert_xlsx_to_pdf(xlsx_file, pdf_file):
    try:
        # Load the workbook
        workbook = Workbook(xlsx_file)
        
        # Set PDF options
        saveOptions = PdfSaveOptions()
        saveOptions.setOnePagePerSheet(True)
        
        # Save
        workbook.save(pdf_file, saveOptions)
        return pdf_file
    except Exception as e:
        print(f"Conversion Error: {e}")
        return None