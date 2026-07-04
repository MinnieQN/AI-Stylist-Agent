from transformers import SegformerImageProcessor, SegformerForSemanticSegmentation
from PIL import Image
import torch
import numpy as np

"""
Segmentation service for processing user uploaded image.
Take an image path, run the model, return the segmentation mask.
"""
# Load model and image processor
model_name = "mattmdjaga/segformer_b2_clothes"
processor = SegformerImageProcessor.from_pretrained(model_name)
model = SegformerForSemanticSegmentation.from_pretrained(model_name)

def segment_image(image_path: str) -> dict:
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