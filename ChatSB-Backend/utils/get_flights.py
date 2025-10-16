# get_flights.py
# this code runs max price
# get_flights.py
import os
import re
from dotenv import load_dotenv
from serpapi import GoogleSearch
from langchain_core.tools import tool

load_dotenv()

def normalize_price(value):
    """
    Normalize a price string into digits only.
    Examples:
      "Rs19000" -> "19000"
      "₹ 19,000" -> "19000"
      "19000" -> "19000"
    Returns None if no valid digits found.
    """
    if not value:
        return None
    cleaned = re.sub(r"[^\d]", "", str(value))
    return cleaned if cleaned.isdigit() else None


def is_flight_under_budget(flight, max_price):
    """
    Quick check if a flight is under budget before making expensive booking API calls.
    Returns True if flight is under budget or if price cannot be determined.
    """
    if not max_price:
        return True  # No budget limit
    
    cleaned_max_price = normalize_price(max_price)
    if not cleaned_max_price:
        return True  # Invalid max_price, show all flights
    
    # Extract price from flight data
    price_amount = None
    price_obj = flight.get("price", {})
    if isinstance(price_obj, dict):
        price_amount = price_obj.get("amount")
    
    if price_amount is None:
        price_amount = flight.get("price_amount")
    
    if price_amount:
        try:
            price_int = int(str(price_amount).replace(",", ""))
            is_under = price_int <= int(cleaned_max_price)
            print(f"💰 [DEBUG] Flight price {price_int} {'≤' if is_under else '>'} max {cleaned_max_price}")
            return is_under
        except (ValueError, TypeError):
            print(f"⚠️ [DEBUG] Could not parse price: {price_amount}, including flight")
            return True  # Include flights with unparseable prices
    
    print(f"⚠️ [DEBUG] No price found for flight, including anyway")
    return True  # Include flights without price info


def get_flights(departure_id, arrival_id, departure_date, max_price=None):
    """
    Call SerpAPI Google Flights engine to fetch flights.
    Uses SerpAPI's max_price filter to reduce API calls.
    """
    params = {
        "api_key": os.getenv("SERPAPI_API_KEY"),
        "engine": os.getenv("SEARCH_ENGINE"),
        "hl": os.getenv("LANGUAGE"),
        "gl": os.getenv("COUNTRY"),
        "currency": os.getenv("CURRENCY"),
        "no_cache": True,
        "type": os.getenv("FLIGHT_TYPE"),
        "departure_id": departure_id,
        "arrival_id": arrival_id,
        "outbound_date": departure_date,
    }

    # Use SerpAPI's max_price filter to reduce API calls
    if max_price:
        cleaned = normalize_price(max_price)
        if cleaned:
            params["max_price"] = cleaned
            print(f"🔎 [DEBUG] Using SerpAPI max_price filter: {cleaned}")

    print("🔎 [DEBUG] Params sent to SerpAPI:", params)

    search = GoogleSearch(params)
    results = search.get_dict()

    best_flights = results.get("best_flights", [])
    other_flights = results.get("other_flights", [])
    all_flights = best_flights + other_flights
    
    print(f"🔎 [DEBUG] SerpAPI returned {len(all_flights)} flights")
    return all_flights


def fetch_booking_options(booking_token, departure_date, departure_id, arrival_id):
    """
    Fetch booking options for a given booking_token.
    """
    try:
        params = {
            "api_key": os.getenv("SERPAPI_API_KEY"),
            "engine": os.getenv("SEARCH_ENGINE"),
            "hl": os.getenv("LANGUAGE"),
            "gl": os.getenv("COUNTRY"),
            "currency": os.getenv("CURRENCY"),
            "type": os.getenv("FLIGHT_TYPE"),
            "no_cache": True,
            "departure_id": departure_id,
            "arrival_id": arrival_id,
            "outbound_date": departure_date,
            "booking_token": booking_token,
            "show_hidden": "true",
            "deep_search": "true",
        }

        print("🔎 [DEBUG] Fetching booking options with:", params)

        search = GoogleSearch(params)
        results = search.get_dict()
        return results
    except Exception as e:
        print(f"❌ Error fetching booking options for token {booking_token}: {e}")
        return None


