from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request, jsonify, send_file, abort)
from flask_login import login_required, current_user
from extensions import db
from models import Animal, EnvironmentalLog, MedicalRecord, User, HandoverRecord
from charts import build_env_charts
from media import save_photo, save_media
from weather import get_current_weather
from wildsight_ai import generate_todays_meal_plan
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime, timedelta
import io
import math
import uuid
import qrcode

animals = Blueprint('animals', __name__)

# assumed standard follow-up interval for any logged vaccination (see feedback note)
VACCINATION_INTERVAL_DAYS = 365


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
        age_val = None
        if age:
            try:
                age_val = float(age)
            except ValueError:
                flash('Age must be a number.', 'danger')
                return render_template('animals/new.html')
            if not math.isfinite(age_val) or age_val < 0 or age_val > 200:
                flash('Age must be a realistic number between 0 and 200 years.', 'danger')
                return render_template('animals/new.html')

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

    if animal.profile_private and not is_owner:
        return render_template('animals/private.html', animal=animal)

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


@animals.route('/<int:animal_id>/handover', methods=['GET', 'POST'])
@login_required
def handover(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can hand over this pet.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    if request.method == 'POST':
        email = request.form.get('new_owner_email', '').strip().lower()
        new_owner = User.query.filter_by(email=email).first()

        if not new_owner:
            flash('No WildNest account found with that email. The new owner needs to register first.', 'danger')
            return redirect(url_for('animals.handover', animal_id=animal.id))
        if new_owner.id == current_user.id:
            flash("That's already you — enter the new owner's email.", 'danger')
            return redirect(url_for('animals.handover', animal_id=animal.id))

        record = HandoverRecord(
            animal_id=animal.id,
            from_user_id=current_user.id,
            to_user_id=new_owner.id,
        )
        db.session.add(record)

        animal.owner_id = new_owner.id
        animal.handover_date = datetime.utcnow()
        animal.status = 'adopted'

        listing = animal.active_listing
        if listing:
            listing.status = 'closed'

        try:
            db.session.commit()
        except SQLAlchemyError:
            db.session.rollback()
            flash('Something went wrong completing the handover — nothing was '
                  'changed. Please try again.', 'danger')
            return redirect(url_for('animals.handover', animal_id=animal.id))

        return redirect(url_for('animals.handover_certificate',
                                animal_id=animal.id, record_id=record.id))

    return render_template('animals/handover.html', animal=animal)


@animals.route('/<int:animal_id>/handover/<int:record_id>/certificate')
@login_required
def handover_certificate(animal_id, record_id):
    animal = Animal.query.get_or_404(animal_id)
    record = HandoverRecord.query.get_or_404(record_id)
    if record.animal_id != animal.id or current_user.id not in (record.from_user_id, record.to_user_id):
        flash('You do not have access to this record.', 'danger')
        return redirect(url_for('main.dashboard'))

    return render_template('animals/handover_certificate.html', animal=animal, record=record)


@animals.route('/<int:animal_id>/delete', methods=['POST'])
@login_required
def delete(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can delete this pet.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    name = animal.name
    db.session.delete(animal)
    db.session.commit()
    flash(f'{name} has been removed from WildNest.', 'success')
    return redirect(url_for('main.dashboard'))


@animals.route('/<int:animal_id>/hide-from-dashboard', methods=['POST'])
@login_required
def hide_from_dashboard(animal_id):
    """Non-destructive: only removes this pet from the CREATOR's own dashboard.
    Never touches the current owner's copy, data, or access in any way."""
    animal = Animal.query.get_or_404(animal_id)
    if animal.created_by_id != current_user.id or animal.owner_id == current_user.id:
        flash('This option is only for pets you rescued but no longer own.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    animal.creator_dashboard_hidden = True
    db.session.commit()
    flash(f"{animal.name} has been removed from your dashboard. "
          f"{animal.owner.name} still has full access to their pet.", 'success')
    return redirect(url_for('main.dashboard'))


@animals.route('/<int:animal_id>/photo', methods=['POST'])
@login_required
def update_photo(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        return jsonify({'error': 'Only the current owner can change this photo.'}), 403

    fname = save_photo(request.files.get('photo'))
    if not fname:
        flash('Please choose a valid image file (PNG, JPG, GIF, WEBP).', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    animal.photo_path = fname
    db.session.commit()
    flash(f"{animal.name}'s photo has been updated.", 'success')
    return redirect(url_for('animals.profile', animal_id=animal.id))


@animals.route('/<int:animal_id>/meal/generate', methods=['POST'])
@login_required
def generate_meal(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash("Only the current owner can generate this pet's meal plan.", 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    weather = get_current_weather(animal.current_location)
    plan = generate_todays_meal_plan(animal, weather)

    animal.meal_plan_content = plan
    animal.meal_plan_generated_at = datetime.utcnow()
    if weather:
        observed_str = ''
        if weather.get('observed_at'):
            try:
                observed_time = datetime.strptime(weather['observed_at'], '%Y-%m-%dT%H:%M')
                observed_str = f" (latest reading: {observed_time.strftime('%I:%M %p').lstrip('0')} local)"
            except ValueError:
                observed_str = ''
        animal.meal_plan_weather_summary = (
            f"{weather['temp_f']}°F, {weather['humidity_pct']}% humidity — {weather['description']} "
            f"· {weather['place_name']}{observed_str}"
        )
    else:
        animal.meal_plan_weather_summary = None
    db.session.commit()

    if not weather:
        flash("Generated today's plan from history alone — add a Current Location under "
              "Origin & Background for weather-aware suggestions.", 'warning')
    else:
        flash(f"Today's meal plan for {animal.name} is ready.", 'success')

    return redirect(url_for('animals.profile', animal_id=animal.id))


@animals.route('/<int:animal_id>/background', methods=['POST'])
@login_required
def update_background(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can edit this.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    rescue_date = None
    rd = request.form.get('rescue_date', '').strip()
    if rd:
        try:
            rescue_date = datetime.strptime(rd, '%Y-%m-%d').date()
        except ValueError:
            rescue_date = animal.rescue_date

    animal.rescue_date = rescue_date
    animal.rescue_location = request.form.get('rescue_location', '').strip() or None
    animal.rescue_reason = request.form.get('rescue_reason', '').strip() or None
    animal.current_location = request.form.get('current_location', '').strip() or None
    db.session.commit()

    flash(f"{animal.name}'s background has been updated.", 'success')
    return redirect(url_for('animals.profile', animal_id=animal.id))


@animals.route('/<int:animal_id>/log', methods=['GET', 'POST'])
@login_required
def log_env(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    # only the current owner may log data
    if animal.owner_id != current_user.id:
        flash('Only the current owner can log data for this animal.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    if request.method == 'POST':
        humidity_val = _to_float(request.form.get('humidity_pct'))
        if humidity_val is not None and (not math.isfinite(humidity_val) or humidity_val < 0 or humidity_val > 100):
            flash('Humidity must be a percentage between 0 and 100.', 'danger')
            return render_template('animals/log_env.html', animal=animal)

        media_path, media_type = save_media(request.files.get('media'))

        log = EnvironmentalLog(
            animal_id=animal.id,
            logged_by_id=current_user.id,
            temperature_f=_to_float(request.form.get('temperature_f')),
            humidity_pct=humidity_val,
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


@animals.route('/<int:animal_id>/toggle-privacy', methods=['POST'])
@login_required
def toggle_profile_privacy(animal_id):
    """Owner-only: block/unblock a previous owner/creator from viewing this profile at all."""
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can change this.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    animal.profile_private = not animal.profile_private
    db.session.commit()
    flash(f"{animal.name}'s profile is now "
          f"{'private' if animal.profile_private else 'visible to previous owners'}.", 'success')
    return redirect(url_for('animals.profile', animal_id=animal.id))


@animals.route('/<int:animal_id>/medical')
@login_required
def medical(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if not can_view_animal(animal):
        flash('You do not have access to this pet.', 'danger')
        return redirect(url_for('main.dashboard'))

    is_owner = animal.owner_id == current_user.id
    if animal.profile_private and not is_owner:
        return render_template('animals/private.html', animal=animal)

    records = MedicalRecord.query.filter_by(animal_id=animal.id) \
        .order_by(MedicalRecord.record_date.desc(), MedicalRecord.created_at.desc()).all()

    # track the MOST RECENTLY GIVEN vaccination — a fresh dose resets the cycle,
    # even if an older, superseded vaccination is still technically "sooner due"
    vaccine_due = None
    vaccinations = [r for r in records if r.next_due_date]
    if vaccinations:
        latest = max(vaccinations, key=lambda r: (r.record_date, r.created_at))
        days_remaining = (latest.next_due_date - datetime.utcnow().date()).days
        elapsed_pct = (VACCINATION_INTERVAL_DAYS - days_remaining) / VACCINATION_INTERVAL_DAYS * 100
        vaccine_due = {
            'record': latest,
            'due_date': latest.next_due_date,
            'days_remaining': days_remaining,
            'state': 'overdue' if days_remaining < 0 else
                     ('soon' if days_remaining <= 7 else 'ok'),
            'progress_pct': max(4, min(100, round(elapsed_pct))),
        }

    return render_template('animals/medical.html', animal=animal, records=records,
                           is_owner=is_owner, today=datetime.utcnow().date().isoformat(),
                           vaccine_due=vaccine_due)


@animals.route('/<int:animal_id>/medical/add', methods=['POST'])
@login_required
def add_medical(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can add medical records.', 'danger')
        return redirect(url_for('animals.medical', animal_id=animal.id))

    title = request.form.get('title', '').strip()
    if not title:
        flash('Please give the medical record a title.', 'danger')
        return redirect(url_for('animals.medical', animal_id=animal.id))

    record_date = datetime.utcnow().date()
    rd = request.form.get('record_date', '').strip()
    if rd:
        try:
            record_date = datetime.strptime(rd, '%Y-%m-%d').date()
        except ValueError:
            pass

    # a vaccination automatically gets a next-due reminder one year out —
    # no extra form field, just detected from the title
    next_due = None
    if 'vaccin' in title.lower():
        next_due = record_date + timedelta(days=VACCINATION_INTERVAL_DAYS)

    record = MedicalRecord(
        animal_id=animal.id,
        logged_by_id=current_user.id,
        record_date=record_date,
        title=title,
        notes=request.form.get('notes', '').strip() or None,
        treatment=request.form.get('treatment', '').strip() or None,
        vet_name=request.form.get('vet_name', '').strip() or None,
        next_due_date=next_due,
    )
    db.session.add(record)
    db.session.commit()

    flash(f"Medical record added for {animal.name}.", 'success')
    return redirect(url_for('animals.medical', animal_id=animal.id))


@animals.route('/<int:animal_id>/medical/<int:record_id>/delete', methods=['POST'])
@login_required
def delete_medical(animal_id, record_id):
    animal = Animal.query.get_or_404(animal_id)
    record = MedicalRecord.query.get_or_404(record_id)
    if animal.owner_id != current_user.id or record.animal_id != animal.id:
        flash('You cannot delete this record.', 'danger')
        return redirect(url_for('animals.medical', animal_id=animal.id))

    db.session.delete(record)
    db.session.commit()
    flash('Medical record deleted.', 'success')
    return redirect(url_for('animals.medical', animal_id=animal.id))


def _ensure_passport_token(animal):
    """Lazily assign a token so old pets get one on first passport view."""
    if not animal.passport_token:
        animal.passport_token = uuid.uuid4().hex[:16]
        db.session.commit()
    return animal.passport_token


@animals.route('/<int:animal_id>/passport')
@login_required
def passport(animal_id):
    """Owner view — shows the QR card, printable, with a copyable public URL."""
    animal = Animal.query.get_or_404(animal_id)
    if not can_view_animal(animal):
        flash('You do not have access to this pet.', 'danger')
        return redirect(url_for('main.dashboard'))

    token = _ensure_passport_token(animal)
    public_url = url_for('animals.passport_public', token=token, _external=True)
    return render_template('animals/passport.html', animal=animal, public_url=public_url)


@animals.route('/<int:animal_id>/passport/qr.png')
@login_required
def passport_qr(animal_id):
    """Owner-only PNG of the QR code, generated on demand from the public URL."""
    animal = Animal.query.get_or_404(animal_id)
    if not can_view_animal(animal):
        abort(403)
    token = _ensure_passport_token(animal)
    public_url = url_for('animals.passport_public', token=token, _external=True)

    img = qrcode.make(public_url, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    buf.seek(0)
    return send_file(buf, mimetype='image/png')


@animals.route('/passport/<token>')
def passport_public(token):
    """PUBLIC — no login. Scanned from the QR code by a vet or finder."""
    animal = Animal.query.filter_by(passport_token=token).first()
    if not animal:
        abort(404)
    return render_template('animals/passport_public.html', animal=animal)
