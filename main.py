import os
from lib import read_files, extract_file_content, chunk_text, save_chunks_to_mongo, show_chunks_from_mongo

def main():
    folder = os.environ.get("DATA_DIR", "/app/data")
    mongo_uri = os.environ.get("MONGO_URI", "mongodb://user123:password123@mongo:27017/")

    files = read_files(folder, filetypes=["pdf","txt","md"])
    print(f"[DEBUG] Gefundene Dateien: {files}")
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
    show_chunks_from_mongo(uri=mongo_uri)

if __name__ == "__main__":
    main()