@tool
def get_flight_with_aggregator(
    departure_id: str,
    arrival_id: str,
    departure_date: str,
    max_price: str = None
):
    """
    Get flight information with aggregated booking options.
    Uses SerpAPI max_price filter + client-side budget check to minimize API calls.
    Returns a Python list of dicts (not a JSON string).
    
    Args:
        max_price: Can be a number string (e.g., "15000"), None, or "no preference"
    """
    print("🚀 [INFO] Running get_flight_with_aggregator")
    print("   Departure:", departure_id)
    print("   Arrival:", arrival_id)
    print("   Date:", departure_date)
    print("   Max Price:", max_price)

    # Handle "no preference" cases
    processed_max_price = None
    if max_price:
        max_price_lower = str(max_price).lower().strip()
        if any(phrase in max_price_lower for phrase in ["no preference", "no budget", "any price", "unlimited", "no limit"]):
            processed_max_price = None
            print("🔓 [INFO] No price limit - showing all flights")
        else:
            processed_max_price = max_price
            print(f"💰 [INFO] Price limit set to: {processed_max_price}")

    # Stage 1: Get flights with SerpAPI max_price filter (reduces initial results)
    all_flights = get_flights(departure_id, arrival_id, departure_date, max_price=processed_max_price)
    
    # Stage 2: Filter flights before making expensive booking API calls
    budget_filtered_flights = []
    for flight in all_flights:
        if is_flight_under_budget(flight, processed_max_price):
            budget_filtered_flights.append(flight)
    
    print(f"🔎 [DEBUG] Filtered {len(all_flights)} flights to {len(budget_filtered_flights)} under budget")
    
    # Stage 3: Only make booking API calls for flights under budget
    enhanced_flights = []
    api_calls_made = 0
    
    for flight in budget_filtered_flights:
        token = flight.get("booking_token")
        if token:
            api_calls_made += 1
            print(f"📞 [DEBUG] Making booking API call #{api_calls_made} for token: {token[:10]}...")
            
            booking_options = fetch_booking_options(token, departure_date, departure_id, arrival_id)
            if not booking_options:
                continue

            selected = booking_options.get("selected_flights", [])
            booking_opts = booking_options.get("booking_options", [])

            flight_obj = []
            if selected and isinstance(selected, list):
                first = selected[0]
                if isinstance(first, dict) and first.get("flights"):
                    flight_obj = first.get("flights")

            enhanced_flights.append({
                "flight_data": flight_obj,
                "booking_options": booking_opts,
            })

    print(f"✅ [INFO] Made {api_calls_made} booking API calls (reduced from {len(all_flights)} potential calls)")
    return enhanced_flights




#this getflights returns flight details from serpapi but is empty array
# import os
# import json
# import re
# import datetime
# from dotenv import load_dotenv
# from serpapi import GoogleSearch
# from langchain_core.tools import tool

# load_dotenv()


# def get_flights(departure_id, arrival_id, departure_date, max_price: int = None, outbound_times: str = None, include_airlines: str = None):
#     """
#     Fetches flights from SerpAPI with optional parameters like outbound_times, max_price, and include_airlines.
#     If no include_airlines are specified or found, shows all flights.
#     """
#     params = {
#         "api_key": os.getenv("SERPAPI_API_KEY"),
#         "engine": os.getenv("SEARCH_ENGINE"),
#         "hl": os.getenv("LANGUAGE"),
#         "gl": os.getenv("COUNTRY"),
#         "currency": os.getenv("CURRENCY"),
#         "no_cache": True,
#         "type": os.getenv("FLIGHT_TYPE"),
#         "departure_id": departure_id,
#         "arrival_id": arrival_id,
#         "outbound_date": departure_date,
#         "include_airlines": "air india",
#         "max_price": "15208",
#         "outbound_times": "6",
#     }

#     if outbound_times:
#         params["outbound_times"] = outbound_times

#     if include_airlines:
#         # Map common airline names and alliances to SerpAPI codes
#         airline_map = {
#             "air india": "AI",
#             "indigo": "6E",
#             "spicejet": "SG",
#             "goair": "G8",
#             "vistara": "UK",
#             "air asia": "I5",
#         }
#         codes = []
#         for airline in include_airlines.split(","):
#             airline = airline.strip().lower()
#             if airline in airline_map:
#                 codes.append(airline_map[airline])
#         if codes:
#             params["airlines"] = ",".join(codes)

