"""Wardrobe routes: upload, list, and delete clothing items.

Endpoints
    POST   /wardrobe/upload       —  Upload image to Cloudinary, save DB record.
    GET    /wardrobe/{user_id}    —  List all wardrobe items for a user.
    DELETE /wardrobe/{item_id}    —  Delete from Cloudinary then DB.

All endpoints require authentication via ``get_current_user``.
Image uploads use server-side signed Cloudinary (secret never hits the client).
"""

from datetime import datetime
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models import User, Wardrobe
from routes.auth import get_current_user
from services.cloudinary_svc import upload_image, delete_image

router = APIRouter()

# 10 MB max upload
MAX_UPLOAD_BYTES = 10 * 1024 * 1024

ALLOWED_TYPES = {"image/jpeg", "image/png", "image/webp"}


# ── Pydantic Schemas ───────────────────────────────────


class WardrobeItemData(BaseModel):
    """Single wardrobe item returned in API responses."""

    id: int
    user_id: int
    cloudinary_url: str
    cloudinary_public_id: str
    category: str | None
    color: str | None
    description: str | None
    uploaded_at: datetime | None  # Serialized to ISO-8601 via model_dump(mode='json')

    model_config = {"from_attributes": True}


AuthResponse = dict[str, Any]


# ── Helpers ────────────────────────────────────────────


def _validate_image(file: UploadFile) -> bytes:
    """Check file size + MIME type, return raw bytes."""
    if file.content_type and file.content_type not in ALLOWED_TYPES:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "data": {},
                "message": f"Unsupported file type: {file.content_type}. Allowed: JPEG, PNG, WebP.",
            },
        )

    raw = file.file.read()
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=400,
            detail={
                "status": "error",
                "data": {},
                "message": "File too large. Maximum is 10 MB.",
            },
        )
    return raw


def _get_item_or_404(item_id: int, db: Session) -> Wardrobe:
    """Return Wardrobe item or raise 404."""
    item = db.query(Wardrobe).filter(Wardrobe.id == item_id).first()
    if not item:
        raise HTTPException(
            status_code=404,
            detail={"status": "error", "data": {}, "message": "Wardrobe item not found."},
        )
    return item


def _require_wardrobe_ownership(user_id: int, current_user: User) -> None:
    """Raise 403 if *current_user* does not own wardrobe of *user_id*."""
    if current_user.id != user_id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": {},
                "message": "You can only access your own wardrobe.",
            },
        )


def _require_item_ownership(item: Wardrobe, current_user: User) -> None:
    """Raise 403 if *current_user* does not own *item*."""
    if item.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail={
                "status": "error",
                "data": {},
                "message": "You can only delete your own items.",
            },
        )


def _isoformat(dt) -> str:
    """Return *dt* as ISO-8601 string or empty string."""
    if dt is None:
        return ""
    return dt.isoformat()


# ── Routes ─────────────────────────────────────────────


@router.post("/upload", status_code=201)
async def upload_wardrobe_item(
    file: UploadFile = File(...),
    category: str | None = Form(None),
    color: str | None = Form(None),
    description: str | None = Form(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Upload a clothing image to Cloudinary and save the record.

    *file* — multipart image (JPEG, PNG, or WebP ≤ 10 MB).
    *category*, *color*, *description* — optional metadata form fields.
    """
    raw = _validate_image(file)

    public_id = f"wutt_{current_user.id}_{uuid4().hex[:12]}"

    try:
        url, pid = upload_image(raw, public_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "data": {}, "message": str(exc)},
        )
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail={
                "status": "error",
                "data": {},
                "message": f"Cloudinary upload failed — {exc}",
            },
        )

    item = Wardrobe(
        user_id=current_user.id,
        cloudinary_url=url,
        cloudinary_public_id=pid,
        category=category,
        color=color,
        description=description,
    )
    db.add(item)
    db.commit()
    db.refresh(item)

    data = WardrobeItemData.model_validate(item).model_dump(mode="json")

    return {"status": "success", "data": data, "message": "Item uploaded successfully."}


@router.get("/{user_id}")
def list_wardrobe(
    user_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Return all wardrobe items for *user_id*.

    Raises:
        403 if the current user does not own this wardrobe.
    """
    _require_wardrobe_ownership(user_id, current_user)
    items = (
        db.query(Wardrobe)
        .filter(Wardrobe.user_id == user_id)
        .order_by(Wardrobe.uploaded_at.desc())
        .all()
    )

    data = []
    for item in items:
        data.append(WardrobeItemData.model_validate(item).model_dump(mode="json"))

    return {"status": "success", "data": data, "message": ""}


@router.delete("/{item_id}")
def delete_wardrobe_item(
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> AuthResponse:
    """Delete a wardrobe item from Cloudinary then the database.

    Raises:
        403 if the current user does not own this item.
        404 if the item is not found.

    Returns 204-style success with no data payload.
    """
    item = _get_item_or_404(item_id, db)
    _require_item_ownership(item, current_user)
    public_id = item.cloudinary_public_id

    try:
        delete_image(public_id)
    except RuntimeError as exc:
        raise HTTPException(
            status_code=503,
            detail={"status": "error", "data": {}, "message": str(exc)},
        )

    db.delete(item)
    db.commit()

    return {"status": "success", "data": {}, "message": "Item deleted successfully."}
