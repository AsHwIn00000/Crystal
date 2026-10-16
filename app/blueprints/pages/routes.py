from flask import render_template, redirect, url_for, request
from flask_login import login_required, current_user
from app.blueprints.pages import pages_bp


@pages_bp.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('pages.chat'))
    return render_template('index.html')


@pages_bp.route('/login')
def login():
    if current_user.is_authenticated:
        return redirect(url_for('pages.chat'))
    return render_template('auth/login.html')


@pages_bp.route('/register')
def register():
    if current_user.is_authenticated:
        return redirect(url_for('pages.chat'))
    return render_template('auth/register.html')


@pages_bp.route('/dashboard')
@login_required
def dashboard():
    return render_template('student/dashboard.html')


@pages_bp.route('/chat')
@login_required
def chat():
    return render_template('student/chat.html')


@pages_bp.route('/history')
@login_required
def history():
    return render_template('student/history.html')


@pages_bp.route('/documents')
@login_required
def documents():
    return render_template('student/documents.html')


@pages_bp.route('/profile')
@login_required
def profile():
    return render_template('student/profile.html')
