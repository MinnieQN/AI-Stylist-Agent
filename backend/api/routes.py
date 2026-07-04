import uuid
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from agent.graph import graph
from services.gemini import generate_tryon_image
from services.mongo import liked_outfits
from services.cache import check_cache
from datetime import datetime
from services.embed import embed_texts
from qdrant_client.models import PointStruct
from services.qdrant import client, LIKED_OUTFITS

router = APIRouter()

# set up upload directory and allowed file types/sizes for image uploads
UPLOAD_DIR = Path(__file__).parent.parent / "uploads"
UPLOAD_DIR.mkdir(exist_ok=True)

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_SIZE_MB = 10

# Pydantic model for the request body
class StyleRequest(BaseModel):
    occasion: str
    style_preference: str | None = None
    skip_cache: bool = False

# handle POST request to generate 3 recommended styles for a given occasion
@router.post("/styles")
async def recommend_styles(request: StyleRequest):
    # handle empty occasion input
    if not request.occasion.strip():
        raise HTTPException(status_code=400, detail="Occasion cannot be empty.")

    user_id = os.getenv("DEFAULT_USER_ID", "local-user")

    # cache check — unless the user explicitly asked to skip it
    if not request.skip_cache:
        cached = check_cache(request.occasion, user_id)
        if cached:
            return {
                "occasion": request.occasion,
                "cached": True,
                "outfit": {
                    "style": cached["style"],
                    "tryon_image": cached["tryon_image"],
                },
            }
    # cache miss, continue to agent
    try:
        # invoke the LangGraph agent
        result = await graph.ainvoke({
            "occasion": request.occasion,
            "style_preference": request.style_preference,
            "user_id": user_id,
        })
        # clarification gate: agent judged the occasion unclear
        if not result.get("occasion_clear", False):
            return {
                "cached": False,
                "needs_clarification": True,
                "question": result.get(
                    "clarification_question",
                    "Could you tell me more about your occasion?"
                ),
            }

        return {
            "occasion": request.occasion,
            "cached": False,
            "recommendations": result["recommendations"],
        }
    except Exception as e:
        # handle errors from Gemini API or JSON parsing
        raise HTTPException(status_code=500, detail=f"Failed to generate styles: {str(e)}")

# handle POST request to upload an image
@router.post("/upload")
async def upload_image(file: UploadFile = File(...)):
    # validate file type and size
    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    contents = await file.read()    # read file
    if len(contents) > MAX_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds limit.")
    
    # save file with unique name
    extension = file.filename.split(".")[-1]
    unique_name = f"{uuid.uuid4()}.{extension}"     # generate unique filename with uuid
    file_path = UPLOAD_DIR / unique_name

    # create the file and write the contents to it
    with open(file_path, "wb") as f:
        f.write(contents)
    
    return {
        "filename": unique_name,
        "filepath": str(file_path),
        "message": "File uploaded successfully."
    }
# Pydantic model for the request body
class TryOnRequest(BaseModel):
    style: dict
    occasion: str
    filepath: str

# handle POST request to generate try-on image
@router.post("/tryon")
def generate_tryon(request: TryOnRequest):
    # validate request data
    if not request.style or not request.occasion or not request.filepath:
        raise HTTPException(status_code=400, detail="Invalid request data.")

    # extract request data
    style = request.style
    occasion = request.occasion
    filepath = request.filepath

    # generate try-on image
    try:
        try_on_image = generate_tryon_image(filepath, style, occasion)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate try-on image: {str(e)}")
    finally:
        # delete the uploaded file from uploads/
        if os.path.exists(filepath):
            os.remove(filepath)

    return {"image": try_on_image}

# Pydantic model for resut body
class LikeRequest(BaseModel):
    occasion: str
    style: dict
    tryon_image: str  # base64
# handle POST request to archieve liked-outfit to Mongo and Qdrant db
@router.post("/tryon/like")
def like_outfit(request: LikeRequest):
    # create an id shared by both Mongo and Qdrant
    shared_id = str(uuid.uuid4())
    # create a user id as a placeholder for later auth
    user_id = os.getenv("DEFAULT_USER_ID", "local-user")

    # create the document to insert into Mongo
    document = {
        "_id": shared_id,
        "user_id": user_id,
        "occasion": request.occasion,
        "style": request.style,
        "tryon_image": request.tryon_image,
        "created_at": datetime.utcnow(),
    }
    # insert into Mongo
    liked_outfits.insert_one(document)

    # embed liked outfit
    embed_input = f"{request.occasion} {request.style['style_name']} {request.style['description']}"
    vector = embed_texts([embed_input])[0]

    # upsert to Qdrant
    client.upsert(
        collection_name=LIKED_OUTFITS,
        points=[
            PointStruct(
                id=shared_id,
                vector=vector,
                payload={
                    "user_id": user_id
                }
            )
        ]
    )

    return {
        "message": "Liked outfir saved.",
        "id": shared_id
    }

