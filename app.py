from flask import Flask, redirect, url_for, request, jsonify, flash
from werkzeug.middleware.proxy_fix import ProxyFix
from extensions import db, login_manager
from dotenv import load_dotenv
from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError
import os
import threading

load_dotenv()


def _warm_up_rag_in_background():
    """Pre-index RAG documents via Gemini embeddings so the first chat message
    doesn't pay the indexing cost. Never blocks server startup; failure is
    silently ignored since RAG degrades gracefully."""
    def _warm():
        import rag
        rag.warmup()
    threading.Thread(target=_warm, daemon=True).start()


def ensure_schema():
    """Add new columns to existing tables without wiping data (lightweight migration)."""
    insp = inspect(db.engine)
    existing_tables = insp.get_table_names()

    # columns we may need to add over time: {table: {column: SQL type}}
    wanted = {
        'environmental_logs': {
            'media_path': 'VARCHAR(200)',
            'media_type': 'VARCHAR(10)',
        },
        'users': {
            'photo_path': 'VARCHAR(200)',
        },
        'animals': {
            'meal_plan_content': 'TEXT',
            'meal_plan_weather_summary': 'VARCHAR(200)',
            'meal_plan_generated_at': 'DATETIME',
            'current_location': 'VARCHAR(200)',
            'passport_token': 'VARCHAR(32)',
            'creator_dashboard_hidden': 'BOOLEAN DEFAULT 0',
            'profile_private': 'BOOLEAN DEFAULT 0',
        },
        'chat_messages': {
            'media_path': 'VARCHAR(200)',
        },
        'medical_records': {
            'next_due_date': 'DATE',
            'due_soon_alert_sent': 'BOOLEAN DEFAULT 0',
            'overdue_alert_sent': 'BOOLEAN DEFAULT 0',
        },
        'notifications': {
            'category': "VARCHAR(30) DEFAULT 'transition'",
            'is_emergency': 'BOOLEAN DEFAULT 0',
        },
    }
    for table, columns in wanted.items():
        if table not in existing_tables:
            continue
        have = {c['name'] for c in insp.get_columns(table)}
        for col, col_type in columns.items():
            if col not in have:
                db.session.execute(
                    text(f'ALTER TABLE {table} ADD COLUMN {col} {col_type}')
                )

    if 'notifications' in existing_tables:
        # drop any duplicate transition notes a past request race already created
        # (keep the earliest row), THEN add the unique index so it can't recur —
        # CREATE UNIQUE INDEX fails outright if duplicates still exist.
        db.session.execute(text("""
            DELETE FROM notifications
            WHERE category = 'transition' AND id NOT IN (
                SELECT MIN(id) FROM notifications
                WHERE category = 'transition'
                GROUP BY user_id, animal_id, day_number
            )
        """))
        db.session.execute(text("""
            CREATE UNIQUE INDEX IF NOT EXISTS uq_transition_notification_per_day
            ON notifications(user_id, animal_id, day_number)
            WHERE category = 'transition'
        """))

    db.session.commit()

def create_app():
    app = Flask(__name__)
    # Trust one hop of X-Forwarded-Proto/Host/Port from the deployment's reverse proxy
    # (Render/Railway/etc. terminate HTTPS in front of the app), so url_for(_external=True)
    # — used by the QR passport link — generates https:// URLs with the real public host
    # instead of guessing http:// from the internal request.
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'wildnest-dev-key')

    # Render (and most hosts) inject DATABASE_URL for their managed Postgres addon.
    # Falls back to local SQLite when unset, so local dev needs no Postgres install.
    database_url = os.getenv('DATABASE_URL', 'sqlite:///wildnest.db')
    if database_url.startswith('postgres://'):
        # SQLAlchemy 1.4+ dropped support for the old 'postgres://' scheme Render
        # (and Heroku before it) still hands out — rewrite it to 'postgresql://'.
        database_url = database_url.replace('postgres://', 'postgresql://', 1)
    app.config['SQLALCHEMY_DATABASE_URI'] = database_url
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # allow short behaviour videos

    if database_url.startswith('postgresql://'):
        app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
            # verify a pooled connection is still alive before handing it to a
            # request — cheap check that avoids "server closed the connection
            # unexpectedly" errors after the DB drops an idle connection
            'pool_pre_ping': True,
            # recycle connections just under Render free-tier Postgres's idle
            # timeout so we never hand out one that's about to be dropped
            'pool_recycle': 280,
        }

    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('rag/documents', exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth import auth
    from routes.main import main
    from routes.animals import animals
    from routes.wildsight import wildsight
    from routes.feed import feed

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(animals, url_prefix='/animals')
    app.register_blueprint(wildsight, url_prefix='/wildsight')
    app.register_blueprint(feed, url_prefix='/feed')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    @app.errorhandler(SQLAlchemyError)
    def handle_db_error(e):
        """Last-resort safety net for any commit/query that fails without its own
        try/except (a dropped hosted-DB connection, an unexpected constraint hit,
        etc.) — without this, a bare SQLAlchemyError bubbles up as a raw 500 page
        and leaves the session in a state that can't be reused for the rest of the
        request. Rolling back here always leaves the session usable again."""
        db.session.rollback()
        if request.path.startswith('/wildsight/') or request.is_json:
            return jsonify({'error': 'A database error occurred. Please try again.'}), 500
        flash('Something went wrong saving that — please try again.', 'danger')
        return redirect(request.referrer or url_for('main.dashboard'))

    @app.context_processor
    def inject_notifications():
        from flask_login import current_user
        from models import Notification
        if current_user.is_authenticated:
            notes = (Notification.query.filter_by(user_id=current_user.id)
                    .order_by(Notification.created_at.desc()).limit(12).all())
            unread = Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
            has_emergency = Notification.query.filter_by(
                user_id=current_user.id, is_read=False, is_emergency=True).count() > 0
            return dict(nav_notifications=notes, nav_unread_count=unread,
                       nav_has_emergency=has_emergency)
        return dict(nav_notifications=[], nav_unread_count=0, nav_has_emergency=False)

    with app.app_context():
        from models import (User, Animal, EnvironmentalLog, DailyMetric,
                            RehomeListing, AdoptionRequest, HandoverRecord,
                            WildSightAnalysis, ChatMessage, MedicalRecord,
                            Notification)
        db.create_all()
        ensure_schema()

    _warm_up_rag_in_background()

    return app


app = create_app()

if __name__ == '__main__':
    # host='0.0.0.0' so phones on the same WiFi can reach it (needed to scan/test
    # the QR passport link locally) — open the app via the LAN IP, not 127.0.0.1,
    # so url_for(_external=True) bakes in an address other devices can reach.
    app.run(debug=True, host='0.0.0.0')
