from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from extensions import db
from models import Animal, DailyMetric
from media import save_photo
from datetime import datetime

main = Blueprint('main', __name__)


def _user_stats(user):
    """Compute animal counts for a user's profile."""
    animals = Animal.query.filter(
        (Animal.owner_id == user.id) |
        (Animal.created_by_id == user.id)
    ).all()
    animal_ids = [a.id for a in animals]
    flagged = 0
    if animal_ids:
        flagged = DailyMetric.query.filter(
            DailyMetric.animal_id.in_(animal_ids),
            DailyMetric.flagged == True
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
    # every animal the user owns OR originally created (read access after handover)
    animals = Animal.query.filter(
        (Animal.owner_id == current_user.id) |
        (Animal.created_by_id == current_user.id)
    ).order_by(Animal.created_at.desc()).all()

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
