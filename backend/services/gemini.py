import os
import json
from google import genai


client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

'''
Function to generate 3 style recommendations and reasonings using Gemini API
@param occasion: a string occasion input by the user
@return: a list of dictionaries, each containing a style recommendation and its one-sentence reasoning
'''
def get_style_recommendations(occasion: str) -> list[dict]:
    prompt = f"""
    A user is attending "{occasion}".
    Generate exactly 3 different outfit styles suitable for this occasion.
    Each style should be distinct in character (e.g. classic, modern, smart casual).
    Respond with only a JSON array of 3 objects and reasonings should be concise (1 sentence).
    Each object should have the following format:
    [
        {{
        "style_name": "Classic Professional",
        "description": "A timeless, polished look",
        "key_pieces": ["navy blazer", "white dress shirt", "grey trousers", "oxford shoes"],
        "reasoning": "This style conveys authority and professionalism."
        }},
        {{
        "style_name": "Modern Business",
        "description": "...",
        "key_pieces": ["..."],
        "reasoning": "..."
        }},
        {{
        "style_name": "Smart Casual",
        "description": "...",
        "key_pieces": ["..."],
        "reasoning": "..."
        }}
    ]
    """
    
    # call Gemini API to generate style recommendations
    # new SDK is synchronous, so without async/awai
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
    )

    # extract the text response and parse it as JSON
    text = response.text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]

    return json.loads(text)
