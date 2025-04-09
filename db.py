# Create all tables and then create them again, just run it once, before running app.py
from app import app, db

with app.app_context():
    db.drop_all()
    db.create_all()