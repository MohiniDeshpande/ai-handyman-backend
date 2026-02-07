# router.py

def needs_image(text: str) -> bool:
    """
    Determine if user prompt requires image generation
    """
    text_lower = text.lower()
    return any(keyword in text_lower for keyword in ["draw", "generate image", "picture", "illustrate"])
