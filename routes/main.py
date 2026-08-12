from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from extensions import db
from models import Animal, Notification, MedicalRecord
from media import save_photo
from wildsight_ai import generate_transition_notification
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload
from collections import defaultdict
from datetime import datetime
import time

main = Blueprint('main', __name__)


def _ensure_vaccination_alerts(animals):
    """One-time, non-AI alerts when a vaccination's auto-computed due date crosses
    the 'due soon' (7 days out) or 'overdue' threshold. Each fires exactly once
    per record, tracked via the due_soon_alert_sent / overdue_alert_sent flags.
    Only the MOST RECENTLY GIVEN vaccination is checked — logging a fresh dose
    resets the cycle, so an older superseded record should stop alerting."""
    today = datetime.utcnow().date()
    owned_ids = [a.id for a in animals if a.owner_id == current_user.id]
    if not owned_ids:
        return

    # one query for every owned animal's vaccination records instead of one per animal
    all_records = MedicalRecord.query.filter(
        MedicalRecord.animal_id.in_(owned_ids),
        MedicalRecord.next_due_date.isnot(None),
    ).all()
    records_by_animal = defaultdict(list)
    for r in all_records:
        records_by_animal[r.animal_id].append(r)

    for animal in animals:
        if animal.owner_id != current_user.id:
            continue
        records = records_by_animal.get(animal.id)
        if not records:
            continue
        record = max(records, key=lambda r: (r.record_date, r.created_at))

        days_remaining = (record.next_due_date - today).days

        if days_remaining < 0 and not record.overdue_alert_sent:
            db.session.add(Notification(
                user_id=current_user.id, animal_id=animal.id, day_number=0,
                category='vaccination', is_emergency=True,
                title=f"🚨 {animal.name}'s vaccination is overdue",
                body=(f"{record.title} was due on {record.next_due_date.strftime('%B %d, %Y')} "
                      f"— overdue by {-days_remaining} day{'s' if -days_remaining != 1 else ''}. "
                      f"Please schedule a vet visit soon."),
            ))
            record.overdue_alert_sent = True

        elif 0 <= days_remaining <= 7 and not record.due_soon_alert_sent:
            db.session.add(Notification(
                user_id=current_user.id, animal_id=animal.id, day_number=0,
                category='vaccination', is_emergency=False,
                title=f"⏰ {animal.name}'s vaccination due in {days_remaining} day{'s' if days_remaining != 1 else ''}",
                body=(f"{record.title} is due on {record.next_due_date.strftime('%B %d, %Y')}. "
                      f"Consider booking a vet appointment soon."),
            ))
            record.due_soon_alert_sent = True
    db.session.commit()


def _ensure_todays_transition_notifications(animals):
    """Lazily generate today's 'from the pet' notification for any animal
    currently in its 30-day transition window, owned by the current user.

    Two small resilience touches so multiple pets don't lose notifications:
    1. Commit each notification IMMEDIATELY so a later failure never rolls
       back the successful ones already generated in this pass.
    2. Add a short 1.2s pause between successive AI calls so the free-tier
       per-minute rate limiter doesn't quietly drop the second/third pet.
       (Any pet skipped due to a genuine failure will simply be retried on
       the next dashboard load — the exists-check makes this idempotent.)"""
    candidates = []  # (animal, day_number) pairs still in their 30-day window
    for animal in animals:
        if animal.owner_id != current_user.id or not animal.handover_date:
            continue
        days_since = (datetime.utcnow() - animal.handover_date).days
        day_number = days_since + 1
        if day_number < 1 or day_number > 30:
            continue
        candidates.append((animal, day_number))

    if not candidates:
        return

    # one query for every candidate's existing notification instead of one per animal
    candidate_animal_ids = [a.id for a, _ in candidates]
    existing = Notification.query.filter(
        Notification.user_id == current_user.id,
        Notification.animal_id.in_(candidate_animal_ids),
        Notification.category == 'transition',
    ).all()
    existing_pairs = {(n.animal_id, n.day_number) for n in existing}

    calls_this_pass = 0
    for animal, day_number in candidates:
        if (animal.id, day_number) in existing_pairs:
            continue

        if calls_this_pass > 0:
            time.sleep(1.2)  # stay under the per-minute rate limit

        result = generate_transition_notification(animal, day_number)
        calls_this_pass += 1
        if not result:
            continue  # will be retried on the next dashboard visit
        title, body = result
        db.session.add(Notification(
            user_id=current_user.id, animal_id=animal.id,
            day_number=day_number, title=title, body=body,
        ))
        try:
            db.session.commit()  # persist immediately, don't wait for the whole loop
        except IntegrityError:
            # another concurrent request already created today's note for this
            # pet (unique index on user_id+animal_id+day_number) — not an error
            db.session.rollback()


