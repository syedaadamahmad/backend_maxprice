#model_with_tool.py
# max filter
# model_with_tool.py
import re
from typing import List
from dotenv import load_dotenv
from utils import rag_retriever, get_flights
from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

load_dotenv()

model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

model_with_tool = model.bind_tools([
    rag_retriever.rag_tool,
    get_flights.get_flight_with_aggregator
])

system_prompt = """
<persona>
  You are TripSaver, a friendly flight assistant.  
  Your job is to help users find flight options and offers.
</persona>

For flight searches, required parameters:
- departure_id (e.g., DEL)
- arrival_id (e.g., BOM)
- departure_date (YYYY-MM-DD)

You must ALWAYS ask the user for their maximum price before calling the tool.
- If the user provides a number (e.g., "19000" or "Rs 19000"), normalize it to digits only.
- If the user says "any price", "no budget", "no preference", "unlimited", or "no limit", set max_price=None.
- Do not call the tool until max_price is clarified (either a number or explicit "no preference").
"""

def rag_agent(chat_history: List[dict]):
    messages = [SystemMessage(system_prompt)]
    for msg in chat_history:
        if msg["role"] == "human":
            messages.append(HumanMessage(msg["content"]))
        elif msg["role"] == "ai":
            messages.append(AIMessage(msg["content"]))

    ai_msg = model_with_tool.invoke(messages)
    ai_msg_content = ""
    flight_data = None

    if ai_msg.tool_calls:
        for call in ai_msg.tool_calls:
            if call["name"] == "rag_tool":
                tool_msg = rag_retriever.rag_tool.invoke(call)
                ai_msg_content += tool_msg.content

            elif call["name"] == "get_flight_with_aggregator":
                try:
                    params = call.get("args", {}) or {}

                    # ✅ Enforce max_price requirement
                    if "max_price" not in params or params["max_price"] in ("", None):
                        ai_msg_content += "Sure, I can help you with that! What is your maximum price?"
                        continue  # Don't call the tool yet

                    # Normalize Rs/₹ input and handle "no preference" cases
                    raw_price = str(params["max_price"]).lower().strip()
                    if any(phrase in raw_price for phrase in ["any", "no budget", "no preference", "unlimited", "no limit"]):
                        params["max_price"] = None
                        print("🔓 [INFO] User specified no price limit")
                    else:
                        cleaned = re.sub(r"[^\d]", "", raw_price)
                        params["max_price"] = cleaned if cleaned else None
                        if params["max_price"]:
                            print(f"💰 [INFO] User specified max price: {params['max_price']}")

                    # Call the tool (returns Python list/dict now)
                    flight_data = get_flights.get_flight_with_aggregator.invoke({
                        "departure_id": params["departure_id"],
                        "arrival_id": params["arrival_id"],
                        "departure_date": params["departure_date"],
                        "max_price": params.get("max_price")
                    })

                    if flight_data and len(flight_data) > 0:
                        if params["max_price"]:
                            ai_msg_content += f"Found {len(flight_data)} flight options under your budget ✈️"
                        else:
                            ai_msg_content += f"Found {len(flight_data)} flight options ✈️"
                    else:
                        ai_msg_content += "No flights found for that search 😕"

                except Exception as e:
                    print(f"Flight search error: {e}")
                    ai_msg_content += "Error occurred while fetching flights."
    else:
        ai_msg_content += ai_msg.content

    return {"content": ai_msg_content, "flight_data": flight_data}




#this model with tool has filters as well
# import json
# from typing import List
# from dotenv import load_dotenv
# from utils import rag_retriever
# from utils import get_flights
# from langchain.chat_models import init_chat_model
# from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
# from datetime import datetime

# load_dotenv()

# model = init_chat_model("gemini-2.5-flash", model_provider="google_genai")

# model_with_tool = model.bind_tools([rag_retriever.rag_tool, get_flights.get_flight_with_aggregator])

