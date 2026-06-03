from dotenv import load_dotenv
load_dotenv()   # load environment variables from .env file

from fastapi import FastAPI
from api.routes import router

# create FastAPI app and include the router
app = FastAPI()
# Cross-Origin Resource Sharing (CORS) settings

from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # allow Vite frontend origin
    allow_methods=["*"],  # allow all HTTP methods
    allow_headers=["*"],  # allow all headers
)

app.include_router(router, prefix="/api")



# check if the app is running
@app.get("/")
def backend_check():
    return {"message": "Backend is running!"}