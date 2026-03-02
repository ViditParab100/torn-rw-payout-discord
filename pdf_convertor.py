import aspose.cells

from aspose.cells import Workbook, PdfSaveOptions

def convert_xlsx_to_pdf(xlsx_file, pdf_file):
    try:
        # Load the existing Excel file
        workbook = Workbook(xlsx_file)
        
        # Options to ensure it fits nicely on a page
        saveOptions = PdfSaveOptions()
        saveOptions.one_page_per_sheet = True  # Keeps the table together
        
        # Save as PDF
        workbook.save(pdf_file, saveOptions)
        return pdf_file
    except Exception as e:
        print(f"Conversion Error: {e}")
        return None