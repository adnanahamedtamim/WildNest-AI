from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort)
from flask_login import login_required, current_user
from extensions import db
from models import Animal, EnvironmentalLog
from charts import build_env_charts
from datetime import datetime
import os
import uuid

animals = Blueprint('animals', __name__)

IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
VIDEO_EXTENSIONS = {'mp4', 'mov', 'webm', 'ogg'}
ALLOWED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS


def _ext(filename):
    return filename.rsplit('.', 1)[1].lower() if '.' in filename else ''


def allowed_file(filename):
    return _ext(filename) in ALLOWED_EXTENSIONS


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


def _store(file_storage):
    ext = _ext(file_storage.filename)
    fname = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, fname))
    return fname


def can_view_animal(animal):
    """Owner or original creator can view."""
    return current_user.id in (animal.owner_id, animal.created_by_id)


def _to_float(value):
    try:
        return float(value) if value not in (None, '') else None
    except (ValueError, TypeError):
        return None


def _to_int(value):
    try:
        return int(value) if value not in (None, '') else None
    except (ValueError, TypeError):
        return None


@animals.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        species = request.form.get('species', '').strip()

        if not name or not species:
            flash('Name and species are required.', 'danger')
            return render_template('animals/new.html')

        origin = request.form.get('origin', 'rescue')

        rescue_date = None
        rd = request.form.get('rescue_date', '').strip()
        if rd:
            try:
                rescue_date = datetime.strptime(rd, '%Y-%m-%d').date()
            except ValueError:
                rescue_date = None

        age = request.form.get('age_years', '').strip()
        try:
            age_val = float(age) if age else None
        except ValueError:
            age_val = None

        animal = Animal(
            name=name,
            species=species,
            common_name=request.form.get('common_name', '').strip() or None,
            age_years=age_val,
            sex=request.form.get('sex', '').strip() or None,
            origin=origin,
            rescue_date=rescue_date,
            rescue_location=request.form.get('rescue_location', '').strip() or None,
            rescue_reason=request.form.get('rescue_reason', '').strip() or None,
            medical_history=request.form.get('medical_history', '').strip() or None,
            stress_triggers=request.form.get('stress_triggers', '').strip() or None,
            dietary_requirements=request.form.get('dietary_requirements', '').strip() or None,
            photo_path=save_photo(request.files.get('photo')),
            status='in_care',
            owner_id=current_user.id,
            created_by_id=current_user.id,
        )
        db.session.add(animal)
        db.session.commit()

        flash(f'{name} has been added to WildNest!', 'success')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    return render_template('animals/new.html')


@animals.route('/<int:animal_id>')
@login_required
def profile(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if not can_view_animal(animal):
        flash('You do not have access to this animal.', 'danger')
        return redirect(url_for('auth.dashboard_redirect'))

    is_owner = animal.owner_id == current_user.id
    is_creator = animal.created_by_id == current_user.id

    logs = animal.env_logs  # ordered by timestamp (oldest first)
    charts = build_env_charts(logs)
    recent_logs = list(reversed(logs))[:12]  # newest first for the history table

    return render_template('animals/profile.html',
                           animal=animal,
                           is_owner=is_owner,
                           is_creator=is_creator,
                           charts=charts,
                           log_count=len(logs),
                           recent_logs=recent_logs)


@animals.route('/<int:animal_id>/log', methods=['GET', 'POST'])
@login_required
def log_env(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    # only the current owner may log data
    if animal.owner_id != current_user.id:
        flash('Only the current owner can log data for this animal.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    if request.method == 'POST':
        media_path, media_type = save_media(request.files.get('media'))

        log = EnvironmentalLog(
            animal_id=animal.id,
            logged_by_id=current_user.id,
            temperature_f=_to_float(request.form.get('temperature_f')),
            humidity_pct=_to_float(request.form.get('humidity_pct')),
            lighting_hours=_to_float(request.form.get('lighting_hours')),
            feeding_amount_g=_to_float(request.form.get('feeding_amount_g')),
            weight_g=_to_float(request.form.get('weight_g')),
            stress_level=_to_int(request.form.get('stress_level')),
            activity_level=_to_int(request.form.get('activity_level')),
            notes=request.form.get('notes', '').strip() or None,
            media_path=media_path,
            media_type=media_type,
        )
        db.session.add(log)
        db.session.commit()

        flash(f'Logged today\'s entry for {animal.name}.', 'success')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    return render_template('animals/log_env.html', animal=animal)
