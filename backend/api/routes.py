import uuid
import os
from pathlib import Path
from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel
from agent.graph import graph
from services.tryon_vton import idm_vton_tryon, chained_tryon
from services.gemini import generate_tryon_image
from services.shopping import search_garment, categorize_key_pieces
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

# Pydantic model for the request body
class SearchRequest(BaseModel):
    occasion: str
    style: dict     # the chosen style from the 3 recommendations
    style_preference: str | None = None    # womenswear/menswear — sharpens shopping queries

# handle POST request to search for garments based on a style and occasion
@router.post("/styles/garments")
async def search_garments(request: SearchRequest):
    # validate request data
    if not request.style or not (
        request.style.get("key_pieces_categorized") or request.style.get("key_pieces")
    ):
        raise HTTPException(status_code=400, detail="Style with key_pieces is required.")

    # what each piece is
    # fall back to keyword rules only when the field is absent
    categorized = request.style.get("key_pieces_categorized") \
        or categorize_key_pieces(request.style.get("key_pieces", []))

    garments = {}
    # fetch garment search results for each key piece
    for category, pieces in categorized.items():
        # no piece in this category (e.g. a dress look has no separate bottom) —
        # omit the key entirely so the UI doesn't render a "no products" section
        if not pieces:
            continue

        try:
            garments[category] = search_garment(pieces[0], request.style_preference)
        except Exception:
            # one category's API failure must not kill the request
            garments[category] = []

    return {"garments": garments}
    """
    garments = {
    "top": [
        {"title": "Nordstrom Navy Wool Blazer", "image_url": "https://...", "product_link": "https://..."},
        {"title": "J.Crew Slim Blazer",          "image_url": "https://...", "product_link": "https://..."},
        # ... up to 4
    ],
    "bottom": [
        {"title": "...", "image_url": "...", "product_link": "..."},
    ],
    "shoes": []          #  empty category
    """

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
    garments: dict | None = None    # selectedGarments from GarmentPickerPage

# handle POST request to generate try-on image.
# Routing: a selected top with an image → IDM-VTON (image-conditioned);
# no top, or IDM-VTON fails (Space asleep, queue, quota) → pix2pix fallback.
@router.post("/tryon")
def generate_tryon(request: TryOnRequest):
    # validate request data
    if not request.style or not request.occasion or not request.filepath:
        raise HTTPException(status_code=400, detail="Invalid request data.")

    style = request.style
    occasion = request.occasion
    filepath = request.filepath

    try:
        # extract the selected garments, if any (only ones with a product image count)
        selected = request.garments or {}
        top = selected.get("top")
        top = top if top and top.get("image_url") else None
        bottom = selected.get("bottom")
        bottom = bottom if bottom and bottom.get("image_url") else None

        try:
            if top and bottom:
                # full outfit: chained VTON — top first, then bottom on the result
                # (internally degrades to the top-only result if step 2 fails)
                try_on_image = chained_tryon(filepath, top, bottom)
            elif top:
                # image-conditioned try-on: the actual product transfers
                try_on_image = idm_vton_tryon(
                    filepath,
                    top["image_url"],
                    garment_description=top.get("title", "an upper-body garment"),
                )
            elif bottom:
                try_on_image = idm_vton_tryon(
                    filepath,
                    bottom["image_url"],
                    garment_description=bottom.get("title", "a lower-body garment"),
                    category="lower_body",
                )
            else:
                # no garment product selected/found — text-based try-on
                try_on_image = generate_tryon_image(filepath, style, occasion)
        except Exception as vton_error:
            # VTON unavailable — degrade to instruction-driven try-on.
            # log the cause: silent fallbacks made a dead Space look like a model bug
            print(f"IDM-VTON failed, falling back to pix2pix: {vton_error}")
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

    # embed liked outfit — occasion + style_name ONLY (occasion-dominant by
    # design): the cache queries with occasion-only text, and mixing the long
    # description into this vector diluted the occasion so much that even a
    # near-identical occasion couldn't reach the cache threshold
    embed_input = f"{request.occasion} {request.style['style_name']}"
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

