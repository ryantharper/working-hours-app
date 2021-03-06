from werkzeug.security import generate_password_hash, check_password_hash
from app import db, login
from flask_login import UserMixin


# creating the User database, inheriting db.model from flask-SQLAlchemy
class User(UserMixin, db.Model):
    # define database schema/structure
    id = db.Column(db.Integer, primary_key=True) # creates id field, which is the PK
    username = db.Column(db.String(64), index=True, unique=True) # creates username field, unique and indexed
    password_hash = db.Column(db.String(128)) # password hash field

    def __repr__(self):
        return '<User {}>'.format(self.username)

    # generates a password hash for security
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    # checks password user entered, returns true if match, else false
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

# creates work/hours database
class Work(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime)

    holiday_sick = db.Column(db.Boolean) # HOLIDAY, WITH ADDED 8 HRS
    holiday_NAH = db.Column(db.Boolean) # HOLIDAY, *NO* ADDED 8 HRS
    sick = db.Column(db.Boolean) # SICK DAYS, UNSURE WHAT TO DO WITH YET

    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    
    driving_hours = db.Column(db.DateTime)
    breaks = db.Column(db.String(64)) # OFFICIAL BREAK. 0,15,30,45mins
    other_work = db.Column(db.DateTime)
    poa = db.Column(db.DateTime)
    total_rest = db.Column(db.DateTime) # may have some calculations if end_of_shift true

    end_of_week = db.Column(db.Boolean)
    # if TRUE, end of week --> when next data entered (start of next week) --> calculate WEEKLY REST

    start_of_week = db.Column(db.Boolean)

    end_of_shift = db.Column(db.Boolean) # TRUE if data is taken straight from end of shift print out

    utc_plusone = db.Column(db.Boolean) # TICKED/TRUE IF DATA IS UTC +1


    week_beginning = db.Column(db.DateTime)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))

    def __repr__(self):
        return '<Work: date: %s, start time: %s, end time: %s, user id: %s>' % (self.date, self.start_time, self.end_time, self.user_id)

# configures user loader function, called using a given user id
@login.user_loader
def load_user(id):
    return User.query.get(int(id))
