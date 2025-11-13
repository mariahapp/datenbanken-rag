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
    """
    Lädt Textchunks aus MongoDB, erzeugt Embeddings über Ollama
    und speichert sie in PostgreSQL (pgvector), ohne Duplikate.
    Optimierte Version für große Datenmengen.
    """

    # --- PostgreSQL Verbindung ---
    conn, cur = connect_to_pg()

    # --- Konfiguration ---
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "nomic-embed-text")
    vector_dim = int(os.getenv("EMBEDDING_DIM", 768))

    print(f"🚀 Verwende Ollama-Host: {ollama_host}")
    print(f"🧠 Verwende Embedding-Modell: {ollama_model}")
    print(f"📏 Embedding-Dimension: {vector_dim}")

    # --- Verbindung zu Ollama vorbereiten ---
    embed = OllamaEmbeddings(
        model=ollama_model,
        base_url=ollama_host
    )

    # --- Mongo lesen ---
    client = connect_to_mongo(mongo_uri)
    db = client["rag_db"]
    collection = db["raw_chunks"]
    chunks = list(collection.find({}, {"_id": 1, "text": 1}))
    print(f"📄 {len(chunks)} Chunks aus MongoDB geladen.")

    # --- Tabelle in Postgres anlegen ---
    cur.execute(f"""
        CREATE TABLE IF NOT EXISTS chunk_embeddings (
            id SERIAL PRIMARY KEY,
            chunk_mongo_id TEXT UNIQUE,
            embedding VECTOR({vector_dim})
        );
    """)
    conn.commit()

    # --- Bereits vorhandene Chunks aus Postgres laden ---
    cur.execute("SELECT chunk_mongo_id FROM chunk_embeddings;")
    existing_ids = {row[0] for row in cur.fetchall()}
    print(f"🧮 {len(existing_ids)} vorhandene Embeddings gefunden.")

    # --- Nur neue Chunks verarbeiten ---
    new_chunks = [c for c in chunks if str(c["_id"]) not in existing_ids]
    print(f"🆕 {len(new_chunks)} neue Chunks, die Embeddings benötigen.")

    # --- Embeddings generieren ---
    inserted = 0
    for chunk in tqdm(new_chunks, desc="✨ Erstelle neue Embeddings"):
        text = chunk.get("text", "").strip()
        if not text:
            continue

        mongo_id = str(chunk["_id"])
        try:
            emb = embed.embed_query(text)
            cur.execute(
                "INSERT INTO chunk_embeddings (chunk_mongo_id, embedding) VALUES (%s, %s) ON CONFLICT DO NOTHING;",
                (mongo_id, emb)
            )
            inserted += 1

        except Exception as e:
            print(f"⚠️ Fehler bei Chunk {mongo_id}: {e}")
            continue

    conn.commit()
    conn.close()
    client.close()

    print(f"✅ {inserted} neue Embeddings gespeichert.")
    print(f"↩️ {len(existing_ids)} Chunks waren bereits vorhanden.")


def rag_query(prompt, top_k=3, mongo_uri=None):
    """
    Führt eine semantische Suche durch und generiert eine LLM-Antwort.
    """

    # --- Konfiguration ---
    ollama_host = os.getenv("OLLAMA_HOST", "http://ollama:11434")
    embedding_model = os.getenv("OLLAMA_MODEL", "nomic-embed-text")
    generation_model = os.getenv("GENERATION_MODEL", "phi3:mini")

    print(f"🚀 Verwende Ollama-Host: {ollama_host}")
    print(f"🧠 Embedding-Modell: {embedding_model}")
    print(f"💬 Generations-Modell: {generation_model}")

    # --- 1️⃣ Embedding für die User-Frage ---
    embedder = OllamaEmbeddings(model=embedding_model, base_url=ollama_host)
    query_vector = embedder.embed_query(prompt)

    # --- 2️⃣ Ähnliche Chunks aus Postgres holen ---
    conn, cur = connect_to_pg()
    cur.execute("""
        SELECT chunk_mongo_id,
               1 - (embedding <=> %s::vector) AS similarity
        FROM chunk_embeddings
        ORDER BY similarity DESC
        LIMIT %s;
    """, (query_vector, top_k))
    similar_chunks = cur.fetchall()
    conn.close()

    if not similar_chunks:
        return "❌ Keine passenden Dokumente gefunden."

    # --- 3️⃣ Texte aus Mongo holen ---
    client = connect_to_mongo(mongo_uri)
    db = client["rag_db"]
    coll = db["raw_chunks"]

    chunk_ids = [cid for (cid, _) in similar_chunks]
    docs = list(coll.find({"_id": {"$in": chunk_ids}}, {"text": 1}))
    client.close()

    # --- 4️⃣ Kontext zusammenbauen ---
    context = "\n\n".join([d["text"] for d in docs])
    full_prompt = f"Beantworte die folgende Frage basierend auf dem Kontext.\n\n" \
                  f"Frage: {prompt}\n\n" \
                  f"Kontext:\n{context}"

    # --- 5️⃣ Antwort vom LLM ---
    response = ollama.chat(
        model=generation_model,
        messages=[{"role": "user", "content": full_prompt}],
        options={"temperature": 0.2}
    )

    answer = response["message"]["content"]
    print("\n🤖 Antwort:\n", answer)
    return answer
