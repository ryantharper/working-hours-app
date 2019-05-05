from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, BooleanField, SubmitField, DateField, DateTimeField, SelectField
from wtforms_components import TimeField
from wtforms.validators import DataRequired, ValidationError, EqualTo, Optional
from app.models import User, Work
from flask_login import current_user
from datetime import timedelta
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


class HoursForm(FlaskForm):
    # Date; Sick/Holiday (checkbox; Start Time; End Time; Submit
    dateEntry = DateField(label='Date', format='%Y-%m-%d', id='datepick', validators=[DataRequired()])
    holiday_sick = BooleanField('Holiday or Sick?', id="holsick", validators=[Optional()])
    start_time = TimeField(label='Start Time', id='timepick1', format='%H:%M', validators=[OptionalIf('holiday_sick')])
    end_time = TimeField(label='End Time', id='timepick2', validators=[OptionalIf('holiday_sick')])
    driving_hours = TimeField(label='Driving Hours', id='timepick3', validators=[OptionalIf('holiday_sick')])

    # OFFICIAL break
    breaks = SelectField(label='Official Break', id='timepick4', choices=[('timedelta(0)', '0 minutes'), ('timedelta(minutes=15)', '15 minutes'),('timedelta(minutes=30)', '30 minutes'),('timedelta(minutes=45)', '45 minutes')], validators=[OptionalIf('holiday_sick')])

    other_work = TimeField(label='Other Work', id='timepick5', validators=[OptionalIf('holiday_sick')])
    poa = TimeField(label='POA', id='timepick6', validators=[OptionalIf('holiday_sick')])

    # total rest, see models.py for details
    total_rest = TimeField(label='Total Rest', id='timepick6', validators=[OptionalIf('holiday_sick')])

    # see what happens if FRIDAY or THURS/FRI is HOLIDAY/SICK, how does that account for WEEKLY REST
    end_of_week = BooleanField('End of Week?', id="endweek", validators=[OptionalIf('holiday_sick')])


    end_of_shift = BooleanField("Data taken from Today's shift?", id="timepick7", validators=[OptionalIf('holiday_sick')]) # see models.py for details
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
