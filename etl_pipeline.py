import os
import json
import csv
import glob
import re
import requests
import hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Generator, Tuple

# ==========================================
# CONFIGURATION
# ==========================================
# Directories
PROJECT_ROOT = os.path.expanduser("~/PROJECTS/PIVOT")
RAW_DATA_DIR = os.path.join(PROJECT_ROOT, "data/raw")
# PROCESSED_DATA_DIR is no longer used as we upload directly
# PROCESSED_DATA_DIR = os.path.join(PROJECT_ROOT, "data/processed")

# Open WebUI API Config for Direct Ingestion
WEBUI_URL = "http://localhost:3000"
# NOTE: Replace with your actual Open WebUI API Key
API_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6IjBjYzk3NTlhLTEwNWEtNGMwNS05NjM1LThmN2NjOWRmOTU0OCIsImV4cCI6MTc2NjYzODk4NSwianRpIjoiM2IzYzNlMmQtYTU4My00ZTNhLTkzZDctMDJkOGY1NTA4MjA4In0.YEH5MWZUTmMlBGqKIaxYeuOhTpT4BKtsXHgfnJY44_0" 
COLLECTION_NAME = "My_Project_History"
# Endpoint for direct RAG ingestion (assuming a standard setup or custom integration)
INGESTION_ENDPOINT = f"{WEBUI_URL}/api/v1/radd/ingest" 

# RAG Chunking Parameters
CHUNK_SIZE = 2048
CHUNK_OVERLAP = 200

# Heuristics for JSON parsing (Keys to look for in messy data)
CONTENT_KEYS = ['text', 'content', 'message', 'body', 'comment', 'post', 'description']
DATE_KEYS = ['created_at', 'timestamp', 'date', 'posted_on']

# Headers that cause "duplicate content" errors in RAG ingestion
DUPLICATE_HEADERS_TO_FILTER = ["Unknown Date"] 

# ==========================================
# HELPERS
# ==========================================

def clean_text(text: str) -> str:
    """Removes HTML, excessive whitespace, and non-printable chars."""
    if not text or not isinstance(text, str):
        return ""
    
    # Remove HTML tags
    text = re.sub(r'<[^>]+>', '', text)
    # Collapse whitespace
    text = re.sub(r'\s+', ' ', text).strip()
    return text

def extract_from_json(filepath: str) -> Generator[str, None, None]:
    """Streams a large JSON file and extracts relevant text fields, prepending date."""
    try:
        with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
            try:
                data = json.load(f)
            except json.JSONDecodeError:
                print(f"Skipping {filepath}: Invalid JSON structure.")
                return

            if isinstance(data, dict):
                data = [data] # Treat as list of 1
            
            for item in data:
                # Find the content
                content = None
                for k in CONTENT_KEYS:
                    if k in item and item[k]:
                        content = item[k]
                        break
                
                # Find a date (for context)
                date = "Unknown Date" # Default date used for filtering later
                for k in DATE_KEYS:
                    if k in item and item[k]:
                        date = str(item[k])
                        break

                if content and isinstance(content, str) and len(content) > 20: # Filter short noise
                    cleaned = clean_text(content)
                    # Yields the line with [Date] prefix
                    yield f"[{date}] {cleaned}\n" 

    except Exception as e:
        print(f"Error reading {filepath}: {e}")

def chunk_text(text: str, source_id: str) -> List[Dict]:
    """
    Breaks a long document into smaller, overlapping chunks.
    Adds unique metadata (source_id) to each chunk.
    """
    chunks = []
    
    # Tokenize by splitting the text into paragraphs (double newline)
    paragraphs = re.split(r'\n\s*\n', text)
    
    current_chunk = ""
    
    for p in paragraphs:
        if not p.strip():
            continue
            
        # Check if adding the paragraph exceeds the chunk size
        if len(current_chunk) + len(p) + 2 > CHUNK_SIZE:
            # Save the current chunk
            if current_chunk:
                chunks.append({
                    "text": current_chunk.strip(),
                    "metadata": {"source_id": source_id, "chunk_method": "pipeline_chunker"}
                })
            
            # Start the new chunk with an overlap (simple back-tracking overlap)
            overlap_text = current_chunk[-CHUNK_OVERLAP:] if len(current_chunk) > CHUNK_OVERLAP else ""
            current_chunk = overlap_text + "\n\n" + p
        else:
            current_chunk += "\n\n" + p

    # Add the final chunk
    if current_chunk.strip():
        chunks.append({
            "text": current_chunk.strip(),
            "metadata": {"source_id": source_id, "chunk_method": "pipeline_chunker"}
        })
        
    return chunks

