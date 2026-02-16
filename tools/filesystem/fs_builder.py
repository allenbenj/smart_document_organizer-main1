import sqlite3
import os
import hashlib
import requests
import json
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class AIFileSystemBuilder:
    def __init__(self):
        # Use current working directory as project root by default
        self.project_root = os.getcwd()
        self.new_db_path = os.path.join(self.project_root, 'tools', 'data', 'file_tracker_new.db')
        self.deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        self.xai_key = os.getenv('XAI_API_KEY')
        self.ollama_url = "http://localhost:11434/api/chat" # Added from another script for consistency

    # --- THIS IS THE METHOD THAT WAS INCORRECTLY INDENTED ---
    # It is now correctly inside the class.
    def run_full_build(self):
        """High-level method to execute the entire build process."""
        print(" AI File System Builder Starting...")
        self.create_fresh_database()
        files = self.scan_file_system()
        if not files:
            return "No files found to process. Build halted."
        self.save_files_to_db(files)
        
        # After building, let's analyze a small batch to get started
        print("\n Performing initial analysis on a batch of files...")
        self.analyze_files_with_ai(batch_size=20)
        
        return f" System rebuilt! New database created at: {self.new_db_path}. Initial analysis complete."
    
    def create_fresh_database(self):
        """Create a new clean database with proper schema"""
        print(" Creating fresh database...")
        db_parent_dir = os.path.dirname(self.new_db_path)
        os.makedirs(db_parent_dir, exist_ok=True)
        if os.path.exists(self.new_db_path):
            os.remove(self.new_db_path)
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        # ... (rest of the schema creation code is fine) ...
        cursor.execute("""
        CREATE TABLE files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            relative_path TEXT,
            file_name TEXT,
            file_extension TEXT,
            file_size INTEGER,
            content_hash TEXT,
            status TEXT DEFAULT 'discovered',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            content TEXT
        )
        """)
        cursor.execute("""
        CREATE TABLE file_analysis (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT UNIQUE NOT NULL,
            file_name TEXT,
            file_type TEXT,
            programming_language TEXT,
            primary_purpose TEXT,
            key_functionality TEXT,
            dependencies TEXT,
            complexity_score INTEGER,
            analysis_timestamp REAL,
            analysis_notes TEXT,
            ai_model_used TEXT
        )
        """)
        conn.commit()
        conn.close()
        print(" Fresh database created!")

    def scan_file_system(self):
        """Scan the entire project and catalog all files"""
        # ... (this method is fine, no changes needed) ...
        print(" Scanning file system...")
        files_discovered = []
        excluded_dirs = {'.git', '__pycache__', '.venv', 'venv', 'node_modules', '.taskmaster'}
        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in excluded_dirs]
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    stat = os.stat(file_path)
                    file_size = stat.st_size
                    if file_size > 10 * 1024 * 1024: continue # Skip large files
                    content = None
                    try:
                        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f: content = f.read()
                    except: pass
                    content_hash = hashlib.md5(content.encode() if content else b'').hexdigest()
                    files_discovered.append({ 'file_path': file_path, 'relative_path': os.path.relpath(file_path, self.project_root), 'file_name': file, 'file_extension': os.path.splitext(file)[1].lower(), 'file_size': file_size, 'content_hash': content_hash, 'content': content })
                except Exception as e: print(f" Error processing {file_path}: {e}")
        print(f" Discovered {len(files_discovered)} files")
        return files_discovered
    
    def save_files_to_db(self, files):
        """Save discovered files to database"""
        print(" Saving files to database...")
        
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        for file_info in files:
            cursor.execute("""
            INSERT OR REPLACE INTO files 
            (file_path, relative_path, file_name, file_extension, file_size, 
             content_hash, content, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, 'cataloged')
            """, (
                file_info['file_path'],
                file_info['relative_path'],
                file_info['file_name'],
                file_info['file_extension'],
                file_info['file_size'],
                file_info['content_hash'],
                file_info['content']
            ))
        
        conn.commit()
        conn.close()
        print(" Files saved to database!")
    
    def call_ollama(self, prompt, model="phi3:mini", max_tokens=800):
        """Call Ollama for bulk analysis"""
        url = "http://localhost:11434/api/chat"
        
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
            response = requests.post(url, json=data, timeout=120)
            if response.status_code == 200:
                result = response.json()
                return result['message']['content']
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Exception: {e}"
    
    def call_deepseek(self, prompt, max_tokens=1500):
        """Call DeepSeek for detailed analysis"""
        url = "https://api.deepseek.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.deepseek_key}"
        }
        
        data = {
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": max_tokens,
            "temperature": 0.1
        }
        
        try:
            response = requests.post(url, headers=headers, json=data, timeout=60)
            if response.status_code == 200:
                result = response.json()
                return result['choices'][0]['message']['content']
            else:
                return f"Error: {response.status_code}"
        except Exception as e:
            return f"Exception: {e}"
    
    def analyze_files_with_ai(self, batch_size=25):
        """Use AI team to analyze discovered files"""
        print(" Starting AI analysis of files...")
        
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        # Get files that need analysis
        cursor.execute("""
        SELECT file_path, file_name, file_extension, content 
        FROM files 
        WHERE content IS NOT NULL 
        AND length(content) > 10 
        AND file_extension IN ('.py', '.js', '.md', '.txt', '.json', '.yaml', '.yml', '.sql', '.sh', '.html', '.css')
        LIMIT ?
        """, (batch_size,))
        
        files = cursor.fetchall()
        conn.close()
        
        analyzed_count = 0
        
        for file_path, file_name, file_ext, content in files:
            print(f" Analyzing: {file_name}")
            
            # Create analysis prompt
            prompt = f"""
Analyze this code file:

FILE: {file_name}
TYPE: {file_ext}
CONTENT (first 1000 chars):
{content[:1000]}

Provide analysis in this format:
LANGUAGE: [programming language]
PURPOSE: [main purpose, max 100 chars]
FUNCTIONALITY: [key features, max 150 chars]
DEPENDENCIES: [imports/requires, comma-separated]
COMPLEXITY: [1-10 scale]
NOTES: [additional insights, max 200 chars]
"""
            
            # Use Ollama for cost-effective analysis
            result = self.call_ollama(prompt)
            
            # Parse and save analysis
            analysis = self.parse_analysis(result, file_path, file_name, file_ext)
            self.save_analysis(analysis)
            
            analyzed_count += 1
        
        print(f" Analyzed {analyzed_count} files!")
        return analyzed_count
    
    def parse_analysis(self, result, file_path, file_name, file_ext):
        """Parse AI analysis into structured data"""
        analysis = {
            'file_path': file_path,
            'file_name': file_name,
            'file_type': file_ext,
            'programming_language': 'unknown',
            'primary_purpose': 'Unknown',
            'key_functionality': '',
            'dependencies': '',
            'complexity_score': 5,
            'analysis_notes': result[:200],
            'ai_model_used': 'ollama-phi3-mini'
        }
        
        # Parse structured response
        lines = result.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('LANGUAGE:'):
                analysis['programming_language'] = line.replace('LANGUAGE:', '').strip()
            elif line.startswith('PURPOSE:'):
                analysis['primary_purpose'] = line.replace('PURPOSE:', '').strip()[:100]
            elif line.startswith('FUNCTIONALITY:'):
                analysis['key_functionality'] = line.replace('FUNCTIONALITY:', '').strip()[:150]
            elif line.startswith('DEPENDENCIES:'):
                analysis['dependencies'] = line.replace('DEPENDENCIES:', '').strip()
            elif line.startswith('COMPLEXITY:'):
                try:
                    complexity = int(line.replace('COMPLEXITY:', '').strip().split()[0])
                    analysis['complexity_score'] = max(1, min(10, complexity))
                except:
                    pass
            elif line.startswith('NOTES:'):
                analysis['analysis_notes'] = line.replace('NOTES:', '').strip()[:200]
        
        return analysis
    
    def save_analysis(self, analysis):
        """Save analysis to database"""
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
        INSERT OR REPLACE INTO file_analysis 
        (file_path, file_name, file_type, programming_language, primary_purpose, 
         key_functionality, dependencies, complexity_score, analysis_timestamp, 
         analysis_notes, ai_model_used)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            analysis['file_path'],
            analysis['file_name'],
            analysis['file_type'],
            analysis['programming_language'],
            analysis['primary_purpose'],
            analysis['key_functionality'],
            analysis['dependencies'],
            analysis['complexity_score'],
            datetime.now().timestamp(),
            analysis['analysis_notes'],
            analysis['ai_model_used']
        ))
        
        conn.commit()
        conn.close()
    
    def generate_system_overview(self):
        """Generate comprehensive system overview using DeepSeek"""
        print(" Generating system overview with DeepSeek...")
        
        conn = sqlite3.connect(self.new_db_path)
        cursor = conn.cursor()
        
        # Get summary statistics
        cursor.execute("""
        SELECT 
            COUNT(*) as total_files,
            COUNT(CASE WHEN file_extension = '.py' THEN 1 END) as python_files,
            COUNT(CASE WHEN file_extension = '.js' THEN 1 END) as js_files,
            COUNT(CASE WHEN file_extension = '.md' THEN 1 END) as markdown_files,
            AVG(complexity_score) as avg_complexity
        FROM files f
        LEFT JOIN file_analysis fa ON f.file_path = fa.file_path
        """)
        
        stats = cursor.fetchone()
        
        # Get top purposes
        cursor.execute("""
        SELECT primary_purpose, COUNT(*) as count
        FROM file_analysis 
        WHERE primary_purpose != 'Unknown'
        GROUP BY primary_purpose 
        ORDER BY count DESC 
        LIMIT 10
        """)
        
        purposes = cursor.fetchall()
        conn.close()
        
        # Create overview prompt
        prompt = f"""
Analyze this project overview and provide comprehensive insights:

PROJECT STATISTICS:
- Total Files: {stats[0]}
- Python Files: {stats[1]}
- JavaScript Files: {stats[2]}  
- Markdown Files: {stats[3]}
- Average Complexity: {stats[4]:.1f}/10

TOP FILE PURPOSES:
{chr(10).join([f"- {purpose}: {count} files" for purpose, count in purposes])}

Please provide:
1. Overall project architecture assessment
2. Technology stack analysis
3. Code organization insights
4. Potential improvement areas
5. System complexity evaluation
6. Key components identification

Make it professional and actionable for developers.
"""
        
        overview = self.call_deepseek(prompt, max_tokens=2000)
        
        # Save overview
        timestamp = datetime.now().isoformat()
        overview_file = f"system_overview_{timestamp.replace(':', '-')}.md"
        
        with open(overview_file, 'w', encoding='utf-8') as f:
            f.write(f"# AI-Generated System Overview\n")
            f.write(f"*Generated by DeepSeek AI on {timestamp}*\n\n")
            f.write(f"## Statistics\n")
            f.write(f"- **Total Files**: {stats[0]}\n")
            f.write(f"- **Python Files**: {stats[1]}\n")
            f.write(f"- **JavaScript Files**: {stats[2]}\n")
            f.write(f"- **Markdown Files**: {stats[3]}\n")
            f.write(f"- **Average Complexity**: {stats[4]:.1f}/10\n\n")
            f.write(overview)
        
        print(f"📄 System overview saved to: {overview_file}")
        return f"System rebuilt! New database created at: {self.new_db_path}"

if __name__ == "__main__":
    print(" AI File System Builder Starting...")
    
    builder = AIFileSystemBuilder()
    builder.run_full_build()
    # Step 1: Create fresh database
    builder.create_fresh_database()
    
    # Step 2: Scan file system
    files = builder.scan_file_system()
    
    # Step 3: Save to database
    builder.save_files_to_db(files)
    
    # Step 4: AI analysis
    analyzed = builder.analyze_files_with_ai(batch_size=30)
    
    # Step 5: Organize documents intelligently
    print("\n Starting intelligent document organization...")
    try:
        from tools.ai_organizer import AIDocumentOrganizer
        organizer = AIDocumentOrganizer()
        organized_count, categories = organizer.run_organization()
        print(f" Organized {organized_count} documents into categorized folders!")
    except ImportError:
        print("  Warning: tools.ai_organizer could not be imported.")
    except Exception as e:
        print(f" Document organization error: {e}")
    
    # Step 6: Generate overview
    if analyzed > 0:
        overview = builder.generate_system_overview()
        print(f" System rebuilt! New database: file_tracker_new.db")
        print(f" Overview report: {overview}")
    else:
        print(" No files analyzed")