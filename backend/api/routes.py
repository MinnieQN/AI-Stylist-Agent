from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from services.gemini import get_style_recommendations

router = APIRouter()

# Pydantic model for the request body
class StyleRequest(BaseModel):
    occasion: str

# handle POST request to generate 3 recommended styles for a given occasion
@router.post("/styles")
def recommend_styles(request: StyleRequest):
    # handle empty occasion input
    if not request.occasion.strip():
        raise HTTPException(status_code=400, detail="Occasion cannot be empty.")

    try:
        # call Gemini to get style reommendations
        recommendations = get_style_recommendations(request.occasion)
        return {
            "occasion": request.occasion,
            "recommendations": recommendations  # list of dictionaries with style_name, description, key_pieces, reasoning
        }
    except Exception as e:
        # handle errors from Gemini API or JSON parsing
        raise HTTPException(status_code=500, detail=f"Failed to generate styles: {str(e)}")