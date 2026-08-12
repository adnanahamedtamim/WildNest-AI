"""
WildNest demo-data seeder.

Run:   python seed_demo.py     (or: venv\\Scripts\\python.exe seed_demo.py)

Creates realistic, lived-in demo accounts + pets so the app looks fully populated
for judging: weeks of environmental logs with behaviour notes (real trend lines),
medical records, a completed handover with transition notifications, and rehoming
listings — two of them with real cat/dog photos.

Fully idempotent and SAFE: each of the 4 demo pets (Rex, Milo, Luna, Kilo) is only
ever CREATED if a pet with that name doesn't already exist under its demo owner.
If it already exists, this script does not touch it AT ALL — no reset, no update —
so anything you've done to it (handovers, deletions, edits) is fully preserved.
To truly reset one pet, delete it yourself in the app first, then re-run this.
It NEVER touches your own real accounts/pets.
"""
import random
import uuid
from datetime import datetime, timedelta

from app import create_app
from extensions import db
from models import (User, Animal, EnvironmentalLog, MedicalRecord,
                    RehomeListing, HandoverRecord, Notification)
from sqlalchemy import or_

random.seed(42)  # reproducible data every run

DEMO_DOMAIN = '@wildnest.demo'
DEMO_PASSWORD = 'demo1234'
NOW = datetime.utcnow()

# real photos already sitting in static/uploads (from earlier testing)
CAT_IMG = '58e920da4baa4bbf9d77f1f0c0fa433f.jpg'   # tabby kitten
DOG_IMG = '70c43d631aa94fcbb41fb840721e9636.jpg'   # golden retriever puppy

# ---- behaviour note pools (per species) ------------------------------------
NOTES_IGUANA = [
    'Basked under the lamp all morning.', 'Ate his greens eagerly today.',
    'Active and exploring the enclosure.', 'Soaked in the water dish for a while.',
    'A little sluggish, stayed in the warm corner.', 'Bright, alert, good colour.',
    'Shed a little skin — looking healthy.',
]
NOTES_TORTOISE_BASELINE = [
    'Grazed on hay for most of the morning.', 'Basked for long hours, very content.',
    'Active — did a full lap of the enclosure.', 'Steady appetite, ate well.',
    'Soaked in the shallow dish, relaxed.',
]
NOTES_TORTOISE_SETTLING = [
    'Hid in her shell most of the day — still settling in.',
    'Ventured out to bask today — good progress!',
    'Ate a little hay, but cautious.', 'Stayed near the warm corner, watchful.',
    'Slowly getting used to the new enclosure.',
]
NOTES_CAT = [
    'Chased her toys around the living room.', 'Napped in the sunny window all afternoon.',
    'Purred through dinner, ate well.', 'A bit shy — hid under the bed for a while.',
    'Very affectionate today, lots of cuddles.', 'Groomed and lounged all day.',
    'Watched the birds at the window intently.',
]
NOTES_DOG = [
    'Energetic on the morning walk.', 'Ate everything, tail wagging.',
    'Napped after a big play session in the yard.', 'Learned a new trick today!',
    'Friendly with visitors — so many tail wags.', 'A little restless in the evening.',
    'Played fetch happily for ages.',
]


def token():
    return uuid.uuid4().hex[:16]


def make_user(name, email, organization=None):
    """Get-or-create: reuses the account (and anything you've built on it) if it
    already exists, since demo accounts are never deleted between runs."""
    existing = User.query.filter_by(email=email).first()
    if existing:
        return existing
    u = User(name=name, email=email, role='member', organization=organization,
             created_at=NOW - timedelta(days=90))
    u.set_password(DEMO_PASSWORD)
    db.session.add(u)
    db.session.flush()
    return u


