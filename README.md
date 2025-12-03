## Hilfreiche Befehle
- docker compose up -d
- docker compose run rag-app

Beim ersten start vom container sich die modelle holen:

Im Ollama container zu Exec gehen

- ollama pull nomic-embed-text

- ollama pull phi3:mini

## Schritt 2: Inhalte der Dateien auslesen
1. **Textbasierte Dateien (.txt, .md)** → einfach einlesen, z. B. mit `open()`
2. **PDF-Dateien (.pdf)** → über **PyMuPDF (fitz)** oder andere PDF-Reader einlesen
3. **Optional:** andere Formate (z. B. CSV) → mit **pandas**, **Excel**, etc.

**Ziel:**  
Du willst aus jeder Datei einen **Textstring** bekommen, der später verarbeitet werden kann.

---

## Schritt 3: Preprocessing / Chunking
- Große Dateien oder PDFs werden in kleine Abschnitte (**"Chunks"**) geteilt  
- **Warum?**  
  - LLMs haben ein **Token-Limit**  
  - Chunking erlaubt **gezieltes Retrieval**  
- **Typisch:** 500–1000 Wörter pro Chunk, ggf. mit **Überlappung** zwischen den Chunks

---

## Schritt 4: Speicherung der Rohdaten
- Hier kommt **MongoDB** ins Spiel:
  - Speichere **jeden Chunk + Metadaten** (Dateiname, Pfad, Dateityp)
  - **Vorteil:** später einfacher Zugriff für Retrieval  
- **Struktur z. B.:**


    "filename": "database.md",
    "filepath": "/app/data/database.md",
    "filetype": "md",
    "chunk_id": 1,
    "text": "Hier steht der Textabschnitt ..."

---


## Schritt 5: Vektorisierung
- Für **RAG** brauchen wir **semantische Embeddings**
- **Schritte:**
  1. Textchunk in **Embedding-Vektor** umwandeln  
     → z. B. via **OpenAI**, **HuggingFace** oder **Llama-Embeddings**
  2. Vektor zusammen mit `chunk_id` in **PostgreSQL** mit **pgvector** speichern
- **Ziel:**  
  Später kann das LLM relevante Chunks per **Cosine-Similarity** abrufen und für die Antwort verwenden

---

## Schritt 6: Retrieval + LLM
- Nutzer stellt eine **Frage**
- Das System sucht per **Vektorähnlichkeit** die **relevantesten Chunks**
- Übergibt **Frage + Chunks** an das **LLM**  
  → Ergebnis: eine **kontextbezogene Antwort**, die auf den Dokumenten basiert

---

## Kurz gesagt: Pipeline nach File-Collection
1. **Dateien sammeln** → Done (`read_files`)
2. **Text aus Dateien extrahieren** → `.txt`, `.md`, `.pdf`
3. **Chunking** → Abschnitte bilden
4. **Rohdaten in MongoDB speichern** → inkl. Metadaten
5. **Embeddings erstellen & in pgvector speichern**

➡️ **Retrieval + LLM → RAG-System funktioniert**
