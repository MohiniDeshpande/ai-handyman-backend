def needs_image(user_text: str) -> bool:
    triggers = [
        "what does it look like",
        "show me",
        "generate an image",
        "draw",
        "picture"
    ]
    return any(t in user_text.lower() for t in triggers)
