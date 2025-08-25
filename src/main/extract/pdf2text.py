import os
import fitz
import easyocr
import numpy as np
from pdf2image import convert_from_path
from pathlib import Path

PDF_DIR = Path("book_data/pdf_files")
OUTPUT_DIR = Path("book_data/not_clean")

PDF_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Check
def check_file_access(pdf_path: Path):
    if not pdf_path.exists():
        print(f"Cannot find: {pdf_path.name}")
        return False
    if not os.access(pdf_path, os.R_OK):
        print(f"Cannot read: {pdf_path.name}")
        return False
    return True

# PyMuPDF (fitz)
def extract_text_pymupdf(pdf_path: Path, output_path: Path):
    try:
        doc = fitz.open(pdf_path)
        full_text = ""

        for i, page in enumerate(doc, start=1):
            text = page.get_text().strip()
            if text:
                full_text += f"\n--- Trang {i} ---\n{text}\n"

        if full_text:
            output_path.write_text(full_text, encoding="utf-8")
            print(f"PyMuPDF done: {pdf_path.name}")
            return True
        return False
    except Exception as e:
        print(f"PyMuPDF error {pdf_path.name}: {e}")
        return False

# EasyOCR
def extract_text_easyocr(pdf_path: Path, output_path: Path, max_pages: int = 3):
    try:
        pages = convert_from_path(str(pdf_path), dpi=300, first_page=1, last_page=max_pages)
        reader = easyocr.Reader(['vi'], gpu=False)

        all_text = ""
        for i, page in enumerate(pages, start=1):
            img_array = np.array(page)
            result = reader.readtext(img_array, detail=0, paragraph=True)
            page_text = "\n".join(result)
            all_text += f"\n--- Trang {i} ---\n{page_text}\n"

        output_path.write_text(all_text, encoding="utf-8")
        print(f"EasyOCR done: {pdf_path.name}")
        return True
    except Exception as e:
        print(f"EasyOCR error {pdf_path.name}: {e}")
        return False

def main():
    pdf_files = list(PDF_DIR.glob("*.pdf"))

    if not pdf_files:
        print(f"Cannot find pdf: {PDF_DIR}")
        return

    for pdf_path in pdf_files:
        output_path = OUTPUT_DIR / f"{pdf_path.stem}.txt"

        if not check_file_access(pdf_path):
            continue

        print(f"In process: {pdf_path.name}")
        if not extract_text_pymupdf(pdf_path, output_path):
            print(f"Use OCR: {pdf_path.name}")
            if not extract_text_easyocr(pdf_path, output_path, max_pages= 150):
                print(f"Cannot extract text: {pdf_path.name}")

if __name__ == "__main__":
    main()
