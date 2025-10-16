import requests

response = requests.post("http://localhost:8000/chat", json={
    "chat_history": [
        {
            "role": "human",
            "content": "helloo can i get all the bonus deals details for hdfc bank using credit card for all flights after 8th august to 12th december domestic and across india on makemytrip platform."
        }
    ]
})

print("Status Code:", response.status_code)
print(response.json()["answer"])
# print("Response JSON:", response.json())  # See what keys are actually returned

# import requests

# response = requests.post("http://localhost:8000/chat", json={
#     "chat_history": [
#         {
#             "role": "human",
#             "content": "helloo"
#         }
#     ]
# })

# print(response.json()["answer"])




# csv -> reads coupons cocde-> json-> front-end.

# discount get-> flight no arrival deparrture,

# op/ (eg make my trip logo) discount logo, kitna discount hai, aur coupon code kya hai.