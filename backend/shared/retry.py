import time

def generate_with_retry(client, max_attempts=3, **kwargs):
    """
    Wraps client.models.generate_content with exponential backoff retry
    for transient 503 UNAVAILABLE errors from the Gemini API.
    """
    for attempt in range(max_attempts):
        try:
            return client.models.generate_content(**kwargs)
        except Exception as e:
            if "503" in str(e) and attempt < max_attempts - 1:
                wait = 2 ** attempt  # 1s, 2s
                print(f"Gemini 503 — retrying in {wait}s (attempt {attempt + 1}/{max_attempts})")
                time.sleep(wait)
                continue
            raise
