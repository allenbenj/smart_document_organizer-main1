
import os
import requests
import json
from pathlib import Path

def main():
    api_base = "http://localhost:8000/api"
    target_dir = "/mnt/e/Organization_Folder/02_Working_Folder/02_Analysis/08_Interviews"
    
    files = [str(p) for p in Path(target_dir).glob("*") if p.is_file()]
    print(f"Found {len(files)} files to process.")
    
    if not files:
        return

    url = f"{api_base}/agents/process-documents"
    
    # We need to send as multipart/form-data
    # This mimics the GUI UploadManyFilesWorker
    
    upload_files = []
    for f in files:
        fh = open(f, "rb")
        upload_files.append(("files", (os.path.basename(f), fh)))
    
    options = {
        "extract_text": True,
        "extract_metadata": True,
        "analyze_content": True,
        "generate_summary": True,
        "index_vector": True,
        "enable_ocr": True
    }
    
    data = {"options": json.dumps(options)}
    
    print("Starting batch processing via API...")
    try:
        response = requests.post(url, files=upload_files, data=data, timeout=600)
        response.raise_for_status()
        result = response.json()
        
        processed = result.get("processed_count", 0)
        failed = result.get("failed_count", 0)
        
        print(f"Processing Complete: {processed} success, {failed} failed.")
        
        if failed > 0:
            print("Errors:")
            for item in result.get("items", []):
                if not item.get("success"):
                    print(f"- {item.get('filename')}: {item.get('error')}")
                    
    except Exception as e:
        print(f"API Call Failed: {e}")
    finally:
        for _, (name, fh) in upload_files:
            fh.close()

if __name__ == "__main__":
    main()
