# pipeline for reading, splitting and saving of the documents
import os
from lib import (
    read_files,
    extract_file_content,
    chunk_text,
    save_chunks_to_mongo,
    connect_to_pg
    #generate_and_store_embeddings
)

def main():
    folder = os.environ.get("DATA_DIR", "/app/data") 
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://user123:password123@mongo:27017/")

    files = read_files(folder, filetypes=["pdf","txt","md"])
    print(f"[DEBUG] Gefundene Dateien: {files}")

    # metadata for chunks: filename, filetype
    all_chunks = []

    for ftype, path, name in files:
        content = extract_file_content(path, ftype)
        chunks = chunk_text(content, chunk_size=500, overlap=50, debug=True)
        for chunk in chunks:
            chunk["filename"] = name
            chunk["filetype"] = ftype
        all_chunks.extend(chunks)
        print(f"[DEBUG] {len(chunks)} Chunks aus {name} erzeugt.")

    save_chunks_to_mongo(all_chunks, uri=mongo_uri)

    connect_to_pg()
    # Nach Mongo-Speicherung → Embeddings erzeugen und in Postgres speichern
    #generate_and_store_embeddings(all_chunks)

 

if __name__ == "__main__":
    main()


