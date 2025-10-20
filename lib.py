import os
import fitz  # PyMuPDF
from pymongo import MongoClient, errors
import uuid
import time

def read_files(folder_path, filetypes=None):
    if filetypes is None:
        filetypes = ["pdf", "txt", "md"]

    collected_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            ext = file.split(".")[-1].lower()
            if ext in filetypes:
                full_path = os.path.join(root, file)
                collected_files.append((ext, full_path, file))
    return collected_files

def extract_pdf_content(pdf_datei):
    doc = fitz.open(pdf_datei)
    text = "".join([page.get_text() for page in doc])
    return text

def extract_text_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Fehler beim Lesen]: {e}"

def extract_file_content(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_content(file_path)
    elif file_type in ["txt", "md"]:
        return extract_text_file(file_path)
    else:
        return ""

def chunk_text(text, chunk_size=500, overlap=50, debug=False):
    words = text.split()
    chunks = []
    start = 0
    chunk_id = 1
    while start < len(words):
        end = start + chunk_size
        chunk_words = words[start:end]
        chunk_text = " ".join(chunk_words)
        chunks.append({
            "chunk_id": chunk_id,
            "text": chunk_text
        })
        chunk_id += 1
        start += chunk_size - overlap
    if debug:
        print(f"[DEBUG] {len(chunks)} Chunks erzeugt")
    return chunks

def connect_to_mongo(uri=None, max_retries=10, delay=3):
    if uri is None:
        uri = os.getenv("MONGO_URI", "mongodb://user123:password123@mongo:27017/")
    for attempt in range(max_retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            client.admin.command("ping")
            print("✅ Verbindung zu MongoDB hergestellt.")
            return client
        except errors.ConnectionFailure:
            print(f"❌ MongoDB nicht erreichbar, Versuch {attempt+1}/{max_retries}")
            time.sleep(delay)
    raise Exception("🚨 Verbindung zu MongoDB fehlgeschlagen.")

def save_chunks_to_mongo(chunks, db_name="rag_db", collection_name="raw_chunks", uri=None):
    client = connect_to_mongo(uri)
    db = client[db_name]
    collection = db[collection_name]

    # Unique-Index verhindert Duplikate
    collection.create_index([("filename",1),("chunk_id",1)], unique=True)

    inserted_count = 0
    for chunk in chunks:
        chunk["_id"] = str(uuid.uuid4())
        try:
            collection.insert_one(chunk)
            inserted_count += 1
        except errors.DuplicateKeyError:
            pass
    total = collection.count_documents({})
    print(f"✅ {inserted_count} neue Chunks hinzugefügt.")
    print(f"📦 Gesamtzahl Chunks in MongoDB: {total}")

def show_chunks_from_mongo(uri=None, db_name="rag_db", collection_name="raw_chunks"):
    client = connect_to_mongo(uri)
    db = client[db_name]
    collection = db[collection_name]
    count = collection.count_documents({})
    print(f"📦 Anzahl Chunks: {count}")
    for doc in collection.find():
        print(f"--- {doc.get('filename')} - Chunk {doc.get('chunk_id')} ---")
        print(f"{doc.get('text')[:200]}...\n")
