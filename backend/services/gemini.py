import os
import base64
import io
import threading
import torch
from PIL import Image
from diffusers import StableDiffusionInstructPix2PixPipeline

_pipe = None
# one generation at a time: the pipeline's scheduler keeps per-run state,
# so concurrent runs corrupt each other (seen as "index 5 is out of bounds
# for dimension 0 with size 5" when duplicate requests overlapped)
_pipe_lock = threading.Lock()

def _get_pipe():
    global _pipe
    if _pipe is None:
        print("Loading instruct-pix2pix model (first call only — ~3GB download)...")
        # low_cpu_mem_usage=False loads weights directly into RAM, avoiding
        # the meta-tensor error that occurs when accelerate is installed
        _pipe = StableDiffusionInstructPix2PixPipeline.from_pretrained(
            "timbrooks/instruct-pix2pix",
            torch_dtype=torch.float32,
            safety_checker=None,
            low_cpu_mem_usage=False,
        )
        # use Apple Metal if available, otherwise CPU
        device = "mps" if torch.backends.mps.is_available() else "cpu"
        _pipe = _pipe.to(device)
        print(f"Model loaded on {device}.")
    return _pipe

"""
Generate a try-on image by editing the person's photo with an outfit instruction
using instruct-pix2pix running locally via Apple Metal (MPS).
Returns a base64-encoded PNG string.
"""
def generate_tryon_image(filepath: str, style: dict, occasion: str) -> str:
    style_name = style["style_name"]
    key_pieces = ", ".join(style["key_pieces"])
    description = style["description"]

    instruction = (
        f"Change this person's clothing to a {style_name} outfit: {description}. "
        f"Key pieces: {key_pieces}. Occasion: {occasion}. "
        f"Keep the person's face, hair, skin tone, and body proportions exactly as they are. "
        f"Keep the background exactly as it is. Only replace the clothing."
    )

    image = Image.open(filepath).convert("RGB")
    image = image.resize((384, 384))

    with _pipe_lock:
        pipe = _get_pipe()
        result = pipe(
            instruction,
            image=image,
            num_inference_steps=4,
            image_guidance_scale=1.5,
            guidance_scale=7.5,
        ).images[0]

    buf = io.BytesIO()
    result.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()
