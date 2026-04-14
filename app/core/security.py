def extract_bearer_token(authorization_header: str | None) -> str | None:
	if not authorization_header:
		return None

	parts = authorization_header.strip().split()
	if len(parts) != 2 or parts[0].lower() != "bearer":
		return None

	return parts[1]
