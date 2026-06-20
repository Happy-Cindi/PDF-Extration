from fastapi import FastAPI
import requests
import pdfplumber
import fitz  # PyMuPDF
import os
from io import BytesIO
from PIL import Image
import pytesseract

app = FastAPI()

IMAGE_DIR = "images"
os.makedirs(IMAGE_DIR, exist_ok=True)


# -----------------------
# OCR FUNCTION
# -----------------------
def ocr_image(image_bytes):
    try:
        image = Image.open(BytesIO(image_bytes))
        return pytesseract.image_to_string(image).strip()
    except Exception:
        return ""


# -----------------------
# MAIN ENDPOINT
# -----------------------
@app.get("/extract-all")
def extract_all(url: str):
    # -----------------------
    # DOWNLOAD PDF
    # -----------------------
    response = requests.get(url)
    pdf_bytes = BytesIO(response.content)

    # -----------------------
    # INIT PAGE STRUCTURE
    # -----------------------
    pages = []

    with pdfplumber.open(pdf_bytes) as pdf:
        for i, page in enumerate(pdf.pages):
            pages.append({
                "page": i + 1,
                "text": page.extract_text() or "",
                "tables": [],
                "images": [],
                "image_ocr": []
            })

    # reset for PyMuPDF
    pdf_bytes.seek(0)

    # -----------------------
    # TABLES (attach per page)
    # -----------------------
    with pdfplumber.open(pdf_bytes) as pdf:
        for i, page in enumerate(pdf.pages):
            pages[i]["tables"] = page.extract_tables() or []

    # reset again for images
    pdf_bytes.seek(0)

    # -----------------------
    # IMAGES + OCR (per page)
    # -----------------------
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")

    for page_index in range(len(doc)):
        page = doc[page_index]

        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]

            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image["ext"]

            filename = f"page{page_index+1}_{img_index}.{ext}"
            filepath = os.path.join(IMAGE_DIR, filename)

            # save image
            with open(filepath, "wb") as f:
                f.write(image_bytes)

            # OCR
            text_from_image = ocr_image(image_bytes)

            pages[page_index]["images"].append({
                "file": filename,
                "path": filepath
            })

            pages[page_index]["image_ocr"].append(text_from_image)

    # -----------------------
    # FINAL RESPONSE
    # -----------------------
    return {
        "pages": pages
    }