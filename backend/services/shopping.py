import os
import re
from serpapi import GoogleSearch

# map the app's style-preference options to shopping search terms
GENDER_TERMS = {"womenswear": "women's", "menswear": "men's"}

"""
Reduce a free-form key piece to a clean product search phrase.
The LLM emits descriptive text like
"high-waisted wide-leg trousers in a pastel shade (e.g., pale yellow) or chinos"
— parentheticals and "or" alternatives pollute Google Shopping queries
(they pull outfit sets and mismatched garment types), so keep only the
first alternative and drop the notes.
@param piece: raw key piece text from the recommendation
@return: cleaned search phrase, e.g. "high-waisted wide-leg trousers in a pastel shade"
"""
def _clean_piece(piece: str) -> str:
    piece = re.sub(r"\([^)]*\)", "", piece)   # drop parenthetical notes
    # keep the LAST "or" alternative: it always ends with the full noun phrase,
    # whether the "or" joins fabrics ("chiffon or silk maxi dress" → "silk maxi
    # dress") or whole garments ("sandals or flat mules" → "flat mules");
    # the first part can be a bare adjective ("chiffon") that derails the search
    piece = piece.split(" or ")[-1]
    return " ".join(piece.split())

"""
Search Google Shopping for a garment and return product results.
The query is the cleaned piece plus a gender term — NOT the style name,
which reads as noise to the shopping engine (proven: "Effortlessly Chic
... shirt (half-tucked)" returned a men's shirt first; "women's ... shirt"
returned all-women's single garments).
@param key_piece: the garment to search for, e.g. "navy blazer"
@param style_preference: "womenswear" | "menswear" | anything else → no gender term
@param limit: how many products to return
@return: list of dicts with title, image_url, product_link
"""
def search_garment(key_piece: str, style_preference: str | None = None, limit: int = 4) -> list[dict]:
    gender = GENDER_TERMS.get((style_preference or "").lower(), "")
    query = f"{gender} {_clean_piece(key_piece)}".strip()

    params = {
        "engine": "google_shopping",
        "q": query,
        "api_key": os.getenv("SERPAPI_KEY"),
        "num": limit,
    }
    results = GoogleSearch(params).get_dict()

    products = []
    for item in results.get("shopping_results", [])[:limit]:
        products.append({
            "title": item.get("title", ""),
            "image_url": item.get("thumbnail", ""),
            "product_link": item.get("product_link", item.get("link", "")),
        })
    return products

"""
Map free-form key_pieces to garment categories using keyword rules.
Pieces that match no category default to "top".
@param key_pieces: e.g. ["navy blazer", "grey trousers", "oxford shoes"]
@return: dict of category -> list of piece names,
         e.g. {"top": ["navy blazer"], "bottom": ["grey trousers"], "shoes": ["oxford shoes"]}
"""
def categorize_key_pieces(key_pieces: list[str]) -> dict:
    BOTTOM_WORDS = ["trouser", "pant", "jean", "chino", "skirt", "short", "slack"]
    SHOES_WORDS = ["shoe", "oxford", "loafer", "sneaker", "boot", "heel",
                   "derby", "flat", "sandal", "pump"]

    categories = {"top": [], "bottom": [], "shoes": []}

    for piece in key_pieces:
        piece_lower = piece.lower()
        if any(word in piece_lower for word in SHOES_WORDS):
            categories["shoes"].append(piece)
        elif any(word in piece_lower for word in BOTTOM_WORDS):
            categories["bottom"].append(piece)
        else:
            # tops, outerwear, accessories all land here — searched as "top"
            categories["top"].append(piece)

    return categories