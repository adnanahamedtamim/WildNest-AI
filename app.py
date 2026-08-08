from flask import Flask, redirect, url_for
from extensions import db, login_manager
from dotenv import load_dotenv
import os

load_dotenv()

def create_app():
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'wildnest-dev-key')
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///wildnest.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

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

    return app


if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