def _user_stats(user):
    """Compute animal counts for a user's profile."""
    animals = Animal.query.filter(
        (Animal.owner_id == user.id) |
        (Animal.created_by_id == user.id)
    ).all()
    flagged = Notification.query.filter_by(
        user_id=user.id, is_read=False, is_emergency=True
    ).count()
    return {
        'total': len(animals),
        'in_care': sum(1 for a in animals if a.status == 'in_care'),
        'rehoming': sum(1 for a in animals if a.status in ('listed', 'pending_adoption')),
        'adopted': sum(1 for a in animals if a.status in ('adopted', 'settled')),
        'rescued': sum(1 for a in animals if a.origin == 'rescue'),
        'personal': sum(1 for a in animals if a.origin == 'personal'),
        'flagged': flagged,
    }


@main.route('/home')
@login_required
def dashboard():
    # every animal the user owns OR originally created (read access after handover) —
    # except pets the creator has chosen to hide from their own dashboard, which
    # never affects the current owner's visibility of their own animal
    animals = Animal.query.filter(
        (Animal.owner_id == current_user.id) |
        ((Animal.created_by_id == current_user.id) &
         (Animal.creator_dashboard_hidden == False))
    ).options(
        # one extra query for every animal's env_logs instead of one per animal
        # when the card loop below reads animal.env_logs
        selectinload(Animal.env_logs)
    ).order_by(Animal.created_at.desc()).all()

    _ensure_todays_transition_notifications(animals)
    _ensure_vaccination_alerts(animals)

    cards = []
    for animal in animals:
        days_since = None
        if animal.handover_date:
            days_since = (datetime.utcnow() - animal.handover_date).days

        # env_logs is ordered oldest -> newest, so the last item is the most recent
        logs = animal.env_logs
        latest_env_log = logs[-1] if logs else None

        cards.append({
            'animal': animal,
            'days_since_handover': days_since,
            'latest_env_log': latest_env_log,
            'in_monitoring': days_since is not None and days_since <= 30,
            'is_owner': animal.owner_id == current_user.id,
            'is_creator_only': (animal.created_by_id == current_user.id
                                and animal.owner_id != current_user.id),
        })

    return render_template('dashboard.html', cards=cards)


@main.route('/profile')
@login_required
def account():
    stats = _user_stats(current_user)
    return render_template('account.html', stats=stats, user=current_user)


@main.route('/profile/photo', methods=['POST'])
@login_required
def update_photo():
    fname = save_photo(request.files.get('photo'))
    if not fname:
        flash('Please choose a valid image file (PNG, JPG, GIF, WEBP).', 'danger')
        return redirect(url_for('main.account'))

    current_user.photo_path = fname
    db.session.commit()
    flash('Your profile photo has been updated.', 'success')
    return redirect(url_for('main.account'))


@main.route('/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    note = Notification.query.get_or_404(notification_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    note.is_read = True
    db.session.commit()
    return jsonify({'ok': True})


@main.route('/notifications/read-all', methods=['POST'])
@login_required
def mark_all_notifications_read():
    Notification.query.filter_by(user_id=current_user.id, is_read=False).update({'is_read': True})
    db.session.commit()
    return jsonify({'ok': True})


@main.route('/notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_notification(notification_id):
    note = Notification.query.get_or_404(notification_id)
    if note.user_id != current_user.id:
        return jsonify({'error': 'forbidden'}), 403
    db.session.delete(note)
    db.session.commit()
    return jsonify({'ok': True})
