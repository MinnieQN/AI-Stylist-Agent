from dotenv import load_dotenv
load_dotenv()   # load environment variables from .env file

from fastapi import FastAPI
from api.routes import router
from services.qdrant import ensure_collections
from services.mongo import verify_connection

# create FastAPI app 
app = FastAPI()
# Cross-Origin Resource Sharing (CORS) settings

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # allow Vite frontend origin
    allow_methods=["*"],  # allow all HTTP methods
    allow_headers=["*"],  # allow all headers
)

# include the router
app.include_router(router, prefix="/api")

# check if the app is running
@app.get("/")
def backend_check():
    return {"message": "Backend is running!"}

# verify qdrant and mongoDB connection
@app.on_event("startup")
def startup():
    ensure_collections()
    verify_connection()