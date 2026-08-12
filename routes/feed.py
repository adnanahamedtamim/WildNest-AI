from flask import (Blueprint, render_template, redirect, url_for,
                   flash, request)
from flask_login import login_required, current_user
from extensions import db
from models import Animal, RehomeListing
from charts import build_env_charts
from wildsight_ai import match_pets, is_configured
from datetime import datetime

feed = Blueprint('feed', __name__)


@feed.route('/')
@login_required
def browse():
    species = request.args.get('species', '').strip()
    scope = request.args.get('scope', 'others')  # 'others' (default) or 'mine'

    query = Animal.query.join(RehomeListing).filter(RehomeListing.status == 'active')

    if scope == 'mine':
        query = query.filter(Animal.owner_id == current_user.id)
    else:  # default: hide the user's own pets so they can't match themselves
        query = query.filter(Animal.owner_id != current_user.id)

    if species:
        query = query.filter(Animal.species.ilike(f'%{species}%'))
    listings = query.order_by(RehomeListing.created_at.desc()).all()

    # species dropdown reflects only what's visible in the current scope
    scope_filter = ((Animal.owner_id == current_user.id) if scope == 'mine'
                    else (Animal.owner_id != current_user.id))
    all_species = sorted({a.species for a in
                          Animal.query.join(RehomeListing)
                          .filter(RehomeListing.status == 'active', scope_filter).all()})

    # count of the user's own active listings (for the toggle label)
    my_count = Animal.query.join(RehomeListing).filter(
        RehomeListing.status == 'active',
        Animal.owner_id == current_user.id).count()

    return render_template('feed/browse.html',
                           listings=listings,
                           all_species=all_species,
                           active_species=species,
                           scope=scope,
                           my_count=my_count)


@feed.route('/match', methods=['GET', 'POST'])
@login_required
def match():
    # pets available to this adopter = active listings that aren't their own
    available = Animal.query.join(RehomeListing).filter(
        RehomeListing.status == 'active',
        Animal.owner_id != current_user.id
    ).all()

    if request.method == 'POST':
        # assemble the adopter's requirements into a readable brief for the AI
        parts = []
        species = request.form.get('species', '').strip()
        parts.append(f"Preferred species: {species}" if species else "Preferred species: open to any")
        parts.append(f"Experience level: {request.form.get('experience', 'not specified')}")
        parts.append(f"Space available: {request.form.get('space', 'not specified')}")
        parts.append(f"Climate they can maintain: {request.form.get('climate', 'not specified')}")
        parts.append(f"Daily time available: {request.form.get('time', 'not specified')}")
        parts.append(f"Home location: {request.form.get('location', 'not specified')}")
        notes = request.form.get('notes', '').strip()
        if notes:
            parts.append(f"Additional notes: {notes}")
        requirements_text = '\n'.join(parts)

        if not is_configured():
            flash('WildNest AI is not connected — add your GEMINI_API_KEY to enable matching.', 'warning')
            return redirect(url_for('feed.match'))

        results = match_pets(requirements_text, available)
        if results is None:
            flash('WildNest AI could not complete the match right now. Please try again.', 'danger')
            return redirect(url_for('feed.match'))

        return render_template('feed/match_results.html',
                               results=results,
                               requirements=parts)

    all_species = sorted({a.species for a in available})
    return render_template('feed/match_form.html',
                           all_species=all_species,
                           default_location=(current_user.organization or ''),
                           available_count=len(available),
                           ai_ready=is_configured())


@feed.route('/pet/<int:animal_id>')
@login_required
def detail(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    listing = animal.active_listing
    if not listing:
        flash('This pet is not currently listed for rehoming.', 'warning')
        return redirect(url_for('feed.browse'))

    is_owner = animal.owner_id == current_user.id

    logs = animal.env_logs
    charts = build_env_charts(logs)
    recent_logs = list(reversed(logs))[:12]
    medical_records = sorted(animal.medical_records,
                             key=lambda r: r.record_date, reverse=True)

    return render_template('feed/detail.html',
                           animal=animal,
                           listing=listing,
                           is_owner=is_owner,
                           charts=charts,
                           recent_logs=recent_logs,
                           log_count=len(logs),
                           medical_records=medical_records)


@feed.route('/list/<int:animal_id>', methods=['GET', 'POST'])
@login_required
def create_listing(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can list this pet.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    if request.method == 'POST':
        reason = request.form.get('reason', '').strip()

        listing = animal.active_listing
        if listing:  # update the existing active listing
            listing.reason = reason or None
        else:
            listing = RehomeListing(
                animal_id=animal.id,
                posted_by_id=current_user.id,
                reason=reason or None,
                status='active',
            )
            db.session.add(listing)

        animal.status = 'listed'
        db.session.commit()

        flash(f'{animal.name} is now listed for rehoming.', 'success')
        return redirect(url_for('feed.detail', animal_id=animal.id))

    return render_template('feed/list_form.html', animal=animal,
                           listing=animal.active_listing)


@feed.route('/unlist/<int:animal_id>', methods=['POST'])
@login_required
def unlist(animal_id):
    animal = Animal.query.get_or_404(animal_id)
    if animal.owner_id != current_user.id:
        flash('Only the current owner can remove this listing.', 'danger')
        return redirect(url_for('animals.profile', animal_id=animal.id))

    listing = animal.active_listing
    if listing:
        listing.status = 'closed'
    animal.status = 'in_care'
    db.session.commit()

    flash(f'{animal.name} has been removed from the rehoming feed.', 'success')
    return redirect(url_for('animals.profile', animal_id=animal.id))
