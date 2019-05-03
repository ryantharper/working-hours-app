from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, DateField, DateTimeField
from wtforms_components import TimeField
from wtforms.validators import DataRequired, ValidationError, EqualTo, Optional
from app.models import User, Work
from flask_login import current_user
import datetime

class OptionalIf(Optional):

    def __init__(self, otherFieldName, *args, **kwargs):
        self.otherFieldName = otherFieldName
        #self.value = value
        super(OptionalIf, self).__init__(*args, **kwargs)

    def __call__(self, form, field):
        otherField = form._fields.get(self.otherFieldName)
        if otherField is None:
            raise Exception('no field named "%s" in form' % self.otherFieldName)
        if bool(otherField.data):
            super(OptionalIf, self).__call__(form, field)

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    remember_me = BooleanField('Remember Me')
    submit = SubmitField('Sign In')

class RegistrationForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired()])
    password = PasswordField('Password', validators=[DataRequired()])
    password2 = PasswordField('Repeat Password', validators=[DataRequired(), EqualTo('password')])
    submit = SubmitField('Register')

    # check if username already taken
    def validate_username(self, username):
        user = User.query.filter_by(username=username.data).first()
        if user is not None:
            raise ValidationError('Please use a different username.')

class HoursForm(FlaskForm):
    # Date; Sick/Holiday (checkbox; Start Time; End Time; Submit
    dateEntry = DateField(label='Date', format='%Y-%m-%d', id='datepick', validators=[DataRequired()])
    holiday_sick = BooleanField('Holiday or Sick?', id="holsick", validators=[Optional()])
    start_time = TimeField(label='Start Time', id='timepick1', format='%H:%M', validators=[OptionalIf('holiday_sick')])
    end_time = TimeField(label='End Time', id='timepick2', validators=[OptionalIf('holiday_sick')])
    driving_hours = TimeField(label='Driving Hours', id='timepick3', validators=[OptionalIf('holiday_sick')])
    submit = SubmitField('Submit')

    def validate_dateEntry(self, dateEntry):
        # only allow past dates and today
        if dateEntry.data > datetime.date.today():
            raise ValidationError('Date must not be in the future.')
        current_user.get_id()
        # avoid date duplicates
        dt = datetime.datetime.strptime(dateEntry.data.strftime(format='%Y-%m-%d'), '%Y-%m-%d') # converts into same format as db
        d = Work.query.filter_by(date=dt, user_id=current_user.get_id()).first()
        if d is not None:
            raise ValidationError('Date already used')

    # formats
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.dateEntry.data:
            self.dateEntry.data = datetime.datetime.strptime(datetime.date.today().strftime(format='%Y-%m-%d'), '%Y-%m-%d')
