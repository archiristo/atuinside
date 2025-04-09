from flask import Flask
from models import db
from flask_migrate import Migrate

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///forum.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.secret_key = 'supersecretkey'
    migrate = Migrate(app, db)
    db.init_app(app)

    #with app.app_context():
       # db.create_all()  # Veritabanını oluştur

    return app