def process_text_for_rag(filepath: str, content: List[str]) -> Tuple[str, str]:
    """
    1. Generates a unique, hash-based ID and title.
    2. Removes duplicate headers like '[Unknown Date]'.
    3. Returns the unique ID and the final cleaned text.
    """
    try:
        relative_path = Path(filepath).relative_to(RAW_DATA_DIR)
    except ValueError:
        # Fallback if the path logic fails (e.g., if paths are messy)
        relative_path = Path(filepath).name
    
    relative_path_str = str(relative_path)

    # 1. Generate Unique Contextual Title (Ensuring the starting tokens are unique)
    # Use a short hash of the path to guarantee the starting characters are unique for every file.
    path_hash = hashlib.sha1(relative_path_str.encode()).hexdigest()[:8]
    
    # Use the hash as the unique ID for vector database indexing
    unique_source_id = f"DOC-{path_hash}"
    
    # The title line now contains the unique ID and the source path
    title_line = f"SOURCE ID: {unique_source_id} | SOURCE PATH: {relative_path_str}\n\n"
    
    final_content = []
    
    # 2. Filter out duplicate headers from the content
    for line in content:
        line_stripped = line.strip()
        
        # Check if the line starts with the problematic duplicate header pattern (e.g., "[Unknown Date]")
        is_duplicate_header = False
        for header in DUPLICATE_HEADERS_TO_FILTER:
            if line_stripped.startswith(f"[{header}]"):
                # We filter if the content after the header is too short (i.e., it's a useless line)
                if len(line_stripped) < 40: 
                    is_duplicate_header = True
                break
        
        if not is_duplicate_header and line_stripped:
            final_content.append(line_stripped)

    # If all lines were removed, return an empty string
    if not final_content:
        return "", ""

    # Prepend the unique title to the cleaned content
    final_text = title_line + "\n".join(final_content)
    
    return unique_source_id, final_text

def upload_chunks_to_rag_api(chunks: List[Dict], collection: str):
    """
    Uploads a batch of chunks directly to the Open WebUI RAG ingestion endpoint.
    This bypasses the UI's file upload process.
    """
    if not chunks:
        return True
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    # The API payload expects the collection name and the list of text chunks with metadata
    payload = {
        "collection": collection,
        "chunks": chunks
    }
    
    try:
        response = requests.post(INGESTION_ENDPOINT, headers=headers, json=payload, timeout=30)
        
        if response.status_code == 200:
            print(f"Successfully uploaded {len(chunks)} chunks for source ID: {chunks[0]['metadata']['source_id']}")
            return True
        else:
            print(f"API Error uploading chunks (Status {response.status_code}): {response.text}")
            return False
            
    except requests.exceptions.RequestException as e:
        print(f"Network error during API upload: {e}")
        return False


def process_file_and_ingest(filepath: str):
    """Processes a single file, chunks it, and uploads the chunks."""
    ext = os.path.splitext(filepath)[1].lower()
    
    buffer = []
    
    if ext == '.json':
        for snippet in extract_from_json(filepath):
            buffer.append(snippet)
    elif ext == '.txt':
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                buffer.append(clean_text(content)) 
        except:
            print(f"Error reading TXT file: {filepath}")
            pass
    elif ext == '.csv':
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    row_text = " ".join([v for k,v in row.items() if v])
                    if len(row_text) > 20:
                        buffer.append(clean_text(row_text) + "\n")
        except:
            print(f"Error reading CSV file: {filepath}")
            pass

    # --- Step 1: Apply RAG-specific processing (Unique ID and Deduplication) ---
    unique_source_id, final_text = process_text_for_rag(filepath, buffer)

    if not final_text:
        print(f"Skipped empty or completely filtered file: {filepath}")
        return

    # --- Step 2: Chunk the Document ---
    chunks = chunk_text(final_text, unique_source_id)
    
    if not chunks:
        print(f"Could not generate chunks for file: {filepath}")
        return

    # --- Step 3: Direct API Ingestion ---
    upload_chunks_to_rag_api(chunks, COLLECTION_NAME)

# ==========================================
# MAIN EXECUTION
# ==========================================

def run_pipeline():
    print(">>> Starting End-to-End Vectorization Pipeline (Direct API Ingestion)...")
    
    if API_KEY == "YOUR_OPEN_WEBUI_API_KEY_HERE":
        print("\n--- ERROR ---")
        print("Please set your Open WebUI API_KEY in the CONFIGURATION section.")
        print("-----------------\n")
        return

    # 1. Find files
    files = glob.glob(os.path.join(RAW_DATA_DIR, "**/*"), recursive=True)
    files = [f for f in files if os.path.isfile(f)]
    
    print(f"Found {len(files)} files to process and ingest directly.")
    
    # 2. Process in Parallel and Upload
    with ThreadPoolExecutor(max_workers=8) as executor:
        # Use list() to force evaluation and wait for all tasks to complete
        list(executor.map(process_file_and_ingest, files))
        
    print(">>> Vectorization and Direct Ingestion Complete.")
    print(f">>> All cleaned and chunked data has been sent to the RAG collection: {COLLECTION_NAME}")

if __name__ == "__main__":
    run_pipeline()
