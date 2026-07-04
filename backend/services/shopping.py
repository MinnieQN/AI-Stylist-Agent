import os
from serpapi import GoogleSearch

"""
Search Google Shopping for a garment and return product results.
@param query: garment description, e.g. "navy blazer men business casual"
@param limit: how many products to return
@return: list of dicts with title, image_url, product_link
"""
def search_garment(query: str, limit: int = 4) -> list[dict]:
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