def gen_logs(animal, logged_by, start_days_ago, end_days_ago, base,
             drift=None, notes_pool=None, note_prob=0.6):
    """Create one env log per day between the two offsets, with behaviour notes.
    base: {field: (center_value, noise)}; drift adds a per-day linear change.
    Fields omitted from `base` are left blank (e.g. cats/dogs have no enclosure temp)."""
    drift = drift or {}
    day = start_days_ago
    while day >= end_days_ago:
        ts = NOW - timedelta(days=day, hours=random.randint(0, 4))
        elapsed = start_days_ago - day
        vals = {}
        for field, (center, noise) in base.items():
            vals[field] = center + random.uniform(-noise, noise) + drift.get(field, 0) * elapsed
        note = None
        if notes_pool and random.random() < note_prob:
            note = random.choice(notes_pool)
        log = EnvironmentalLog(
            animal_id=animal.id, logged_by_id=logged_by.id, timestamp=ts,
            temperature_f=round(vals['temperature_f'], 1) if 'temperature_f' in vals else None,
            humidity_pct=round(vals['humidity_pct'], 1) if 'humidity_pct' in vals else None,
            lighting_hours=round(vals['lighting_hours'], 1) if 'lighting_hours' in vals else None,
            feeding_amount_g=round(vals['feeding_amount_g'], 1) if 'feeding_amount_g' in vals else None,
            weight_g=round(vals['weight_g'], 1) if 'weight_g' in vals else None,
            stress_level=int(round(min(5, max(1, vals.get('stress_level', 2))))),
            activity_level=int(round(min(5, max(1, vals.get('activity_level', 3))))),
            notes=note,
        )
        db.session.add(log)
        day -= 1


def existing(name, demo_user_ids):
    """Look up a previously-seeded pet by name, connected to ANY demo account
    (as current owner OR original creator) — deliberately NOT scoped to one
    specific owner, because ownership legitimately changes via handover, and
    we still need to recognize 'this is the same pet' after that happens."""
    return Animal.query.filter(
        Animal.name == name,
        or_(Animal.owner_id.in_(demo_user_ids), Animal.created_by_id.in_(demo_user_ids)),
    ).first()


