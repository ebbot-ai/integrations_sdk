def request_headers(auth_key: str) -> dict:
    return {"Authorization": f"Bearer {auth_key}"}
