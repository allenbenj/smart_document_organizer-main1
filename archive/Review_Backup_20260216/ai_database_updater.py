#!/usr/bin/env python3
"""
AI Database Updater - Uses AI team to analyze and update file_tracker.db
"""

import sqlite3
import requests
import json
import os
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

class AIDatabaseUpdater:
    def __init__(self):
        # Using a relative path from project root is better practice
        project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.db_path = os.path.join(project_root, 'project_tools', 'data', 'file_tracker.db')
        self.deepseek_key = os.getenv('DEEPSEEK_API_KEY')
        self.xai_key = os.getenv('XAI_API_KEY')

    def get_unanalyzed_files(self, limit=50):
        """Get files that haven't been analyzed yet"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get files that are not in file_analysis table
        query = """
        SELECT f.id, f.file_path, f.content 
        FROM files f 
        LEFT JOIN file_analysis fa ON f.file_path = fa.file_path 
        WHERE fa.file_path IS NULL 
        AND f.content IS NOT NULL 
        LIMIT ?
        """
        
        cursor.execute(query, (limit,))
        results = cursor.fetchall()
        conn.close()
        
        return results
    
    def call_deepseek(self, prompt, max_tokens=1000):
        """Call DeepSeek API for detailed analysis"""
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
    
    def call_ollama(self, prompt, model="phi3:mini", max_tokens=1000):
        """Call Ollama for high-volume processing"""
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
                return f"Ollama Error: {response.status_code}"
        except Exception as e:
            return f"Ollama Exception: {e}"
    
    def analyze_file(self, file_path, content):
        """Analyze a single file using AI"""
        # Determine file type
        file_ext = os.path.splitext(file_path)[1].lower()
        file_name = os.path.basename(file_path)
        
        # Create analysis prompt
        prompt = f"""
Analyze this code file and provide structured information:

FILE: {file_path}
CONTENT:
{content[:2000]}  # Limit content for API

Please provide analysis in this exact format:
FILE_TYPE: [programming language or file type]
PRIMARY_PURPOSE: [brief description of main purpose]
KEY_FUNCTIONALITY: [key features/functions, max 200 chars]
DEPENDENCIES: [imported modules/libraries, comma-separated]
ANALYSIS_NOTES: [additional insights, max 300 chars]

Focus on:
- What this file does
- Key functions/classes
- External dependencies
- Role in the larger system
"""
        
        # Use Ollama for bulk processing (cost-effective)
        result = self.call_ollama(prompt, max_tokens=500)
        
        # Parse the structured response
        analysis = self.parse_analysis_result(result, file_path, file_name, file_ext)
        return analysis
    
    def parse_analysis_result(self, result, file_path, file_name, file_ext):
        """Parse AI analysis result into structured data"""
        analysis = {
            'file_path': file_path,
            'file_name': file_name,
            'file_type': file_ext or 'unknown',
            'primary_purpose': 'Unknown',
            'key_functionality': '',
            'dependencies': '',
            'analysis_notes': result[:300]  # Fallback to raw result
        }
        
        # Try to parse structured format
        lines = result.split('\n')
        for line in lines:
            if line.startswith('FILE_TYPE:'):
                analysis['file_type'] = line.replace('FILE_TYPE:', '').strip()
            elif line.startswith('PRIMARY_PURPOSE:'):
                analysis['primary_purpose'] = line.replace('PRIMARY_PURPOSE:', '').strip()
            elif line.startswith('KEY_FUNCTIONALITY:'):
                analysis['key_functionality'] = line.replace('KEY_FUNCTIONALITY:', '').strip()[:200]
            elif line.startswith('DEPENDENCIES:'):
                analysis['dependencies'] = line.replace('DEPENDENCIES:', '').strip()
            elif line.startswith('ANALYSIS_NOTES:'):
                analysis['analysis_notes'] = line.replace('ANALYSIS_NOTES:', '').strip()[:300]
        
        return analysis
    
    def save_analysis(self, analysis):
        """Save analysis to database"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        query = """
        INSERT OR REPLACE INTO file_analysis 
        (file_path, file_name, file_type, primary_purpose, key_functionality, 
         dependencies, analysis_timestamp, analysis_notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        
        cursor.execute(query, (
            analysis['file_path'],
            analysis['file_name'],
            analysis['file_type'],
            analysis['primary_purpose'],
            analysis['key_functionality'],
            analysis['dependencies'],
            datetime.now().timestamp(),
            analysis['analysis_notes']
        ))
        
        conn.commit()
        conn.close()
    
    def update_file_status(self, file_id, status='analyzed'):
        """Update file status in files table"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute(
            "UPDATE files SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (status, file_id)
        )
        
        conn.commit()
        conn.close()
    
    def run_analysis_batch(self, batch_size=20):
        """Run analysis on a batch of files"""
        print(f" Getting {batch_size} unanalyzed files...")
        files = self.get_unanalyzed_files(batch_size)
        
        if not files:
            print(" No unanalyzed files found!")
            return 0
        
        print(f" Analyzing {len(files)} files...")
        analyzed_count = 0
        
        for file_id, file_path, content in files:
            if not content or content.strip() == '':
                print(f"  Skipping empty file: {file_path}")
                continue
                
            print(f" Analyzing: {file_path}")
            
            try:
                # Analyze the file
                analysis = self.analyze_file(file_path, content)
                
                # Save to database
                self.save_analysis(analysis)
                self.update_file_status(file_id, 'analyzed')
                
                analyzed_count += 1
                print(f" Analyzed: {analysis['primary_purpose']}")
                
            except Exception as e:
                print(f" Error analyzing {file_path}: {e}")
                self.update_file_status(file_id, 'error')
        
        print(f"🎉 Completed analysis of {analyzed_count} files!")
        return analyzed_count
    
    def generate_summary_report(self):
        """Generate summary report using DeepSeek"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get analysis summary
        cursor.execute("""
        SELECT file_type, COUNT(*) as count, 
               GROUP_CONCAT(primary_purpose, '; ') as purposes
        FROM file_analysis 
        GROUP BY file_type 
        ORDER BY count DESC
        """)
        
        summary_data = cursor.fetchall()
        conn.close()
        
        # Create summary prompt for DeepSeek
        prompt = f"""
Analyze this file analysis summary and create a comprehensive report:

FILE TYPE BREAKDOWN:
{chr(10).join([f"{ftype}: {count} files - {purposes[:200]}..." for ftype, count, purposes in summary_data])}

Please provide:
1. Overall system architecture insights
2. File type distribution analysis
3. Key components and their roles
4. Dependency patterns
5. Recommendations for organization

Make it professional and actionable.
"""
        
        print(" Generating summary report with DeepSeek...")
        report = self.call_deepseek(prompt, max_tokens=2000)
        
        # Save report
        timestamp = datetime.now().isoformat()
        report_file = f"file_analysis_report_{timestamp.replace(':', '-')}.md"
        
        with open(report_file, 'w') as f:
            f.write(f"# File Analysis Report\n")
            f.write(f"*Generated by DeepSeek AI on {timestamp}*\n\n")
            f.write(report)
        
        print(f"📄 Report saved to: {report_file}")
        return report_file

if __name__ == "__main__":
    print(" AI Database Updater Starting...")
    
    updater = AIDatabaseUpdater()
    
    # Run analysis batch
    analyzed = updater.run_analysis_batch(batch_size=30)
    
    if analyzed > 0:
        # Generate summary report
        report = updater.generate_summary_report()
        print(f" Analysis complete! Report: {report}")
    else:
        print("  No files to analyze")