# # system_prompt = "You are a Flight Coupon Assistant, designed to help users find the best offers, discounts, and deals on flight bookings."
# system_prompt = """
# <persona>
#   You are TripSaver, a friendly flight assistant.  
#   Your role is to help users with two main tasks:
#   1. Find the best flight offers, discounts, and coupons
#   2. Search for actual flight options and prices
#   You can use two tools:
# 1. `rag_tool` → Retrieve textual knowledge and credit card offers from MongoDB Atlas.
# 2. `get_flight_with_aggregator` → Fetch live flight data from SerpAPI.
#   Always respond warmly and naturally, never robotic or overly AI-like.  
#   Keep the conversation flowing, ask clarifying questions when needed, and only call tools when you have enough details.
# </persona>

# ---

# ### 1. Soft tone
# - Respond in a warm, conversational, human style.  
# - Use emojis sparingly to keep things light and friendly.  
# - Avoid robotic or overly formal phrasing.  
# **Example Conversation:**  
# - **User:** "Hello"  
# - **Assistant:** "Hey there 👋 Looking for flight deals or want to search for flights today?"  

# - **User:** "Do you have any HDFC offers?"  
# - **Assistant:** "Hmm, looks like I couldn't find offers for that right now 😕. But we can try another bank or platform if you'd like!"  

# - **User:** "Show me flights from Delhi to Mumbai"  
# - **Assistant:** "I'd love to help you find flights! ✈️ What date are you planning to travel?"  

# ---

# ### 2. Query Types and Handling

# #### A. COUPON/OFFERS QUERIES
# - Required details before **rag_tool** call:  
#   - **Platform** (MakeMyTrip, Goibibo, EaseMyTrip, etc.)  
#   - **Bank name** (HDFC, ICICI, SBI, etc.)
#   - **Card type** (credit or debit)  
#   - **Flight type** (domestic or international)  

# **Example Conversation:**  
# - **User:** "I want HDFC offers."  
# - **Assistant:** "Got it 😊 Do you want me to check for credit card or debit card offers?"  
# - **User:** "Credit card."  
# - **Assistant:** "Nice! And which platform are you planning to book on — MakeMyTrip, Goibibo, or something else?"  

# #### B. FLIGHT SEARCH QUERIES
#   Before calling `get_flight_with_aggregator`, ensure you collect and normalize:
# - **Departure airport or city** (city name or airport code like DEL, BOM, etc.)
# - **Arrival airport or city** (city name or airport code like MAA, BLR, etc.)
# - **Departure date** (YYYY-MM-DD format or natural date)
# - **Preferred maximum price (max_price)** → numeric only, in INR.  
#   Users may say:
#   - “under 5000”, “below 7000”, “less than 10000”, “up to 12000”, "Rs9000" → extract number (e.g., 10000)
#   - “no limit”, “any price”, “no budget” → treat as None (unlimited)
# - **Preferred departure time (departure_time)** mapped to SerpAPI’s `outbound_times`:
#   - "morning" → "4am,11am"
#   - "afternoon" → "12pm,17pm"
#   - "evening" → "18pm,21pm"
#   - "night" → "22pm,3am"
#   - Explicit times like “3:30 AM” → automatically converted to a ±1 hour window.
#   - “any time” or “no preference” → None (unrestricted)
#   -**Include airlines (include_airlines)** → comma-separated 2-character IATA codes (e.g., "air india, vistara, indigo, air india express, spicejet, akasa air, alliance air, flybig, indiaone air, star air, fly91, airasia,go air, AI,6E,SG,IX,QP,UK,9I,I7,IC,I5,S5,S9" etc the user might mispell or use full names so convert airlines names to codes)

# If any required field is missing, ask for it explicitly before calling the tool.
# - Required details before **get_flight_with_aggregator** call:  
#   - **Departure airport** (city name or airport code like DEL, BOM, etc.)
#   - **Arrival airport** (city name or airport code like MAA, BLR, etc.)  
#   - **Departure date** (in YYYY-MM-DD format or natural date)
#   - **Departure date** (YYYY-MM-DD format or natural date)
#   - **Preferred maximum price (max_price)** → numeric only, in INR.  
#   - **Preferred departure time (departure_time)** mapped to SerpAPI’s `outbound_times`
#   - **Include airlines (include_airlines)** → comma-separated 2-character IATA codes (include only include_airlines in the rest or show all airlines if the user says "no preference" or "any airline" or "no airline preference" etc)
  
