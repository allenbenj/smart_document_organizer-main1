#!/usr/bin/env python3
"""
AI Document Organizer - Extension to automatically classify and organize documents
"""

import os
import shutil
import sqlite3
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class AIDocumentOrganizer:
    def __init__(self):
        self.db_path = '/mnt/e/Coding_Project/project_tools/data/file_tracker_new.db'
        self.base_path = '/mnt/e/Coding_Project'
        self.ollama_url = "http://localhost:11434/api/chat"
        
        # Define document categories and their target folders
        self.categories = {
            'project_overview': {
                'folder': 'organized_docs/project_documents',
                'description': 'High-level project descriptions, READMEs, overviews',
                'keywords': ['project', 'overview', 'readme', 'introduction', 'about']
            },
            'technical_specs': {
                'folder': 'organized_docs/technical_specifications', 
                'description': 'Technical specifications, API docs, architecture details',
                'keywords': ['api', 'specification', 'architecture', 'design', 'technical']
            },
            'installation_setup': {
                'folder': 'organized_docs/setup_guides',
                'description': 'Installation guides, setup instructions, configuration',
                'keywords': ['install', 'setup', 'configuration', 'deployment', 'environment']
            },
            'user_guides': {
                'folder': 'organized_docs/user_documentation',
                'description': 'User manuals, tutorials, how-to guides',
                'keywords': ['tutorial', 'guide', 'manual', 'usage', 'how-to']
            },
            'development_notes': {
                'folder': 'organized_docs/development_notes',
                'description': 'Development notes, changelogs, meeting notes',
                'keywords': ['changelog', 'notes', 'meeting', 'development', 'todo']
            },
            'ai_generated': {
                'folder': 'organized_docs/ai_generated',
                'description': 'AI-generated documentation and analysis',
                'keywords': ['generated', 'ai', 'analysis', 'deepseek', 'grok', 'ollama']
            }
        }
        
        # Create all target directories
        self.create_directories()
    
    def create_directories(self):
        """Create all target directories"""
        for category, info in self.categories.items():
            folder_path = os.path.join(self.base_path, info['folder'])
            os.makedirs(folder_path, exist_ok=True)
            print(f" Created: {info['folder']}")
    
    def call_ollama(self, prompt, model="phi3:mini", max_tokens=500):
        """Call Ollama for document classification"""
        data = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {
                "num_predict": max_tokens,
                "temperature": 0.1
            }
        }
        
        try:
            response = requests.post(self.ollama_url, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return result['message']['content']
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Exception: {e}"
    
    def classify_document(self, file_path, content):
        """Use AI to classify document type and purpose"""
        # Create classification prompt
        prompt = f"""
Classify this document and determine its purpose:

FILE: {os.path.basename(file_path)}
CONTENT (first 800 chars):
{content[:800]}

Choose the BEST category from these options:
1. PROJECT_OVERVIEW - High-level project descriptions, READMEs, overviews
2. TECHNICAL_SPECS - Technical specifications, API docs, architecture details  
3. INSTALLATION_SETUP - Installation guides, setup instructions, configuration
4. USER_GUIDES - User manuals, tutorials, how-to guides
5. DEVELOPMENT_NOTES - Development notes, changelogs, meeting notes
6. AI_GENERATED - AI-generated documentation and analysis
7. OTHER - Doesn't fit the above categories

Respond with ONLY the category name (e.g., "TECHNICAL_SPECS").
If unsure, respond with "OTHER".
"""
        
        result = self.call_ollama(prompt, max_tokens=50)
        
        # Parse result and map to our categories
        result = result.strip().upper()
        category_mapping = {
            'PROJECT_OVERVIEW': 'project_overview',
            'TECHNICAL_SPECS': 'technical_specs', 
            'INSTALLATION_SETUP': 'installation_setup',
            'USER_GUIDES': 'user_guides',
            'DEVELOPMENT_NOTES': 'development_notes',
            'AI_GENERATED': 'ai_generated'
        }
        
        return category_mapping.get(result, None)
    
    def get_documents_to_organize(self):
        """Get documents that should be organized"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get markdown, text, and documentation files
        cursor.execute("""
        SELECT file_path, file_name, content 
        FROM files 
        WHERE (file_extension IN ('.md', '.txt', '.rst', '.doc', '.docx') 
               OR file_name LIKE '%README%' 
               OR file_name LIKE '%CHANGELOG%'
               OR file_name LIKE '%INSTALL%'
               OR file_name LIKE '%SETUP%'
               OR file_name LIKE '%GUIDE%'
               OR file_name LIKE '%MANUAL%')
        AND content IS NOT NULL 
        AND length(content) > 100
        AND file_path NOT LIKE '%organized_docs%'
        """)
        
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def organize_document(self, file_path, category):
        """Move document to appropriate organized folder"""
        if category not in self.categories:
            return False
        
        # Create target path
        file_name = os.path.basename(file_path)
        target_folder = os.path.join(self.base_path, self.categories[category]['folder'])
        target_path = os.path.join(target_folder, file_name)
        
        # Handle filename conflicts
        counter = 1
        original_target = target_path
        while os.path.exists(target_path):
            name, ext = os.path.splitext(original_target)
            target_path = f"{name}_{counter}{ext}"
            counter += 1
        
        try:
            # Copy the file (don't move, to preserve original structure)
            shutil.copy2(file_path, target_path)
            
            # Log the organization
            self.log_organization(file_path, target_path, category)
            
            return target_path
        except Exception as e:
            print(f" Error organizing {file_path}: {e}")
            return False
    
    def log_organization(self, source, target, category):
        """Log document organization to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Create organization log table if it doesn't exist
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS document_organization (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_path TEXT,
            target_path TEXT,
            category TEXT,
            organized_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """)
        
        cursor.execute("""
        INSERT INTO document_organization (source_path, target_path, category)
        VALUES (?, ?, ?)
        """, (source, target, category))
        
        conn.commit()
        conn.close()
    
    def run_organization(self):
        """Main organization process"""
        print(" AI Document Organizer Starting...")
        
        # Get documents to organize
        documents = self.get_documents_to_organize()
        print(f" Found {len(documents)} documents to classify and organize")
        
        organized_count = 0
        category_counts = {}
        
        for file_path, file_name, content in documents:
            print(f" Classifying: {file_name}")
            
            # Classify document
            category = self.classify_document(file_path, content)
            
            if category:
                # Organize document
                target_path = self.organize_document(file_path, category)
                
                if target_path:
                    organized_count += 1
                    category_counts[category] = category_counts.get(category, 0) + 1
                    
                    print(f" Organized to: {self.categories[category]['folder']}")
                else:
                    print(f" Failed to organize: {file_name}")
            else:
                print(f" Skipped (category: OTHER): {file_name}")
        
        # Summary report
        print(f"\n Organization Complete!")
        print(f" Organized {organized_count} documents")
        
        for category, count in category_counts.items():
            folder = self.categories[category]['folder']
            print(f"   {folder}: {count} documents")
        
        return organized_count, category_counts

if __name__ == "__main__":
    organizer = AIDocumentOrganizer()
    organizer.run_organization()