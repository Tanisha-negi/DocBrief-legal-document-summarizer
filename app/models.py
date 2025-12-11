from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
from sqlalchemy.ext.hybrid import hybrid_property

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    
    # Store the hashed password securely
    _password = db.Column('password', db.String(200), nullable=True)

    is_verified = db.Column(db.Boolean, default=False)
    otp = db.Column(db.String(6), nullable=True)
    google_id = db.Column(db.String(200), nullable=True)
    otp_created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Hybrid property for password access
    @hybrid_property
    def password(self):
        return self._password

    @password.setter
    def password(self, raw_password):
        self._password = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        if not self._password:
            return False
        return check_password_hash(self._password, raw_password)


class Document(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(200), nullable=False)
    filepath = db.Column(db.String(300), nullable=False)
    # This field stores the multi-line, plain-text summary from the AI
    summary = db.Column(db.Text, nullable=True)

    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    user = db.relationship('User', backref=db.backref('documents', lazy=True))

    # ❌ REMOVED the bullet_points property 
    # The logic is handled correctly in the Flask routes via doc.summary.split('\n')