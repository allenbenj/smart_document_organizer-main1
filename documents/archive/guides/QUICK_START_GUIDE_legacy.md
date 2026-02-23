[ARCHIVED] This quick start guide is out‑of‑date and has been archived.  Refer to `documents/guides/GETTING_STARTED.md` for current startup instructions.

---

# 🚀 Smart Document Organizer - Quick Start Guide

## ✅ Required Runtime Split

Use this runtime split as the default:

- **Backend/API:** Linux (WSL or native Linux)
- **GUI:** Windows

### Launch order

1. Backend on Linux:
```bash
cd /mnt/e/Project/smart_document_organizer-main
python3 Start.py
```

2. GUI on Windows:
```powershell
cd E:\Project\smart_document_organizer-main
python gui\gui_dashboard.py
```

3. Backend URL expected by GUI:
```text
http://127.0.0.1:8000
```

## 📋 **How to Begin Using the Application**

### **Option 1: Robust Organizer (Recommended for Beginners)**

The simplest way to start organizing documents:

#### **Step 1: Navigate to Directory**
```bash
cd smart_document_organizer
```

#### **Step 2: Run the Robust Organizer**
```bash
python robust_organizer.py
```

**What it does:**
- ✅ Automatically processes all files in the `watch/` directory
- ✅ Handles corrupted PDFs, fake PDFs, HTML files, and any document type
- ✅ Creates organized folders: Legal_Documents, Contracts, Case_Law, etc.
- ✅ Stores results in `robust_organized/` directory
- ✅ Saves processing data to SQLite database

#### **Step 3: Add Your Documents**
1. Put your documents in the `watch/` folder
2. Run the command again to process new files

---

### **Option 2: Advanced Smart Organizer with SmolLM2**

For AI-powered organization with SmolLM2:

#### **Step 1: Install Dependencies**
```bash
pip install streamlit requests sqlite3
```

#### **Step 2: Start SmolLM2 Server** (if you have it)
```bash
# Start your SmolLM2 model server on localhost:8080
```

#### **Step 3: Run CLI Interface**
```bash
python smart_document_organizer/User_Interfaces/CLI_Runner_Interface.py watch
```

#### **Step 4: Or Launch Web Dashboard**
```bash
python smart_document_organizer/User_Interfaces/Streamlit_Web_Dashboard.py
```

---

### **Option 3: Simple Examples**

Try the example organizers first:

#### **Rule-Based Organizer**
```bash
python smart_document_organizer/Examples/Rule_Based_Organizer_Example.py
```

#### **Simple Organizer**
```bash
python smart_document_organizer/Examples/Simple_Organizer_Example.py
```

...
