import os
from pymongo import MongoClient

# connect to MongoDB running in Docker on localhost:27017
client = MongoClient(os.getenv("MONGODB_URI", "mongodb://localhost:27017/"))

# database and collection handles
db = client["ai_stylist"]
# only one collection for user's liked outfits
liked_outfits = db["liked_outfits"]


"""
Verify the connection works. Called on startup.
Raises if MongoDB is unreachable so you find out immediately.
"""
def verify_connection():
    client.admin.command("ping")
    print("MongoDB connected.")