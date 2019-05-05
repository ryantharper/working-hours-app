from flask import render_template, flash, redirect, request, url_for, send_file
from werkzeug.urls import url_parse
from flask_login import current_user, login_user, logout_user, login_required

from app import db
from app.auth import bp
from app.auth.forms import LoginForm, RegistrationForm

from app.models import User, Work


#@bp.route('/', methods=['GET', 'POST'])
@bp.route('/login', methods=['GET', 'POST'])
def login():
    # redirects to index() route if user already logged in
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    form = LoginForm() # create object of LoginForm class from forms.py
    if form.validate_on_submit():
        # load user from database; filter_by query only includes objs that have a matching username
        # first --> used when you only need to have one result; return user obj if exists, or None if it doesn't;
        user = User.query.filter_by(username=form.username.data).first()
        # if user doesn't exist or password incorrect, display flash and redirect to login page
        if user is None or not user.check_password(form.password.data):
            flash('Invalid username or password')
            return redirect(url_for('auth.login'))
        # if username and password both correct, register user as logged in
        login_user(user, remember=form.remember_me.data)
        next_page = request.args.get('next')
        if not next_page or url_parse(next_page).netloc != '':
            next_page = url_for('main.index')
        return redirect(url_for('main.index'))
    return render_template('auth/login.html', title='Sign In', form=form)

# route for if user wants to logout
@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth/login'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))

    # creates database entry with regsiter entry
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()

        flash('Congratulations, you are now registered!')
        return redirect(url_for('auth.login'))

    return render_template('register.html', title='Register', form=form)
