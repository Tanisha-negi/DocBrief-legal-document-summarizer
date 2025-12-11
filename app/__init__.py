from flask import Flask, flash, redirect, url_for
from flask_session import Session
from .extensions import db, login_manager, mail

def create_app():
    app = Flask(__name__)

    # Core Config
    app.config['SECRET_KEY'] = 'your_secret_key'
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
    app.config['SESSION_TYPE'] = 'filesystem'

    app.config['SERVER_NAME'] = '127.0.0.1:5000'
    app.config['PREFERRED_URL_SCHEME'] = 'http'
    app.config['APPLICATION_ROOT'] = '/'
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50 MB


    # Mail Config
    app.config['MAIL_SERVER'] = 'smtp.gmail.com'
    app.config['MAIL_PORT'] = 587
    app.config['MAIL_USE_TLS'] = True
    app.config['MAIL_USERNAME'] = 'tan.negi19@gmail.com'
    app.config['MAIL_PASSWORD'] = 'iqcmbdvxioazndlf'
    app.config['MAIL_DEFAULT_SENDER'] = 'tan.negi19@gmail.com'

    # Initialize Extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    Session(app)

    # Register Blueprints
    from .auth import auth
    app.register_blueprint(auth)

    from .routes import main
    app.register_blueprint(main)

    # User loader for Flask-Login
    from .models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Size error handler
    from werkzeug.exceptions import RequestEntityTooLarge

    @app.errorhandler(RequestEntityTooLarge)
    def handle_large_file(e):
        flash("File too large. Please upload a document under 50 MB.")
        return redirect(url_for("main.home"))

    return app