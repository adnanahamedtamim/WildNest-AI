from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, current_app, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from extensions import db
from models import Animal
from datetime import datetime
import os
import uuid

animals = Blueprint('animals', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def save_photo(file_storage):
    """Save an uploaded photo and return the stored filename, or None."""
    if not file_storage or file_storage.filename == '':
        return None
    if not allowed_file(file_storage.filename):
        return None
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    fname = f"{uuid.uuid4().hex}.{ext}"
    upload_dir = os.path.join(current_app.root_path, 'static', 'uploads')
    os.makedirs(upload_dir, exist_ok=True)
    file_storage.save(os.path.join(upload_dir, fname))
    return fname


def can_view_animal(animal):
    """Owner or original creator can view."""
    return current_user.id in (animal.owner_id, animal.created_by_id)


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

    return render_template('animals/profile.html',
                           animal=animal,
                           is_owner=is_owner,
                           is_creator=is_creator)