def seed():
    print('Seeding WildNest demo data...')

    # --- users (get-or-create, never deleted) ---------------------------------
    center = make_user('Green Valley Wildlife Center', f'center{DEMO_DOMAIN}',
                       organization='Green Valley Wildlife Center')
    maya = make_user('Maya Chen', f'maya{DEMO_DOMAIN}')
    rob = make_user('Rob Alvarez', f'rob{DEMO_DOMAIN}')
    db.session.commit()
    demo_user_ids = [center.id, maya.id, rob.id]
    print('  demo users ready (created if missing, reused if not)')

    # --- Rex — Green Iguana, at the center, LISTED for rehoming ---------------
    if existing('Rex', demo_user_ids):
        print('  Rex already exists — left untouched')
    else:
        rex = Animal(
            owner_id=center.id, created_by_id=center.id,
            name='Rex', species='Iguana iguana', common_name='Green Iguana',
            age_years=4, sex='Male', origin='rescue',
            rescue_date=(NOW - timedelta(days=120)).date(),
            rescue_location='Riverside, California',
            rescue_reason='Surrendered by an owner who could no longer meet his heat and space needs.',
            current_location='San Diego, California',
            stress_triggers='Loud noise, temperatures below 80°F, sudden handling.',
            dietary_requirements='Leafy greens daily (collard, mustard); calcium supplement twice weekly.',
            status='listed', passport_token=token(), created_at=NOW - timedelta(days=120),
        )
        db.session.add(rex)
        db.session.flush()
        gen_logs(rex, center, 45, 0, {
            'temperature_f': (93, 2.5), 'humidity_pct': (68, 6), 'lighting_hours': (12, 0.5),
            'feeding_amount_g': (55, 8), 'weight_g': (2500, 30), 'stress_level': (2, 0.6),
            'activity_level': (3.5, 0.8),
        }, drift={'weight_g': 4}, notes_pool=NOTES_IGUANA)
        db.session.add(MedicalRecord(
            animal_id=rex.id, logged_by_id=center.id,
            record_date=(NOW - timedelta(days=110)).date(),
            title='Intake exam & deworming', vet_name='Dr. Patel, Green Valley',
            treatment='Fenbendazole course', notes='Mild dehydration on arrival, resolved within a week.'))
        db.session.add(MedicalRecord(
            animal_id=rex.id, logged_by_id=center.id,
            record_date=(NOW - timedelta(days=30)).date(),
            title='Routine check-up', vet_name='Dr. Patel, Green Valley',
            treatment='None needed', notes='Healthy weight gain, good colour, alert.'))
        db.session.add(RehomeListing(
            animal_id=rex.id, posted_by_id=center.id, status='active',
            created_at=NOW - timedelta(days=6),
            reason='Rex is thriving and ready for an experienced keeper who can give him a '
                   'large, warm enclosure. We are looking for a calm, patient forever home.'))
        db.session.commit()
        print('  created Rex')

    # --- Milo — Golden Retriever, at the center, LISTED (with photo) ----------
    if existing('Milo', demo_user_ids):
        print('  Milo already exists — left untouched')
    else:
        milo = Animal(
            owner_id=center.id, created_by_id=center.id,
            name='Milo', species='Canis familiaris', common_name='Golden Retriever',
            age_years=1, sex='Male', origin='rescue',
            rescue_date=(NOW - timedelta(days=70)).date(),
            rescue_location='Green Valley Wildlife Center',
            rescue_reason='Found as a stray puppy; fully vaccinated and socialised, ready for a family.',
            current_location='San Diego, California',
            stress_triggers='Being left alone for long periods, thunderstorms.',
            dietary_requirements='Large-breed puppy kibble, 3 meals/day; no chocolate or grapes.',
            status='listed', photo_path=DOG_IMG, passport_token=token(),
            created_at=NOW - timedelta(days=70),
        )
        db.session.add(milo)
        db.session.flush()
        gen_logs(milo, center, 35, 0, {
            'feeding_amount_g': (300, 25), 'weight_g': (15000, 200), 'stress_level': (2, 0.7),
            'activity_level': (4.5, 0.6),
        }, drift={'weight_g': 90}, notes_pool=NOTES_DOG)
        db.session.add(MedicalRecord(
            animal_id=milo.id, logged_by_id=center.id,
            record_date=(NOW - timedelta(days=65)).date(),
            title='Vaccinations & microchip', vet_name='Dr. Okafor, Green Valley',
            treatment='DHPP + rabies, microchipped', notes='Healthy, energetic puppy. Cleared for adoption.'))
        db.session.add(RehomeListing(
            animal_id=milo.id, posted_by_id=center.id, status='active',
            created_at=NOW - timedelta(days=3),
            reason='Milo is a playful, gentle golden retriever puppy looking for an active family '
                   'with a yard and time for training and companionship.'))
        db.session.commit()
        print('  created Milo')

    # --- Luna — Tabby Cat, Maya's personal pet (with photo) -------------------
    if existing('Luna', demo_user_ids):
        print('  Luna already exists — left untouched')
    else:
        luna = Animal(
            owner_id=maya.id, created_by_id=maya.id,
            name='Luna', species='Felis catus', common_name='Tabby Cat',
            age_years=2, sex='Female', origin='personal',
            current_location='Austin, Texas',
            stress_triggers='Loud vacuum, unfamiliar dogs, changes to her feeding routine.',
            dietary_requirements='Grain-free wet food twice daily; fresh water; occasional treats.',
            status='in_care', photo_path=CAT_IMG, passport_token=token(),
            created_at=NOW - timedelta(days=80),
        )
        db.session.add(luna)
        db.session.flush()
        gen_logs(luna, maya, 30, 0, {
            'feeding_amount_g': (120, 15), 'weight_g': (4200, 60), 'stress_level': (2, 0.6),
            'activity_level': (4, 0.8),
        }, notes_pool=NOTES_CAT)
        db.session.add(MedicalRecord(
            animal_id=luna.id, logged_by_id=maya.id,
            record_date=(NOW - timedelta(days=25)).date(),
            title='Annual wellness & vaccines', vet_name='Austin Cat Clinic',
            treatment='FVRCP booster', notes='Healthy weight, glossy coat, teeth clean.'))
        db.session.commit()
        print('  created Luna')

    # --- Kilo — Sulcata Tortoise, HANDED OVER to Maya 4 days ago (star demo) --
    if existing('Kilo', demo_user_ids):
        print('  Kilo already exists — left untouched')
    else:
        kilo = Animal(
            owner_id=maya.id, created_by_id=center.id,
            name='Kilo', species='Centrochelys sulcata', common_name='Sulcata Tortoise',
            age_years=6, sex='Female', origin='rescue',
            rescue_date=(NOW - timedelta(days=200)).date(),
            rescue_location='Green Valley Wildlife Center',
            rescue_reason='Rescued from an undersized enclosure; rehabilitated over 6 months.',
            current_location='Austin, Texas',
            stress_triggers='Cold drafts, damp substrate, being lifted from above.',
            dietary_requirements='High-fibre grasses and hay; occasional leafy greens; no fruit.',
            status='adopted', handover_date=NOW - timedelta(days=4),
            passport_token=token(), created_at=NOW - timedelta(days=200),
        )
        db.session.add(kilo)
        db.session.flush()
        gen_logs(kilo, center, 44, 5, {
            'temperature_f': (95, 2), 'humidity_pct': (55, 5), 'lighting_hours': (13, 0.4),
            'feeding_amount_g': (60, 7), 'weight_g': (8200, 40), 'stress_level': (1.5, 0.5),
            'activity_level': (4, 0.7),
        }, drift={'weight_g': 6}, notes_pool=NOTES_TORTOISE_BASELINE)
        gen_logs(kilo, maya, 4, 0, {
            'temperature_f': (90, 2), 'humidity_pct': (48, 5), 'lighting_hours': (12, 0.5),
            'feeding_amount_g': (45, 8), 'weight_g': (8420, 30), 'stress_level': (3, 0.6),
            'activity_level': (3, 0.8),
        }, notes_pool=NOTES_TORTOISE_SETTLING, note_prob=0.9)
        db.session.add(MedicalRecord(
            animal_id=kilo.id, logged_by_id=center.id,
            record_date=(NOW - timedelta(days=190)).date(),
            title='Shell health assessment', vet_name='Dr. Okafor, Green Valley',
            treatment='Calcium & UVB correction', notes='Early pyramiding from prior poor diet; stabilised.'))
        db.session.add(HandoverRecord(
            animal_id=kilo.id, from_user_id=center.id, to_user_id=maya.id,
            handover_date=NOW - timedelta(days=4)))

        notif_texts = [
            ("It's my 1st day with you — everything smells so new",
             "Hi, it's Kilo! I just arrived and I'm hiding in my shell a little — that's normal for me on a big move. "
             "A warm, quiet basking spot around 95°F would help me settle. I might not eat much today, and that's okay."),
            ("It's my 2nd day with you — still finding my feet",
             "It's a bit cooler here than I'm used to at the center. Could you nudge my basking lamp up a touch? "
             "I'd love some hay to nibble, and please lift me from the sides, not from above — it startles me."),
            ("It's my 3rd day with you — starting to explore",
             "I ventured out to bask today! I still miss my old routine, so keeping feeding times steady really helps. "
             "A little grazing time on safe grass would make me happy, and maybe a gentle warm soak."),
        ]
        for i, (title, body) in enumerate(notif_texts, start=1):
            db.session.add(Notification(
                user_id=maya.id, animal_id=kilo.id, day_number=i,
                title=title, body=body, is_read=(i < 2),
                created_at=NOW - timedelta(days=(4 - i))))
        db.session.commit()
        print('  created Kilo')

    print('  done — only missing pets were created; anything already present was left exactly as-is')


if __name__ == '__main__':
    app = create_app()
    with app.app_context():
        seed()
    print('\nDone! Demo accounts (password for all: demo1234):')
    print('  center@wildnest.demo   — Green Valley Wildlife Center (Rex + Milo, listed; rescued Kilo)')
    print('  maya@wildnest.demo     — Maya Chen (owns Luna; adopted Kilo — in transition)')
    print('  rob@wildnest.demo      — Rob Alvarez (empty; use to browse feed & test AI matching)')
    print('\nLog in as maya@wildnest.demo to see Kilo\'s Day-4 transition + notifications.')
