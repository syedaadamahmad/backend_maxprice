# # main.py
# main.py
from typing import List
from fastapi import FastAPI
from pydantic import BaseModel
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
import csv
from dotenv import load_dotenv
from utils import model_with_tool, mongoDB

load_dotenv()

app = FastAPI()

origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request body model
class ChatRequest(BaseModel):
    chat_history: List[dict]  # [{"role": "human", "content": "..."}, {"role": "ai", "content": "..."}]

CSV_FILE_PATH = os.getenv(
    "UPDATED_DEALS_CSV",
    r"C:\Users\newbr\OneDrive\Desktop\mongo_dataentry\updated_deals.csv"
)

@app.get("/")
def home():
    return {"message": "its working fine :)"}


@app.post("/chat")
def chat_endpoint(request: ChatRequest):
    """
    Chat endpoint that uses model_with_tool.rag_agent.
    Returns both the assistant's message and any structured flight data.
    """
    result = model_with_tool.rag_agent(request.chat_history)
    # result is already a dict: {"content": "...", "flight_data": [...]}
    return JSONResponse(content=result)


@app.get("/get_latest_deals")
def get_latest_deals():
    """
    Primary endpoint for the frontend Book Now flow.
    - Tries to read CSV_FILE_PATH and return as JSON {"deals": [...]}
    - If CSV missing or unreadable, falls back to MongoDB collection "flight_coupons"
    - Ensures returned JSON keys match EXPECTED_COLUMNS used throughout the project
    """
    EXPECTED_COLUMNS = [
        "platform", "title", "offer", "coupon_code", "bank",
        "payment_mode", "emi", "url", "expiry_date",
        "current/upcoming", "flight_type"
    ]

    # 1) Try CSV first
    try:
        if os.path.exists(CSV_FILE_PATH):
            deals = []
            with open(CSV_FILE_PATH, newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    # normalize to expected columns: if missing columns exist, insert empty string
                    normalized = {
                        k: (row.get(k, "") if row.get(k, None) is not None else "")
                        for k in EXPECTED_COLUMNS
                    }
                    deals.append(normalized)
            return JSONResponse(content={"deals": deals})
    except Exception as e:
        # Log but continue to fallback to MongoDB
        print(f"[get_latest_deals] Error reading CSV ({CSV_FILE_PATH}): {e}")

    # 2) Fallback to MongoDB
    try:
        client = mongoDB.connect_db()
        coll = mongoDB.get_collection(client, "flight_coupons")
        if coll is None:
            return JSONResponse(
                content={"deals": [], "error": "No data source available"},
                status_code=500
            )

        docs = list(coll.find({}, {"_id": 0, "embedding": 0}))
        # Ensure keys match EXPECTED_COLUMNS: convert keys if necessary or fill missing
        normalized_docs = []
        for d in docs:
            normalized = {}
            for k in EXPECTED_COLUMNS:
                normalized[k] = d.get(k, "")
            normalized_docs.append(normalized)

        return JSONResponse(content={"deals": normalized_docs})
    except Exception as e:
        print(f"[get_latest_deals] Mongo fallback error: {e}")
        return JSONResponse(
            content={"deals": [], "error": str(e)},
            status_code=500
        )                  
                  
#ooriginal functional main.py
# from typing import List
# from fastapi import FastAPI
# from pydantic import BaseModel
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import JSONResponse
# import os
# import csv
# from io import StringIO
# from dotenv import load_dotenv
# from utils import model_with_tool, mongoDB

# load_dotenv()

# app = FastAPI()

# origins = [
#     "*",
# ]

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=origins,
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Request body model
# class ChatRequest(BaseModel):
#     chat_history: List[dict]  # [{"role": "human", "content": "..."}, {"role": "system", "content": "..."}]

# CSV_FILE_PATH = os.getenv("UPDATED_DEALS_CSV", r"C:\Users\newbr\OneDrive\Desktop\mongo_dataentry\updated_deals.csv")

# @app.get("/")
# def home():
#     return {"message": "its working fine :)"}

# @app.post("/chat")
# def chat_endpoint(request: ChatRequest):
#     """
#     Existing chat endpoint that uses model_with_tool.rag_agent
#     """
#     result = model_with_tool.rag_agent(request.chat_history)
#     return result

# @app.get("/get_latest_deals")
# def get_latest_deals():
#     """
#     Primary endpoint for the frontend Book Now flow.
#     - Tries to read CSV_FILE_PATH and return as JSON {"deals": [...]}
#     - If CSV missing or unreadable, falls back to MongoDB collection "flight_coupons"
#     - Ensures returned JSON keys match EXPECTED_COLUMNS used throughout the project
#     """
#     EXPECTED_COLUMNS = [
#         "platform", "title", "offer", "coupon_code", "bank",
#         "payment_mode", "emi", "url", "expiry_date",
#         "current/upcoming", "flight_type"
#     ]

#     # 1) Try CSV first
#     try:
#         if os.path.exists(CSV_FILE_PATH):
#             deals = []
#             with open(CSV_FILE_PATH, newline="", encoding="utf-8") as csvfile:
#                 reader = csv.DictReader(csvfile)
#                 for row in reader:
#                     # normalize to expected columns: if missing columns exist, insert empty string
#                     normalized = {k: (row.get(k, "") if row.get(k, None) is not None else "") for k in EXPECTED_COLUMNS}
#                     deals.append(normalized)
#             return JSONResponse(content={"deals": deals})
#     except Exception as e:
#         # Log but continue to fallback to MongoDB
#         print(f"[get_latest_deals] Error reading CSV ({CSV_FILE_PATH}): {e}")

#     # 2) Fallback to MongoDB
#     try:
#         client = mongoDB.connect_db()
#         coll = mongoDB.get_collection(client, "flight_coupons")
#         if coll is None:
#             return JSONResponse(content={"deals": [], "error": "No data source available"}, status_code=500)

#         docs = list(coll.find({}, {"_id": 0, "embedding": 0}))
#         # Ensure keys match EXPECTED_COLUMNS: convert keys if necessary or fill missing
#         normalized_docs = []
#         for d in docs:
#             normalized = {}
#             for k in EXPECTED_COLUMNS:
#                 normalized[k] = d.get(k, "")
#             normalized_docs.append(normalized)

#         return JSONResponse(content={"deals": normalized_docs})
#     except Exception as e:
#         print(f"[get_latest_deals] Mongo fallback error: {e}")
#         return JSONResponse(content={"deals": [], "error": str(e)}, status_code=500)