#     search = GoogleSearch(params)
#     results = search.get_dict()

#     best_flights = results.get("best_flights", [])
#     other_flights = results.get("other_flights", [])
#     all_flights = best_flights + other_flights

#     # Safety filter for max_price
#     if max_price:
#         filtered_flights = []
#         for flight in all_flights:
#             if not isinstance(flight, dict):
#                 continue
#             price = flight.get("price", {}).get("amount", 0)
#             if price <= max_price:
#                 filtered_flights.append(flight)
#         return filtered_flights

#     return all_flights


# def fetch_booking_options(booking_token, departure_date, departure_id, arrival_id):
#     """
#     Fetches detailed booking options for a flight given its booking token.
#     """
#     try:
#         params = {
#             "api_key": os.getenv("SERPAPI_API_KEY"),
#             "engine": os.getenv("SEARCH_ENGINE"),
#             "hl": os.getenv("LANGUAGE"),
#             "gl": os.getenv("COUNTRY"),
#             "currency": os.getenv("CURRENCY"),
#             "type": os.getenv("FLIGHT_TYPE"),
#             "no_cache": True,
#             "departure_id": departure_id,
#             "arrival_id": arrival_id,
#             "outbound_date": departure_date,
#             "booking_token": booking_token,
#             "show_hidden": "true",
#             "deep_search": "true",
#         }

#         search = GoogleSearch(params)
#         results = search.get_dict()
#         return results
#     except Exception as e:
#         print(f"Error fetching booking options for token {booking_token}: {e}")
#         return None


# @tool
# def get_flight_with_aggregator(
#     departure_id: str,
#     arrival_id: str,
#     departure_date: str,
#     max_price: int = None,
#     departure_time: str = None,
#     include_airlines: str = None
# ) -> str:
#     """
#     Get flight information with aggregated booking options from multiple airlines.
#     Supports filtering by max price, preferred departure time, and included airlines.
#     Returns a JSON string with flight data.
#     """
#     # Default to current year if year not specified
#     today = datetime.date.today()
#     if len(departure_date.split("-")) == 2:  # e.g., "10-21"
#         departure_date = f"{today.year}-{departure_date}"

#     # Map named periods to SerpAPI outbound_times
#     outbound_map = {
#         "morning": "4,11",
#         "afternoon": "12,17",
#         "evening": "18,21",
#         "night": "22,3",
#     }

#     outbound_times = None
#     if departure_time:
#         lower = departure_time.lower().strip()
#         if lower in outbound_map:
#             outbound_times = outbound_map[lower]
#         else:
#             match = re.search(r"(\d{1,2})(?::\d{2})?\s*(am|pm)?", lower)
#             if match:
#                 hour = int(match.group(1))
#                 meridiem = match.group(2)
#                 if meridiem == "pm" and hour != 12:
#                     hour += 12
#                 if meridiem == "am" and hour == 12:
#                     hour = 0
#                 start = max(hour - 1, 0)
#                 end = min(hour + 1, 23)
#                 outbound_times = f"{start},{end}"

#     # Fetch flights
#     all_flights = get_flights(
#         departure_id,
#         arrival_id,
#         departure_date,
#         max_price=max_price,
#         outbound_times=outbound_times,
#         include_airlines=include_airlines
#     )

#     # Filter by price
#     filtered_flights = []
#     for flight in all_flights:
#         price = flight.get("price", {}).get("amount", 0) if isinstance(flight, dict) else 0
#         if max_price and price > max_price:
#             continue
#         filtered_flights.append(flight)

#     # Aggregate booking options
#     enhanced_flights = []
#     for flight in filtered_flights:
#         booking_token = flight.get("booking_token")
#         if not booking_token:
#             continue
#         booking_options = fetch_booking_options(booking_token, departure_date, departure_id, arrival_id)
#         if not booking_options:
#             continue
#         selected = booking_options.get("selected_flights", [])
#         booking_opts = booking_options.get("booking_options", [])
#         flight_obj = selected[0].get("flights") if selected and isinstance(selected, list) and selected[0].get("flights") else []
#         enhanced_flights.append({
#             "flight_data": flight_obj,
#             "booking_options": booking_opts,
#         })

#     return json.dumps(enhanced_flights[:10], indent=2)