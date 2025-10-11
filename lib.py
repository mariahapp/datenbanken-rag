import os
import sys

def read_text_file(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception as e:
        return f"[Fehler beim Lesen]: {e}"

def main():
    if len(sys.argv) < 2:
        print("Bitte Ordnernamen als Argument angeben, z.B. 'python lib.py data'")
        sys.exit(1)

    folder_path = sys.argv[1]

    if not os.path.exists(folder_path):
        print(f"Ordner '{folder_path}' existiert nicht!")
        sys.exit(1)

    print(f"Dateien im Ordner '{folder_path}':\n")

    for filename in os.listdir(folder_path):
        file_path = os.path.join(folder_path, filename)
        print(f"--- {filename} ---")
        # Für Textdateien (txt, md)
        if filename.lower().endswith((".txt", ".md")):
            content = read_text_file(file_path)
            print(content[:200])  # nur die ersten 200 Zeichen
        else:
            print("[Dateityp nicht unterstützt, nur Name angezeigt]")
        print()

if __name__ == "__main__":
    main()
