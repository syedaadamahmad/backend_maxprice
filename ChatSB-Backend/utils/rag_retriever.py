#rag_retriever.py
import os
from utils import mongoDB
from dotenv import load_dotenv
from langchain_core.tools import tool
from langchain_aws import BedrockEmbeddings
from langchain.chat_models import init_chat_model
from langchain_mongodb import MongoDBAtlasVectorSearch

load_dotenv()
# Setup
embeddings = BedrockEmbeddings(
                model_id= os.getenv("EMBEDDING_MODEL_ID"),
                region_name= os.getenv("AWS_DEFAULT_REGION"),
                aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
                aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            )

mongo_client = mongoDB.connect_db()
collection = mongoDB.get_collection(mongo_client, "flight_coupons")


vector_store = MongoDBAtlasVectorSearch(
    embedding=embeddings,
    collection=collection,
    index_name="vector_index",
)

retriever = vector_store.as_retriever(
    search_type="similarity_score_threshold",
    search_kwargs={"k": 10, "score_threshold": 0.75,},
)

@tool
def rag_tool(query: str):
    """
    this tool is used to return the offers on flights.
    """
    docs = retriever.invoke(query)
    context = "\n".join(d.page_content for d in docs)

    llm = init_chat_model("gemini-2.5-flash", model_provider="google_genai")
    prompt = f"""
        You are a helpful assistant.  

        You will receive:  
        - A user's query.  
        - A set of available offers.  

        Your task:  
        - Read the offers carefully and check if they match the user's query.  
        - If you find relevant information, respond politely and naturally by providing the matching offers.  
        - If no relevant information is found, simply say that you couldn't find any offers or discounts for the query.  
        - Never mention "documents," "context," or "list of offers."  
        - Always keep your response clear, concise, and human-friendly.  
        
        **FORMATTING REQUIREMENTS:**
        - Include offer details like discount percentages, cashback amounts in bold
        - Include numbering for each offer
        - Use this format for each offer and examples:
          1. **[Discount/Cashback Details]**
          2. **[Next offer with all details in bold]**
        - For example:
            1. **Get FLAT ₹400 OFF on domestic flights when your transaction is above ₹7,500.**
            2. **Get FLAT ₹500 OFF on domestic flights when your transaction is above ₹10,000.**
            3. **Get FLAT ₹600 OFF on domestic flights when your transaction is above ₹12,500.**
            4. **Get FLAT ₹700 OFF on international flights when your transaction is above ₹15,000.**
        - Keep the entire offer content within the bold formatting
        - Additional terms/conditions can be mentioned in regular text after the bold offer if needed
        User query: {query}  

        Available offers:  
        {context}  

        Answer:
        """


    resp = llm.invoke(prompt)
    return resp.content