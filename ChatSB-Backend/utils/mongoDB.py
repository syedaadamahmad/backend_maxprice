# utils/mongoDB.py
import os
from dotenv import load_dotenv
from pymongo import MongoClient, errors

load_dotenv()

def connect_db():
    """
    Connects to MongoDB Atlas and returns a client.
    Handles errors and prints connection status.
    """
    uri = os.getenv("MONGO_DB_URI")
    if not uri:
        print("❌ MONGO_DB_URI not set in env")
        return None

    try:
        client = MongoClient(uri, serverSelectionTimeoutMS=5000)
        client.admin.command("ping")  # test connection
        print("✅ Successfully connected to MongoDB Atlas")
        return client
    except errors.ServerSelectionTimeoutError as e:
        print("❌ Connection timed out. Check your URI and internet connection.")
        print("Error:", e)
        return None
    except Exception as e:
        print("❌ Failed to connect to MongoDB Atlas.")
        print("Error:", e)
        return None

def get_collection(client, collection: str):
    if client is None:
        print("⚠️ No MongoDB client available. Returning None.")
        return None

    db_name = os.getenv("DB_NAME")
    if not db_name:
        print("❌ DB_NAME not set in env")
        return None

    db = client[db_name]
    collection = db[collection]
    return collection

def insert_vector_data(collection:str, csv_file:str):
    """
    Helper wrapper to call create_vector_store.insert_csv_with_embeddings
    """
    from utils import create_vector_store
    mongo_client = connect_db()
    coll = get_collection(mongo_client, collection)
    create_vector_store.insert_csv_with_embeddings(csv_file, coll)

def get_all_deals(collection_name: str = "flight_coupons"):
    """
    Return list of deals from MongoDB (no _id, no embedding).
    """
    client = connect_db()
    coll = get_collection(client, collection_name)
    if coll is None:
        return []
    try:
        docs = list(coll.find({}, {"_id": 0, "embedding": 0}))
        return docs
    except Exception as e:
        print(f"[get_all_deals] error: {e}")
        return []