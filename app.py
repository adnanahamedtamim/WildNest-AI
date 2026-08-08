from flask import Flask, redirect, url_for
from extensions import db, login_manager
from dotenv import load_dotenv
from sqlalchemy import inspect, text
import os

load_dotenv()


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
    db.session.commit()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'wildnest-dev-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wildnest.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 64 * 1024 * 1024  # allow short behaviour videos

    os.makedirs('static/uploads', exist_ok=True)
    os.makedirs('rag/documents', exist_ok=True)

    db.init_app(app)
    login_manager.init_app(app)

    from routes.auth import auth
    from routes.main import main
    from routes.animals import animals
    from routes.wildsight import wildsight

    app.register_blueprint(auth)
    app.register_blueprint(main)
    app.register_blueprint(animals, url_prefix='/animals')
    app.register_blueprint(wildsight, url_prefix='/wildsight')

    @app.route('/')
    def index():
        return redirect(url_for('auth.login'))

    with app.app_context():
        from models import (User, Animal, EnvironmentalLog, DailyMetric,
                            RehomeListing, AdoptionRequest, HandoverRecord,
                            WildSightAnalysis)
        db.create_all()
        ensure_schema()

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
