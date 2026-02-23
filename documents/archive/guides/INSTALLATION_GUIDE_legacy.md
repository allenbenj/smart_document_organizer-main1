[ARCHIVED] This installation guide is out‑of‑date and has been moved to the archive.  The current setup procedure is described in `documents/guides/GETTING_STARTED.md`.

---

# 🚀 Enhanced Document Organizer - Installation Guide

## 📋 **Overview**

## ✅ Runtime Profile (Hardcoded Default)

This project should be run in **split mode**:

- **Backend/API:** Linux (WSL or native Linux)
- **GUI (PySide6):** Windows

Use this split as the default deployment and troubleshooting assumption.

### Split launch sequence

1. Start backend on Linux:
```bash
cd /mnt/e/Project/smart_document_organizer-main
python3 Start.py
```

2. Start GUI on Windows (separate terminal):
```powershell
cd E:\Project\smart_document_organizer-main
python gui\gui_dashboard.py
```

3. GUI should connect to backend at:
```text
http://127.0.0.1:8000
```

The Enhanced Document Organizer now includes:
- ✅ **OCR (Optical Character Recognition)** for images and scanned documents
- ✅ **Advanced image processing** with OpenCV
- ✅ **Intelligent document classification** with scoring system
- ✅ **Entity extraction** (dates, names, companies, amounts)
- ✅ **Smart filename generation** based on content
- ✅ **Comprehensive image categorization** (Screenshots, Photos, Diagrams, etc.)

## 🔧 **Installation Steps**

### **Step 1: Basic Python Dependencies**
```bash
 
```

### **Step 2: OCR Dependencies (Recommended)**
```bash
# Install Tesseract OCR engine
# Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Ubuntu: sudo apt install tesseract-ocr

# Install Python OCR packages
pip install pytesseract pillow
```

### **Step 3: Advanced Image Processing (Optional)**
```bash
# For enhanced image preprocessing
pip install opencv-python numpy
```

### **Step 4: PDF Processing (Optional)**
```bash
# For better PDF handling
pip install pypdf pdfplumber PyMuPDF
```

### **Step 5: Document Processing (Optional)**
```bash
# For Office document processing
pip install python-docx

# For HTML processing
pip install beautifulsoup4
```

## 🎯 **Quick Start**

### **Basic Usage (No Dependencies Required)**
```bash
cd smart_document_organizer
python robust_organizer.py
```

### **With OCR Capabilities**
```bash
# Install OCR first
pip install pytesseract pillow

# Then run
python robust_organizer.py
```

## 📊 **What the Enhanced System Does**

### **🔍 File Type Detection**
- **Real PDFs** vs **Fake PDFs** (HTML files with .pdf extension)
- **Image Types**: JPEG, PNG, GIF, BMP, WebP, TIFF
- **Office Documents**: DOCX, DOC, etc.
- **ZIP-based files**: DOCX, EPUB, etc.

### **📝 Text Extraction Methods**
1. **Direct text extraction** for text files
2. **PDF text extraction** with multiple fallback methods
3. **OCR for images** and scanned documents
4. **HTML content extraction** with tag removal
5. **Office document parsing**
6. **ZIP-based file content extraction**

### **🏷️ Advanced Classification Categories**

#### **Document Types:**
- `Legal_Documents` - Motions, court filings, legal briefs
- `Contracts` - Agreements, contracts, legal bindings
- `Financial_Documents` - Invoices, receipts, statements, tax documents
- `Medical_Documents` - Patient records, prescriptions, medical reports
- `Academic_Documents` - Research papers, theses, academic publications
- `Business_Documents` - Memos, reports, meeting minutes, proposals
- `Personal_Documents` - Birth certificates, passports, personal records
- `Technical_Documents` - Manuals, specifications, API documentation
- `Case_Law` - Court opinions, legal precedents
- `Emails` - Email communications and threads

#### **Image Types:**
- `Screenshots` - Screen captures and UI images
- `Photos` - Personal photos and pictures
- `Diagrams_and_Charts` - Technical diagrams, flowcharts, graphs
- `Logos_and_Graphics` - Brand logos and graphic elements
- `Scanned_Financial_Documents` - OCR'd financial papers
- `Scanned_Legal_Documents` - OCR'd legal documents
- `Scanned_Medical_Documents` - OCR'd medical records
- `Certificates_and_Awards` - Diplomas, certificates, awards

### **🧠 Entity Extraction**
The system automatically extracts:
- **Dates** in various formats (MM/DD/YYYY, Month DD, YYYY, etc.)
- **Names** with titles (Mr., Dr., etc.)
- **Companies** with indicators (Inc., LLC, Corp., etc.)
- **Amounts** (dollar amounts, percentages)

### **💡 Intelligent Filename Generation**
Files are renamed based on:
- **Content analysis** - Most frequent meaningful words
- **Entity extraction** - Dates, names, companies found in text
- **Category prefixes** - Legal_, Contract_, Financial_, etc.
- **Original extension preservation**

Example transformations:
- `document.pdf` → `Legal_2024-01-15_Motion_Summary.pdf`
- `scan.jpg` → `Scanned_Financial_Invoice_2024.jpg`
- `IMG_001.png` → `Screenshot_Dashboard_Analysis.png`

## 🔧 **Configuration Options**

### **OCR Languages**
```python
# In the code, you can modify OCR language:
text = pytesseract.image_to_string(image, lang='eng+spa')  # English + Spanish
```

### **Classification Thresholds**
```python
# Minimum confidence score for classification (default: 2)
if best_score >= 2:  # Adjust this value
    return best_category
```

### **Directory Structure**
```python
# Customize input/output directories
organizer = RobustOrganizer(
    watch_dir="your_input_folder",
    output_dir="your_organized_folder"
)
```

## 🚨 **Troubleshooting**

### **OCR Not Working**
```bash
# Check Tesseract installation
tesseract --version

# Install Tesseract if missing:
# Windows: https://github.com/UB-Mannheim/tesseract/wiki
# macOS: brew install tesseract
# Ubuntu: sudo apt install tesseract-ocr
```

### **Image Processing Issues**
```bash
# Install OpenCV for better image preprocessing
pip install opencv-python numpy
```

### **PDF Processing Problems**
```bash
```
