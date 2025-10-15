import os
import fitz  # PyMuPDF
from pymongo import MongoClient,errors
import uuid
import time

from pymongo import MongoClient

def read_files(folder_path, filetypes=None):
    """
    Liest alle Dateien in einem Ordner (inkl. Unterordner) ein
    und gibt eine Liste von Tuples zurück: (Dateityp, voller Pfad, Dateiname)

    :param folder_path: Pfad zum Ordner
    :param filetypes: Liste von Dateiendungen, z.B. ["pdf", "txt", "md"]
    :return: Liste von (file_type, full_path, filename)
    """
    if filetypes is None:
        filetypes = ["pdf", "txt", "md"]

    collected_files = []

    for root, dirs, files in os.walk(folder_path):
        for file in files:
            ext = file.split(".")[-1].lower()
            if ext in filetypes:
                full_path = os.path.join(root, file)
                collected_files.append((ext, full_path, file))

    #print(collected_files)
    return collected_files

# Ziel: Du willst aus jeder Datei einen Textstring bekommen, der später verarbeitet werden kann.
def extract_pdf_content(pdf_datei):
    doc = fitz.open(pdf_datei)  # PDF öffnen
    text = ""
    for page in doc:
        text += page.get_text()
    return text

def extract_text_file(file_path): # pfd and markdown
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

def chunk_text(text, chunk_size=500, overlap=50):
    """
    Teilt Text in überlappende Chunks auf.
    """
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
    print(f"chuncks ausgabe: {chunks}")
    return chunks

def connect_to_mongo(uri="mongodb://user123:password123@mongo:27017/", max_retries=10, delay=3):
    """Versucht mehrfach, sich mit MongoDB zu verbinden"""
    for attempt in range(max_retries):
        try:
            client = MongoClient(uri, serverSelectionTimeoutMS=2000)
            # Verbindung testen
            client.admin.command("ping")
            print("✅ Verbindung zu MongoDB hergestellt.")
            return client
        except errors.ConnectionFailure:
            print(f"❌ MongoDB noch nicht bereit... Versuch {attempt + 1}/{max_retries}")
            time.sleep(delay)
    raise Exception("🚨 Verbindung zu MongoDB nach mehreren Versuchen fehlgeschlagen.")

    #print(f"✅ In MongoDB gespeicherte Chunks: {count}")

def save_chunks_to_mongo(chunks, db_name="rag_db", collection_name="raw_chunks"):
    client = connect_to_mongo()
    db = client[db_name]
    collection = db[collection_name]

    for chunk in chunks:
        # Prüfen, ob dieser Chunk schon existiert
        if not collection.find_one({"filename": chunk["filename"], "chunk_id": chunk["chunk_id"]}):
            chunk["_id"] = str(uuid.uuid4())
            collection.insert_one(chunk)

    count = collection.count_documents({})
    print(f"✅ In MongoDB gespeicherte Chunks: {count}")

def show_chunks_from_mongo(uri="mongodb://user123:password123@mongo:27017/", db_name="rag_db", collection_name="raw_chunks"):
    # Verbindung aufbauen
    client = connect_to_mongo(uri)  # <- wieder die connect_to_mongo Funktion nutzen
    db = client[db_name]
    collection = db[collection_name]

    # Anzahl der gespeicherten Chunks
    count = collection.count_documents({})
    print(f"📦 Anzahl der Chunks in MongoDB: {count}\n")

    # Alle Chunks ausgeben (optional: nur Vorschau)
    for doc in collection.find():
        print(f"--- Chunk ID: {doc.get('chunk_id')} ---")
        print(f"Datei: {doc.get('filename')}")
        print(f"Text (Vorschau 200 Zeichen):\n{doc.get('text')[:200]}")
        print("-----------------\n")





if __name__ == "__main__":
    folder = "data"
    files = read_files(folder, filetypes=["pdf", "txt", "md"])

    all_chunks = []  # sammelt alle Chunks aus allen Dateien

    for ftype, path, name in files:
        print(f"--- {name} ({ftype}) ---")
        content = extract_file_content(path, ftype)
        chunks = chunk_text(content, chunk_size=500, overlap=50)

        # Metadaten ergänzen
        for chunk in chunks:
            chunk["filename"] = name
            chunk["filetype"] = ftype

        all_chunks.extend(chunks)

        print(f"{len(chunks)} Chunks aus {name} erzeugt.")
        print("-----------------\n")

    # Alle Chunks auf einmal in MongoDB speichern
    save_chunks_to_mongo(all_chunks)

    show_chunks_from_mongo()