# **Example Conversation:**  
# - **User:** "Find flights from Delhi to Chennai"  
# - **Assistant:** "Great! ✈️ What date are you planning to travel?"
#   After getting the date of travel do not ask for what year and assume current year if not specified.
# - **User:** "Tomorrow"  
# - **Assistant:** "What’s your maximum budget in INR?” and “What time of day would you prefer to depart?”
# - **User:** "9000, afternoon works."
# - **Assistant:** "Any airlines you prefer?"
# - **User:** "Air India."
#   Include only include_airlines in the rest or show all airlines if the user says "no preference" or "any airline" or "no airline preference" etc
#   After getting all fields, call `get_flight_with_aggregator`.
# - **Assistant:** "Perfect! Let me search for flights from Delhi to Chennai for [date] under [max_price]..."  

# **Airport Code Mapping (use these codes for tool calls):**
#  - Agartala: IXA​
#  - Allahabad: IXD​
#  - Aurangabad: IXU​
#  - Bagdogra: IXB​
#  - Bareilly: BEK​
#  - Belgaum: IXG​
#  - Bellary: BEP​
#  - Bengaluru: BLR​
#  - Bhavnagar: BHU​
#  - Bhopal: BHO​
#  - Bhubaneswar: BBI​
#  - Bhuj: BHJ​
#  - Bhuntar: KUU​
#  - Bikaner: BKB​
#  - Chandigarh: IXC​
#  - Chennai: MAA​
#  - Cochin: COK​
#  - Coimbatore: CJB​
#  - Dehra Dun: DED​
#  - Delhi: DEL​
#  - Dhanbad: DBD​
#  - Dharamshala: DHM​
#  - Dibrugarh: DIB​
#  - Dimapur: DMU​
#  - Gaya: GAY​
#  - Goa (Dabolim): GOI​
#  - Gorakhpur: GOP​
#  - Guwahati: GAU​
#  - Gwalior: GWL​
#  - Hubli: HBX​
#  - Hyderabad: HYD​
#  - Imphal: IMF​
#  - Indore: IDR​
#  - Jabalpur: JLR​
#  - Jaipur: JAI​
#  - Jaisalmer: JSA​
#  - Jammu: IXJ​
#  - Jamnagar: JGA​
#  - Jamshedpur: IXW​
#  - Jodhpur: JDH​
#  - Jorhat: JRH​
#  - Kanpur: KNU​
#  - Keshod: IXK​
#  - Khajuraho: HJR​
#  - Kolkata: CCU​
#  - Kota: KTU​
#  - Kozhikode: CCJ​
#  - Leh: IXL​
#  - Lilabari: IXI​
#  - Lucknow: LKO​
#  - Madurai: IXM​
#  - Mangalore: IXE​
#  - Mumbai: BOM​
#  - Muzaffarpur: MZU​
#  - Mysore: MYQ​
#  - Nagpur: NAG​
#  - Pant Nagar: PGH​
#  - Pathankot: IXP​
#  - Patna: PAT​
#  - Port Blair: IXZ​
#  - Pune: PNQ​
#  - Puttaparthi: PUT​
#  - Raipur: RPR​
#  - Rajahmundry: RJA​
#  - Rajkot: RAJ​
#  - Ranchi: IXR​
#  - Shillong: SHL​
#  - Sholapur: SSE​
#  - Silchar: IXS​
#  - Shimla: SLV​
#  - Srinagar: SXR​
#  - Surat: STV​
#  - Tezpur: TEZ​
#  - Thiruvananthapuram: TRV​
#  - Tiruchirappalli: TRZ​
#  - Tirupati: TIR​
#  - Udaipur: UDR​
#  - Vadodara: BDQ​
#  - Varanasi: VNS​
#  - Vijayawada: VGA​
#  - Visakhapatnam: VTZ​
#  - Tuticorin: TCR
 
# **Airlines Code Mapping (use these codes for tool calls):**
#  - Air India: AI
#  - IndiGo: 6E
#  - SpiceJet: SG
#  - Air India Express: AIX
#  - Akasa Air: QP
#  - Vistara: UK
#  - Alliance Air: 9I
#  - FlyBig: S9
#  - IndiaOne Air: I7
#  - Star Air: S5
#  - Fly91: IC
#  - AirAsia: I5
#  - GoAir: G8

# ---

# ### 3. Follow-up Questions
# - Always ask clarifying questions naturally, never as a checklist.  
# - Only one question at a time.  
# - For flight searches, convert city names to airport codes automatically when possible.

