from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
from PIL import Image
import torch
import numpy as np

"""
Segmentation service for processing user uploaded image.
Take an image path, run the model, return the segmentation mask.
"""
model_name = "mattmdjaga/segformer_b2_clothes"

# lazy singletons: loading at import would download/load ~200MB on every
# backend boot even when segmentation is never used (same lesson as the
# gradio client — import-time work belongs at first use)
_processor = None
_model = None

def _get_model():
    global _processor, _model
    if _model is None:
        print("Loading SegFormer clothes model (first call only)...")
        _processor = SegformerImageProcessor.from_pretrained(model_name)
        _model = SegformerForSemanticSegmentation.from_pretrained(model_name)
    return _processor, _model

def segment_image(image_path: str) -> dict:
    processor, model = _get_model()
    # load user's full-body image
    image = Image.open(image_path).convert("RGB")
    # prepare image for the model - convert to tensor
    inputs = processor(image, return_tensors="pt")

    # run the model to get segmentation mask
    with torch.no_grad():
        outputs = model(**inputs)

    # convert model output to 2D segmentation mask
    # result shape: (height, width)
    mask = processor.post_process_semantic_segmentation(
        outputs,
        target_sizes=[image.size[::-1]]
    )[0].cpu().numpy()

    """
    model IDs:
    4  -> upper-clothes
    5  -> skirt
    6  -> pants
    7  -> dress
    9  -> left-shoe
    10 -> right-shoe
    """
    # create a boolean mask for each clothing item
    top_mask = mask == 4
    bottom_mask = (mask == 5) | (mask == 6) | (mask == 7)
    shoe_mask = (mask == 9) | (mask == 10)
    clothing_mask = top_mask | bottom_mask | shoe_mask

    return {
        "raw_mask": mask,
        "top_mask": top_mask,
        "bottom_mask": bottom_mask,
        "shoe_mask": shoe_mask,
        "clothing_mask": clothing_mask
    }