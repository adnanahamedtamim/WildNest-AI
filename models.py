from extensions import db, login_manager
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import uuid


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


class User(UserMixin, db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'staff' or 'adopter'
    organization = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # animals this user currently owns
    animals_owned = db.relationship(
        'Animal', foreign_keys='Animal.owner_id',
        backref='owner', lazy=True
    )
    # animals this user originally created
    animals_created = db.relationship(
        'Animal', foreign_keys='Animal.created_by_id',
        backref='creator', lazy=True
    )

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.email}>'


class Animal(db.Model):
    __tablename__ = 'animals'
    id = db.Column(db.Integer, primary_key=True)

    # ownership
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    # identity
    name = db.Column(db.String(100), nullable=False)
    species = db.Column(db.String(100), nullable=False)
    common_name = db.Column(db.String(100))
    age_years = db.Column(db.Float)
    sex = db.Column(db.String(10))
    origin = db.Column(db.String(20), default='rescue')  # 'rescue' or 'personal'

    # rescue details
    rescue_date = db.Column(db.Date)
    rescue_location = db.Column(db.String(200))
    rescue_reason = db.Column(db.Text)

    # care profile
    medical_history = db.Column(db.Text)
    stress_triggers = db.Column(db.Text)
    dietary_requirements = db.Column(db.Text)
    photo_path = db.Column(db.String(200))

    # lifecycle
    status = db.Column(db.String(20), default='in_care')
    # in_care -> listed -> pending_adoption -> adopted -> settled
    handover_date = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # relationships
    env_logs = db.relationship(
        'EnvironmentalLog', backref='animal', lazy=True,
        cascade='all, delete-orphan', order_by='EnvironmentalLog.timestamp'
    )
    daily_metrics = db.relationship(
        'DailyMetric', backref='animal', lazy=True,
        cascade='all, delete-orphan', order_by='DailyMetric.date'
    )
    listings = db.relationship(
        'RehomeListing', backref='animal', lazy=True,
        cascade='all, delete-orphan'
    )
    handovers = db.relationship(
        'HandoverRecord', backref='animal', lazy=True,
        cascade='all, delete-orphan'
    )
    ai_analyses = db.relationship(
        'WildSightAnalysis', backref='animal', lazy=True,
        cascade='all, delete-orphan', order_by='WildSightAnalysis.created_at.desc()'
    )

    @property
    def days_since_handover(self):
        if self.handover_date:
            return (datetime.utcnow() - self.handover_date).days
        return None

    @property
    def active_listing(self):
        for listing in self.listings:
            if listing.status == 'active':
                return listing
        return None

    def __repr__(self):
        return f'<Animal {self.name} ({self.species})>'


class EnvironmentalLog(db.Model):
    __tablename__ = 'environmental_logs'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    logged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    temperature_f = db.Column(db.Float)
    humidity_pct = db.Column(db.Float)
    lighting_hours = db.Column(db.Float)
    feeding_amount_g = db.Column(db.Float)
    weight_g = db.Column(db.Float)
    stress_level = db.Column(db.Integer)      # 1-5
    activity_level = db.Column(db.Integer)    # 1-5
    notes = db.Column(db.Text)
    media_path = db.Column(db.String(200))    # optional photo/video of behaviour
    media_type = db.Column(db.String(10))     # 'image' or 'video'


class DailyMetric(db.Model):
    __tablename__ = 'daily_metrics'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    logged_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    date = db.Column(db.Date, default=lambda: datetime.utcnow().date())
    feeding_habit = db.Column(db.Integer)     # 1-5
    sleep_quality = db.Column(db.Integer)     # 1-5
    aggression_level = db.Column(db.Integer)  # 1-5
    activity_level = db.Column(db.Integer)    # 1-5
    notes = db.Column(db.Text)
    photo_path = db.Column(db.String(200))
    flagged = db.Column(db.Boolean, default=False)
    ai_analysis = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class RehomeListing(db.Model):
    __tablename__ = 'rehome_listings'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    posted_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reason = db.Column(db.Text)
    adoption_fee = db.Column(db.Float)
    status = db.Column(db.String(20), default='active')  # active / closed
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    posted_by = db.relationship('User', foreign_keys=[posted_by_id])
    requests = db.relationship(
        'AdoptionRequest', backref='listing', lazy=True,
        cascade='all, delete-orphan'
    )


class AdoptionRequest(db.Model):
    __tablename__ = 'adoption_requests'
    id = db.Column(db.Integer, primary_key=True)
    listing_id = db.Column(db.Integer, db.ForeignKey('rehome_listings.id'), nullable=False)
    requester_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    message = db.Column(db.Text)
    enclosure_setup = db.Column(db.Text)      # JSON string of setup answers
    match_score = db.Column(db.Integer)       # 0-100
    status = db.Column(db.String(20), default='pending')  # pending / approved / rejected
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    requester = db.relationship('User', foreign_keys=[requester_id])


class HandoverRecord(db.Model):
    __tablename__ = 'handover_records'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    from_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    to_user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    request_id = db.Column(db.Integer, db.ForeignKey('adoption_requests.id'), nullable=True)
    handover_date = db.Column(db.DateTime, default=datetime.utcnow)
    certificate_id = db.Column(db.String(40), default=lambda: str(uuid.uuid4())[:8].upper())

    from_user = db.relationship('User', foreign_keys=[from_user_id])
    to_user = db.relationship('User', foreign_keys=[to_user_id])


class WildSightAnalysis(db.Model):
    __tablename__ = 'wildsight_analyses'
    id = db.Column(db.Integer, primary_key=True)
    animal_id = db.Column(db.Integer, db.ForeignKey('animals.id'), nullable=False)
    requested_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    photo_path = db.Column(db.String(200))
    ai_response = db.Column(db.Text)
    severity = db.Column(db.String(20))  # normal / watch / contact_staff / emergency
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
