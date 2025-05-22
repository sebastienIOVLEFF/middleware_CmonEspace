import sqlite3

def setup_database():
    connection = sqlite3.connect("images.db")
    cursor = connection.cursor()

    # Création de la table des images
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS images (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            file_path TEXT NOT NULL,
            capture_date TEXT NOT NULL,
            sent INTEGER DEFAULT 0
        )
    """)

    connection.commit()
    connection.close()

if __name__ == "__main__":
    setup_database()
    print("Database setup completed.")
