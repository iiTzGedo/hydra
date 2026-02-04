"""Profile document formatting for API responses."""


def format_profile(doc: dict) -> dict:
    """Format a profile document for API response."""
    return {
        "profileId": doc["profileId"],
        "nodeId": doc["nodeId"],
        "version": doc["version"],
        "collectedAt": doc["collectedAt"],
        "submittedAt": doc["submittedAt"],
        "agentVersion": doc["agentVersion"],
        "collectionLevel": doc["collectionLevel"],
        "serviceIds": doc.get("serviceIds", []),
        "hardware": doc.get("hardware"),
        "network": doc.get("network"),
        "storage": doc.get("storage"),
        "software": doc.get("software"),
        "users": doc.get("users"),
        "configs": doc.get("configs"),
        "metadata": doc.get("metadata", {}),
    }


def format_profile_summary(doc: dict) -> dict:
    """Format a profile document for list response."""
    return {
        "profileId": doc["profileId"],
        "nodeId": doc["nodeId"],
        "version": doc["version"],
        "collectedAt": doc["collectedAt"],
        "submittedAt": doc["submittedAt"],
        "collectionLevel": doc["collectionLevel"],
        "serviceCount": len(doc.get("serviceIds", [])),
    }
