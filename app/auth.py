from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from .models import db, User
from flask_mail import Message
from flask_login import login_user, logout_user
from datetime import datetime, timedelta
from app import mail
import random

auth = Blueprint('auth', __name__)

# Login
@auth.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email'].strip().lower()
        password = request.form['password']
        user = User.query.filter_by(email=email).first()

        if not user:
            flash('No account found with that email. Try signing up first!')
            return redirect(url_for('auth.login'))

        if not user.is_verified:
            flash('Account not verified. Please complete OTP verification first.')
            return redirect(url_for('auth.signup'))

        if user.check_password(password):
            login_user(user)
            flash('Login successful! Welcome back 🎉')
            return redirect(url_for('main.home'))
        else:
            flash('Incorrect password. Thalliyallo! Try cheyyu again.')

    return render_template('login.html')

# Signup
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        full_name = request.form['full_name'].strip()
        email = request.form['email'].strip().lower()
        password = request.form['password']

        # Check if a verified user already exists
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash("Email already registered. Try logging in, chetta!")
            return redirect(url_for('auth.login'))

        # Generate OTP
        otp = generate_otp()

        # Store signup data in session
        session['pending_signup'] = {
            'full_name': full_name,
            'email': email,
            'password': password,
            'otp': otp,
            'otp_created_at': datetime.utcnow().isoformat()
        }

        send_otp_email(email, otp)
        flash("Signup started! OTP sent to your email. Verify to continue 🎯")
        return redirect(url_for('auth.verify_otp'))

    return render_template('signup.html')

def generate_otp():
    return str(random.randint(100000, 999999))

# Helper: Send OTP Email
def send_otp_email(email, otp):
    msg = Message('Your OTP Code', recipients=[email])
    msg.body = f'Your OTP is {otp}. It will expire in 10 minutes.'
    mail.send(msg)

# Verify OTP
@auth.route('/verify-otp', methods=['GET', 'POST'])
def verify_otp():
    data = session.get('pending_signup')
    if not data:
        flash("Session expired or missing. Please restart signup.")
        return render_template('verify_otp.html')

    if request.method == 'POST':
        entered_otp = request.form['otp']
        stored_otp = data['otp']
        otp_created_at = datetime.fromisoformat(data['otp_created_at'])

        if entered_otp != stored_otp:
            flash("Invalid OTP. Please try again.")
            return render_template('verify_otp.html')

        if datetime.utcnow() - otp_created_at > timedelta(minutes=10):
            flash("OTP expired. Click resend to get a fresh one 💌")
            return render_template('verify_otp.html')

        # Create and save verified user
        user = User(
            full_name=data['full_name'],
            email=data['email'],
            is_verified=True
        )
        user.password = data['password']
        db.session.add(user)
        db.session.commit()

        session.pop('pending_signup', None)
        login_user(user)
        flash("Account verified! Welcome aboard 🎉")
        return redirect(url_for('main.dashboard'))

    return render_template('verify_otp.html')

@auth.route('/resend-otp')
def resend_otp():
    data = session.get('pending_signup')
    if not data:
        flash("No signup in progress. Try signing up again.")
        return redirect(url_for('auth.signup'))

    new_otp = generate_otp()
    data['otp'] = new_otp
    data['otp_created_at'] = datetime.utcnow().isoformat()
    session['pending_signup'] = data

    send_otp_email(data['email'], new_otp)
    flash("New OTP sent! Check your inbox 💌")
    return redirect(url_for('auth.verify_otp'))

# Forgot Password
@auth.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            otp = generate_otp()
            user.otp = otp
            db.session.commit()
            send_otp_email(email, otp)
            session['pending_reset'] = {
                'email': email,
                'otp': otp,
                'otp_created_at': datetime.utcnow().isoformat()
            }
            return redirect(url_for('auth.verify_reset_otp'))
        flash('Email not found')
    return render_template('forgot_password.html')

# Verify OTP for Password Reset
@auth.route('/verify-reset-otp', methods=['GET', 'POST'])
def verify_reset_otp():
    data = session.get('pending_reset')
    if not data:
        flash("Session expired or missing. Please restart password reset.")
        return render_template('forgot_password.html')

    if request.method == 'POST':
        entered_otp = request.form['otp']
        stored_otp = data['otp']
        otp_created_at = datetime.fromisoformat(data['otp_created_at'])

        if entered_otp != stored_otp:
            flash("Incorrect OTP. Try again.")
            return render_template("verify_reset_otp.html")

        if datetime.utcnow() - otp_created_at > timedelta(minutes=10):
            flash("OTP expired. Click resend to get a fresh one 💌")
            return render_template("verify_reset_otp.html")

        session['reset_email'] = data['email']
        session.pop('pending_reset', None)
        flash("OTP verified! You can now reset your password 🔐")
        return redirect(url_for('auth.change_password'))

    return render_template("verify_reset_otp.html")

@auth.route('/resend-reset-otp')
def resend_reset_otp():
    data = session.get('pending_reset')
    if not data:
        flash("No password reset in progress. Try again.")
        return redirect(url_for('auth.forgot_password'))

    new_otp = generate_otp()
    data['otp'] = new_otp
    data['otp_created_at'] = datetime.utcnow().isoformat()
    session['pending_reset'] = data

    send_otp_email(data['email'], new_otp)
    flash("New OTP sent! Check your inbox 💌")
    return redirect(url_for('auth.verify_reset_otp'))

# Change Password
@auth.route('/change-password', methods=['GET', 'POST'])
def change_password():
    if request.method == 'POST':
        email = session.get('reset_email')
        user = User.query.filter_by(email=email).first()
        if user:
            user.password = request.form['new_password']
            db.session.commit()
            flash('Password updated! Please log in.')
            return redirect(url_for('auth.login'))
    return render_template('change_password.html')

# Logout
@auth.route('/logout')
def logout():
    logout_user()
    flash("You’ve been logged out successfully.")
    return redirect(url_for('main.home'))  # ✅ Redirect to home page

@auth.route('/delete-all-users')
def delete_all_users():
    User.query.delete()
    db.session.commit()
    return "All users deleted!"