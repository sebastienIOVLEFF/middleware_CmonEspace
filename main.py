import sqlite3
from fastapi import FastAPI
from pydantic import BaseModel
from apscheduler.schedulers.background import BackgroundScheduler
import requests
import base64
from datetime import datetime
import cv2
import uuid
import os
import uvicorn

# Connexion à la base de données
def get_db_connection():
    return sqlite3.connect("images.db")

app = FastAPI()

class CaptureResponse(BaseModel):
    status: str
    image_path: str

@app.get("/")
async def root():
    return {"message": "Local Camera API is running"}

@app.get("/capture", response_model=CaptureResponse)
async def capture_image():
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        return {"status": "error", "image_path": ""}

    os.makedirs("captures", exist_ok=True)
    filename = f"captures/{uuid.uuid4()}.jpg"
    cv2.imwrite(filename, frame)

    # Enregistrer l'image dans la base de données
    capture_time = datetime.utcnow().isoformat()
    save_image_to_db(filename, capture_time)

    return {"status": "success", "image_path": filename}

# Sauvegarde des images dans la base de données
def save_image_to_db(file_path, capture_date):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO images (file_path, capture_date) VALUES (?, ?)
        """, (file_path, capture_date))
        conn.commit()

# Capture périodique
def capture_image_periodically():
    print("Starting periodic capture...")
    cap = cv2.VideoCapture(0)
    ret, frame = cap.read()
    cap.release()

    if not ret:
        print("Failed to capture image.")
        return

    os.makedirs("captures", exist_ok=True)
    filename = f"captures/{uuid.uuid4()}.jpg"
    cv2.imwrite(filename, frame)

    capture_time = datetime.utcnow().isoformat()
    save_image_to_db(filename, capture_time)
    print(f"Image captured: {filename} at {capture_time}")

# Récupération des images non envoyées
def get_unsent_images(limit=10):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT id, file_path, capture_date FROM images WHERE sent = 0 LIMIT ?
        """, (limit,))
        return cursor.fetchall()

# Marquer les images comme envoyées
def mark_images_as_sent(image_ids):
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            UPDATE images SET sent = 1 WHERE id = ?
        """, [(image_id,) for image_id in image_ids])
        conn.commit()

# Fonction pour supprimer une entrée de la base de données
def delete_sent_image():
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM images WHERE sent = 1")
            conn.commit()
        except Exception as e:
            print(f"Error deleting images : {e}")

def get_image_path_from_db(image_id):
    # Cette fonction doit interroger votre base de données pour récupérer le chemin du fichier
    # Remplacez par le code adapté à votre système
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("SELECT file_path FROM images WHERE id = ?", (image_id,))
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            print(f"Error fetching image path for ID {image_id}: {e}")
            return None

# Envoi périodique des images
def periodic_send():
    print("Starting periodic send...")
    unsent_images = get_unsent_images(limit=10)

    if not unsent_images:
        print("No unsent images to send.")
        return

    payload = []
    for image in unsent_images:
        image_id, file_path, capture_date = image
        try:
            with open(file_path, "rb") as image_file:
                base64_image = base64.b64encode(image_file.read()).decode("utf-8")
            payload.append({
                "base64Image": base64_image,
                "date": capture_date,
                "id": image_id
            })
        except Exception as e:
            print(f"Error reading image {file_path}: {e}")

    if not payload:
        print("No valid images to send.")
        return

    try:
        response = requests.post("http://127.0.0.1:5104/count-from-picture", json=payload)
        if response.status_code == 200:
            print(f"Successfully sent {len(payload)} images.")
            print(response.content)

            # Marquer les images comme envoyées
            sent_image_ids = [item["id"] for item in payload]
            mark_images_as_sent(sent_image_ids)

            # Supprimer les fichiers physiques associés
            for image in payload:
                # Récupère le chemin réel du fichier image à partir de la base de données
                image_path = get_image_path_from_db(image["id"])  # Assurez-vous que cette fonction existe
                if image_path and os.path.exists(image_path):
                    os.remove(image_path)
                    print(f"Deleted file: {image_path}")
                else:
                    print(f"File not found or path invalid: {image_path}")
            delete_sent_image()
        else:
            print(f"Failed to send images. Status code: {response.status_code}")
    except Exception as e:
        print(f"Error while sending images: {e}")

# Configuration du planificateur
scheduler = BackgroundScheduler()
scheduler.add_job(capture_image_periodically, "interval", seconds=7)
scheduler.add_job(periodic_send, "interval", seconds=21)
scheduler.start()

if __name__ == "__main__":
    try:
        print("Starting local camera API...")
        uvicorn.run(app, host="127.0.0.1", port=8000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
