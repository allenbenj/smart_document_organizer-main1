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

---

## 📁 **Directory Structure After Running**

```
smart_document_organizer/
├── watch/                    # Put your documents here
├── robust_organized/         # Organized output appears here
│   ├── Legal_Documents/
│   ├── Contracts/
│   ├── Case_Law/
│   ├── Emails/
│   ├── Discovery/
│   ├── Notes/
│   ├── Unreadable/
│   └── Other_Documents/
├── robust_organizer.db      # Processing database
└── robust_organizer.py      # Main application
```

---

## 🎯 **Recommended Workflow**

### **For First-Time Users:**

1. **Start Simple**: Use `python robust_organizer.py`
2. **Test with Sample Files**: Put 2-3 documents in `watch/` folder
3. **Check Results**: Look in `robust_organized/` folder
4. **Scale Up**: Add more documents and run again

### **For Advanced Users:**

1. **Set up SmolLM2**: Install and configure SmolLM2 model
2. **Use Web Dashboard**: Launch Streamlit interface for monitoring
3. **Batch Processing**: Use CLI for large document sets
4. **Custom Configuration**: Modify settings in configuration files

---

## 🔧 **Troubleshooting**

### **Python Not Found**
```bash
# Use full path if needed
C:\Python314\python.exe robust_organizer.py
```

### **Missing Dependencies**
```bash
# Install required packages
pip install neo4j sqlite3 pathlib
```

### **No Files to Process**
- Make sure documents are in the `watch/` directory
- Check file permissions
- Verify files aren't empty

---

## 📊 **What the Application Does**

1. **Scans** all files in the watch directory
2. **Detects** actual file types (handles fake PDFs, corrupted files)
3. **Extracts** text using multiple methods
4. **Classifies** documents based on content
5. **Organizes** files into logical folders
6. **Tracks** processing in database
7. **Provides** detailed reports

---

## 🎉 **Success Indicators**

You'll know it's working when you see:
- ✅ "Connected to Neo4j" (if Neo4j is running)
- ✅ "ROBUST Document Organizer ready!"
- ✅ "FOUND X FILES FOR ROBUST ANALYSIS"
- ✅ Files appearing in organized folders
- ✅ "ROBUST ORGANIZATION COMPLETE!"

---

## 📞 **Next Steps**

After your first successful run:
1. Check the organized folders
2. Review the processing database
3. Try the web dashboard for advanced features
4. Explore the SmolLM2 integration for AI-powered classification

**Ready to start? Just run:**
```bash
python robust_organizer.py
