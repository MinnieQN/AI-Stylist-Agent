import os
import base64
import tempfile
import httpx
from gradio_client import Client, handle_file

"""
Service: IDM-VTON image-conditioned try-on.
Calls your duplicated HuggingFace ZeroGPU Space via gradio_client.
Person image comes from a local filepath (the uploaded body photo);
garment image comes from a web URL (Google Shopping thumbnail).
Returns the try-on image as a base64 string (same contract as pix2pix path).
Raises on any failure — the /tryon route catches and falls back to pix2pix.
"""

# your duplicated Space — set in .env as HF_SPACE=your_username/IDM-VTON
HF_SPACE = os.getenv("HF_SPACE", "your_username/IDM-VTON")

# module-level cached client: connect once, but lazily on first use —
# connecting at import would make an unreachable/paused Space crash the
# whole backend at boot instead of falling back to pix2pix per-request.
# NOTE: if the Space is asleep, the first predict() after idle is slow
# (cold start) — that's expected ZeroGPU behavior, not a bug.
_client = None

def _get_client() -> Client:
    global _client
    if _client is None:
        # gradio_client >= 2.0 renamed hf_token → token.
        # generous read timeout: a ZeroGPU Space asleep after idle takes
        # minutes to cold-start — the default timeout gave up mid-boot and
        # every first-try-on-of-the-day silently degraded to pix2pix
        _client = Client(
            HF_SPACE,
            token=os.getenv("HF_TOKEN"),
            httpx_kwargs={"timeout": httpx.Timeout(300.0, connect=30.0)},
        )
    return _client


"""
Check whether the Space's /tryon endpoint accepts the extra category
argument (i.e. the app.py patch is live). Reads the client's cached API
config — no network call. NOTE: the config is fetched at connect time,
so after patching/rebuilding the Space, restart this backend.
@param client: connected gradio client
@return: True if /tryon takes 8+ parameters (category exposed)
"""
def _space_supports_category(client: Client) -> bool:
    api = client.view_api(return_format="dict", print_info=False)
    params = api.get("named_endpoints", {}).get("/tryon", {}).get("parameters", [])
    return len(params) >= 8


"""
Download the garment image from its web URL to a local temp file.
gradio_client's handle_file accepts URLs directly on most Spaces, but
downloading locally is more reliable (some shopping thumbnail hosts
block hotlinking or redirect, which confuses the Space-side fetch).
@param image_url: the product image URL from Google Shopping
@return: path to the downloaded temp file
"""
def _download_garment(image_url: str) -> str:
    response = httpx.get(image_url, timeout=20, follow_redirects=True)
    response.raise_for_status()

    # infer a usable extension; default jpg
    content_type = response.headers.get("content-type", "")
    extension = ".png" if "png" in content_type else ".jpg"

    # delete=False: gradio_client needs to read the file after we close it;
    # cleaned up in the caller's finally block
    tmp = tempfile.NamedTemporaryFile(suffix=extension, delete=False)
    tmp.write(response.content)
    tmp.close()
    return tmp.name


"""
Run image-conditioned try-on: person photo + garment image → try-on image.
@param person_filepath: local path to the uploaded full-body photo
@param garment_image_url: web URL of the selected garment image
@param garment_description: short text describing the garment (helps the model)
@param category: mask region — "upper_body" | "lower_body" | "dresses".
       Anything other than upper_body requires the duplicated Space to be
       patched to accept the category argument; upper_body is sent as the
       original 7-arg call so it works on an unpatched Space too.
@return: base64-encoded try-on image string
@raises: any exception from download, the Space call, or result reading —
         the route treats any raise as "fall back to pix2pix"
"""
def idm_vton_tryon(
    person_filepath: str,
    garment_image_url: str,
    garment_description: str = "an upper-body garment",
    category: str = "upper_body",
) -> str:
    garment_path = None
    try:
        # 1. bring the garment image local
        garment_path = _download_garment(garment_image_url)

        # 2. call the Space
        # NOTE: this argument list must match YOUR Space's "Use via API" page
        # (adjust here if your duplicated Space's signature differs — this is
        # the standard yisol/IDM-VTON signature proven in the standalone test)
        args = [
            dict(background=handle_file(person_filepath), layers=[], composite=None),
            handle_file(garment_path),      # garment image
            garment_description,            # garment description text
            True,                           # auto-generate mask
            False,                          # crop
            30,                             # denoise steps
            42,                             # seed
        ]
        client = _get_client()
        if category != "upper_body":
            # guard: on an unpatched Space (7 params) gradio_client silently
            # DROPS the extra category arg — the call "succeeds" but masks the
            # upper body, painting e.g. pants onto the torso. Fail loudly instead.
            if not _space_supports_category(client):
                raise RuntimeError(
                    f"Space {HF_SPACE} does not accept a category argument — "
                    f"apply the app.py patch (and restart this backend) to "
                    f"enable {category} try-on."
                )
            args.append(category)           # 8th arg: only the patched Space has it
        result = client.predict(*args, api_name="/tryon")

        # 3. extract the output image path from the result.
        # the Space returns a tuple: (tryon_image_path, masked_image_path) —
        # gradio_client downloads outputs locally and gives us file paths
        output_path = result[0] if isinstance(result, (tuple, list)) else result

        # 4. read and return as base64 (matches the pix2pix response contract)
        with open(output_path, "rb") as f:
            return base64.b64encode(f.read()).decode("utf-8")

    finally:
        # clean up the downloaded garment temp file
        if garment_path and os.path.exists(garment_path):
            os.remove(garment_path)


"""
Chained full-body try-on: fit the top, then fit the bottom onto the result.
If the bottom step fails (Space error, quota, queue), return the top-only
result rather than erroring — half the outfit beats none.
@param person_filepath: local path to the uploaded full-body photo
@param top: selected top product dict with image_url + title
@param bottom: selected bottom product dict with image_url + title
@return: base64-encoded try-on image string
@raises: only if the FIRST (top) step fails — route falls back to pix2pix
"""
def chained_tryon(person_filepath: str, top: dict, bottom: dict) -> str:
    step1_b64 = idm_vton_tryon(
        person_filepath,
        top["image_url"],
        top.get("title", "an upper-body garment"),
    )

    # feed step 1's output back in as the person image for the bottom pass
    step1_path = None
    try:
        tmp = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
        tmp.write(base64.b64decode(step1_b64))
        tmp.close()
        step1_path = tmp.name

        return idm_vton_tryon(
            step1_path,
            bottom["image_url"],
            bottom.get("title", "a lower-body garment"),
            category="lower_body",
        )
    except Exception as step2_error:
        # chain step 2 failed — ship the top-only result (log why: a silent
        # degrade here already cost one debugging session)
        print(f"Chained try-on: bottom step failed, returning top-only result: {step2_error}")
        return step1_b64
    finally:
        if step1_path and os.path.exists(step1_path):
            os.remove(step1_path)