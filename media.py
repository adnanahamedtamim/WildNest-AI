"""Shared file-upload helpers for photos/videos across animals, chat, and profiles."""
from flask import current_app
import os
import uuid

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'ogg'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def _ext(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def allowed_file(filename):
    return _ext(filename) in ALLOWED_EXTENSIONS


def _store(file_storage):
    ext = _ext(file_storage.filename)
    fname = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, fname))
    return fname


def save_photo(file_storage):
    """Save an uploaded image and return the stored filename, or None."""
    if not file_storage or file_storage.filename == '':
        return None
    if _ext(file_storage.filename) not in IMAGE_EXTENSIONS:
        return None
    return _store(file_storage)


def save_media(file_storage):
    """Save an image OR video. Returns (filename, media_type) or (None, None)."""
    if not file_storage or file_storage.filename == '':
        return None, None
    ext = _ext(file_storage.filename)
    if ext in IMAGE_EXTENSIONS:
        return _store(file_storage), 'image'
    if ext in VIDEO_EXTENSIONS:
        return _store(file_storage), 'video'
    return None, None
