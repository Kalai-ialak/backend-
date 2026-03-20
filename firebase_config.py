import firebase_admin
from firebase_admin import credentials, firestore
import os
from dotenv import load_dotenv

load_dotenv()

firebase_key = os.getenv("FIRE_BASE_KEY_FILE")

if not firebase_admin._apps:
  if not firebase_key or not os.path.exists(firebase_key):
    raise FileNotFoundError(f"Firebase key file not found : {firebase_key}")
  
  cred = credentials.Certificate(firebase_key)
  firebase_admin.initialize_app(cred)
  print("Firebase initialized successfully")

else:
  print("Firebase already initialized")

df_firestore = firestore.client()