# ---

# ### 4. Tool Call Policies

# #### A. **rag_tool** (for offers/coupons)
# - Never call for small talk like "hi", "hello", "ok", "how are you"
# - Only call when:  
#   - All required details (**Platform**, **Bank name**, **card type**, **Flight type**) are available
#   - User query is about offers, discounts, or coupons — not casual chit-chat
#   - Reformulate into rich semantic query before calling

# #### B. **get_flight_with_aggregator** (for flight search)
# - Never call for small talk or coupon queries
# - Only call when:
#   - User asks for flight search, flight prices, or flight options
#   - All required details (**departure airport code**, **arrival airport code**, **departure date**) are available
#   - Convert city names to airport codes before calling
#   - Convert natural dates to YYYY-MM-DD format

# **Example Tool Calls:**
# - Query: "Flights from Delhi to Mumbai on 2025-10-01"
# - Call: get_flight_with_aggregator("DEL", "BOM", "2025-10-01")

# ---

# ### 5. Date Handling
# - Accept natural language dates: "tomorrow", "next Monday", "Oct 15", etc.
# - Convert to YYYY-MM-DD format for tool calls
# - If date is ambiguous, ask for clarification
# - Current date context: September 30, 2025

# ---

# ### 6. If No Results Found
# - **For offers:** Suggest alternative platforms, banks, or card types
# - **For flights:** Suggest nearby dates or alternative airports

# ---

# ### 7. Output Rules
# 1. **For coupon queries:** If all details available → call **rag_tool**
# 2. **For flight queries:** If all details available → call **get_flight_with_aggregator**  
# 3. If clarification needed → ask the next follow-up question
# 4. If no results → suggest alternatives
# 5. Always keep tone soft, natural, and human
# 6. **Never call both tools in the same response**
# """
# def rag_agent(chat_history: list):
#     """
#     Handles user chat and calls appropriate tools:
#     - rag_tool for offers/coupons
#     - get_flight_with_aggregator for flight searches
#     Returns JSON: {"content": str, "flight_data": list | None}
#     """
#     messages = [SystemMessage(system_prompt)]
#     for msg in chat_history:
#         if msg["role"] == "human":
#             messages.append(HumanMessage(msg["content"]))
#         elif msg["role"] == "ai":
#             messages.append(AIMessage(msg["content"]))

#     ai_msg = model_with_tool.invoke(messages)
#     ai_msg_content = ""
#     flight_data = None

#     if getattr(ai_msg, "tool_calls", None):
#         for call in ai_msg.tool_calls:

#             # ----- RAG TOOL -----
#             if call["name"] == "rag_tool":
#                 # tool expects a single string query argument
#                 query = call["args"].get("query") if isinstance(call.get("args"), dict) else None
#                 if query is None:
#                     query = call["args"]
#                 tool_msg = rag_retriever.rag_tool.invoke(query)
#                 ai_msg_content += tool_msg.content

#             # ----- FLIGHT SEARCH TOOL -----
#             elif call["name"] == "get_flight_with_aggregator":
#                 try:
#                     params = call.get("args", {}) or {}
#                     # Normalize departure_date if a short form was provided (e.g., "10-21" or "21-10")
#                     dep_date = params.get("departure_date")
#                     if dep_date and len(dep_date.split("-")) == 2:
#                         dep_date = f"{datetime.now().year}-{dep_date}"
#                         params["departure_date"] = dep_date

#                     # Call get_flight_with_aggregator tool - pass dict (tool handles sanitization)
#                     flight_json = get_flights.get_flight_with_aggregator.invoke(params)
#                     flight_data = json.loads(flight_json) if flight_json else None

#                     if flight_data and len(flight_data) > 0:
#                         ai_msg_content += f"Found {len(flight_data)} flight options! ✈️ Here are the available flights with prices from multiple platforms."
#                     else:
#                         ai_msg_content += "Sorry, no flights were found for your search. 😕 Try different dates or nearby airports."

#                 except Exception as e:
#                     ai_msg_content += "Sorry, there was an error searching for flights. 😕"
#                     print(f"Flight search error: {e}")

#     else:
#         ai_msg_content += ai_msg.content

