import os
import fitz  # PyMuPDF
from pymongo import MongoClient, errors
import uuid
import time
import psycopg2
from tqdm import tqdm
import ollama
from langchain_ollama import OllamaEmbeddings

# return list of tupels
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

# PDF → Text
def extract_pdf_content(pdf_datei):
    doc = fitz.open(pdf_datei)
    text = "".join([page.get_text() for page in doc])
    return text

# Textdateien → String
def extract_text_file(file_path):
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Fehler beim Lesen]: {e}"
    
# mapping for file type
def extract_file_content(file_path, file_type):
    if file_type == "pdf":
        return extract_pdf_content(file_path)
    elif file_type in ["txt", "md"]:
        return extract_text_file(file_path)
    else:
        return ""

# return list of dicts
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

# return db client object
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

# use client object to save chunks in db
# raw chunks: _id | filename | chunk_id | text | filetype
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



def connect_to_pg(max_retries=15, delay=3):
    # Umgebung einlesen
    db_host = os.getenv("POSTGRES_HOST", "postgres")
    db_port = int(os.getenv("POSTGRES_PORT", 5432))
    db_name = os.getenv("POSTGRES_DB", "embedding_db")
    db_user = os.getenv("POSTGRES_USER", "dev_user")
    db_pass = os.getenv("POSTGRES_PASSWORD", "dev_password")

    time.sleep(5)
    print(f"🌐 Verbinde zu PostgreSQL auf {db_host}:{db_port} / DB: {db_name} ...")

    for attempt in range(1, max_retries + 1):
        try:
            conn = psycopg2.connect(
                host=db_host,
                port=db_port,
                dbname=db_name,
                user=db_user,
                password=db_pass
            )
            conn.autocommit = True
            print("✅ Verbindung zu PostgreSQL hergestellt.")
            cur = conn.cursor()

            # Wichtig: pgvector aktivieren
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")
            print("✅ pgvector Extension aktiviert.")

            print("✅ Verbindung zu PostgreSQL hergestellt.")
            return conn, cur

        except psycopg2.OperationalError as e:
            print(f"❌ Verbindung fehlgeschlagen (Versuch {attempt}/{max_retries}): {e}")
            time.sleep(delay)

    raise Exception("🚨 Verbindung zu PostgreSQL nach mehreren Versuchen fehlgeschlagen.")



# Liest alle Text-Chunks aus MongoDB, erzeugt Embeddings mit Ollama
# und speichert sie in PostgreSQL (pgvector).
def generate_embeddings(mongo_uri=None):
    conn, cur = connect_to_pg()

    # ✅ Host aus ENV lesen
    ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")

    embed = OllamaEmbeddings(
        model="mxbai-embed-small",
        base_url=ollama_host
    )

    # Mongo lesen
    client = connect_to_mongo(mongo_uri)
    db = client["rag_db"]
    collection = db["raw_chunks"]
    chunks = list(collection.find({}, {"_id": 1, "text": 1}))

    print(f"📄 {len(chunks)} Chunks aus MongoDB geladen.")

    cur.execute("""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            id SERIAL PRIMARY KEY,
            chunk_mongo_id TEXT,
            embedding VECTOR(1024)
        );
    """)

    for chunk in tqdm(chunks, desc="Erstelle Embeddings"):
        text = chunk["text"]
        mongo_id = chunk["_id"]

        try:
            emb = embed.embed_query(text)
            cur.execute(
                "INSERT INTO chunk_embeddings (chunk_mongo_id, embedding) VALUES (%s, %s)",
                (mongo_id, emb)
            )
        except Exception as e:
            print(f"⚠️ Fehler bei Chunk {mongo_id}: {e}")
            continue

    conn.commit()
    conn.close()
    print("✅ Alle Embeddings in PostgreSQL gespeichert.")


def store_emmbedings():
    pass