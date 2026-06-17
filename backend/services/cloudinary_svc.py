"""Cloudinary image upload and deletion service.

Uses server-side signed uploads — the Cloudinary API secret is NEVER
exposed to the frontend (per CLAUDE.md security rule).

Public functions
    upload_image(file_bytes, public_id)  →  (url, public_id)
    delete_image(public_id)              →  bool
"""

import cloudinary
import cloudinary.uploader
import cloudinary.api
from config import settings

# Configure once at import time
cloudinary.config(
    cloud_name=settings.cloudinary_cloud_name,
    api_key=settings.cloudinary_api_key,
    api_secret=settings.cloudinary_api_secret,
    secure=True,
)


def upload_image(file_bytes: bytes, public_id: str) -> tuple[str, str]:
    """Upload *file_bytes* to Cloudinary.

    Args:
        file_bytes: The raw image bytes.
        public_id: A unique identifier (e.g. ``f"wutt_{user_id}_{uuid4()}"``).

    Returns:
        ``(secure_url, public_id)`` tuple.

    Raises:
        RuntimeError: If Cloudinary API key / secret are not configured.
        cloudinary.exceptions.Error: On upload failure.
    """
    if not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise RuntimeError(
            "Cloudinary API key or secret not set. "
            "Configure CLOUDINARY_API_KEY and CLOUDINARY_API_SECRET in .env."
        )

    try:
        result = cloudinary.uploader.upload(
            file_bytes,
            public_id=public_id,
            overwrite=False,
            resource_type="image",
        )
    except cloudinary.exceptions.Error as exc:
        raise RuntimeError(f"Cloudinary upload failed — {exc}") from exc
    return result["secure_url"], result["public_id"]


def delete_image(public_id: str) -> bool:
    """Delete an image from Cloudinary by *public_id*.

    Returns:
        True if deleted, False if the resource wasn't found.
    """
    if not settings.cloudinary_api_key or not settings.cloudinary_api_secret:
        raise RuntimeError(
            "Cloudinary API key or secret not set."
        )

    try:
        result = cloudinary.uploader.destroy(public_id, resource_type="image")
        return result.get("result") == "ok"
    except cloudinary.exceptions.NotFound:
        return False
    except cloudinary.exceptions.Error as exc:
        raise RuntimeError(f"Cloudinary deletion failed — {exc}") from exc