#     return {"content": ai_msg_content, "flight_data": flight_data}

#this rag agent works but returns an empty array for flights.
# def rag_agent(chat_history: list):
#     """
#     Handles user chat and calls appropriate tools:
#     - rag_tool for offers/coupons
#     - get_flight_with_aggregator for flight searches
#     Returns JSON: {"content": str, "flight_data": list | None}
#     """
#     messages = [SystemMessage(system_prompt)]
#     for msg in chat_history:
#         if msg["role"] == "human":
#             messages.append(HumanMessage(msg["content"]))
#         elif msg["role"] == "ai":
#             messages.append(AIMessage(msg["content"]))

#     # ai_msg = rag_retriever.model_with_tool.invoke(messages)
#     ai_msg = model_with_tool.invoke(messages)
#     ai_msg_content = ""
#     flight_data = None

#     if ai_msg.tool_calls:
#         for call in ai_msg.tool_calls:

#             # ----- RAG TOOL -----
#             if call["name"] == "rag_tool":
#                 tool_msg = rag_retriever.rag_tool.invoke(input=call["args"]["query"])
#                 ai_msg_content += tool_msg.content

#             # ----- FLIGHT SEARCH TOOL -----
#             elif call["name"] == "get_flight_with_aggregator":
#                 try:
#                     params = call.get("args", {})

#                     # Ensure departure_date has year
#                     dep_date = params.get("departure_date")
#                     if dep_date and len(dep_date.split("-")) == 2:  # e.g., "10-21"
#                         dep_date = f"{datetime.now().year}-{dep_date}"
#                     params["departure_date"] = dep_date

#                     # Call tool correctly with JSON string input
#                     flight_json = get_flights.get_flight_with_aggregator.invoke(params)
#                     flight_data = json.loads(flight_json) if flight_json else None

#                     if flight_data and len(flight_data) > 0:
#                         ai_msg_content += f"Found {len(flight_data)} flight options! ✈️ Here are the available flights with prices from multiple platforms."
#                     else:
#                         ai_msg_content += "Sorry, no flights were found for your search. 😕 Try different dates or nearby airports."

#                 except Exception as e:
#                     ai_msg_content += "Sorry, there was an error searching for flights. 😕"
#                     print(f"Flight search error: {e}")

#     else:
#         ai_msg_content += ai_msg.content

#     return {"content": ai_msg_content, "flight_data": flight_data}
  
  
  
#OLD RAG AGENT    
# def rag_agent(chat_history: List[dict]):
#   messages = []
#   messages.append(SystemMessage(system_prompt))
#   for msg in chat_history:
#     if msg["role"] == "human":
#       messages.append(HumanMessage(msg["content"]))
#     elif msg["role"] == "ai":
#       messages.append(AIMessage(msg["content"]))
  
#   ai_msg = model_with_tool.invoke(messages)
#   ai_msg_content = ""
#   flight_data = None
  
#   if ai_msg.tool_calls:
#     for call in ai_msg.tool_calls:
#       # Handle RAG tool for offers/coupons
#       if call["name"] == "rag_tool":
#         tool_msg = rag_retriever.rag_tool.invoke(call)
#         ai_msg_content += tool_msg.content
      
#       # Handle flight aggregator tool
#       elif call["name"] == "get_flight_with_aggregator":
#         try:
#           print(call)
#           flight_json = get_flights.get_flight_with_aggregator.invoke(call)
#           flight_data = json.loads(flight_json.content) if flight_json else None
#           print(flight_data)
          
#           # Generate a summary for flight results
#           if flight_data and len(flight_data) > 0:
#             num_flights = len(flight_data)
#             ai_msg_content += f"Found {num_flights} flight options for your search! ✈️ Here are the available flights with pricing details from multiple booking platforms."
#           else:
#             ai_msg_content += "Sorry, I couldn't find any flights for your search criteria. 😕 You might want to try different dates or nearby airports."
            
#         except Exception as e:
#           ai_msg_content += f"Sorry, I encountered an issue while searching for flights. Please try again later. 😕"
#           print(f"Flight search error: {e}")
#   else:
#     ai_msg_content += ai_msg.content
  
#   # Return response with flight data if available
#   response = {"content": ai_msg_content, "flight_data": flight_data}
  
#   # Return as JSON string
#   return response