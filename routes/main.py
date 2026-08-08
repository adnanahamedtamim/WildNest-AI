from flask import Blueprint, render_template
from flask_login import login_required, current_user
from models import Animal, DailyMetric
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

        latest_metric = DailyMetric.query.filter_by(
            animal_id=animal.id
        ).order_by(DailyMetric.date.desc()).first()

        cards.append({
            'animal': animal,
            'days_since_handover': days_since,
            'latest_metric': latest_metric,
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
