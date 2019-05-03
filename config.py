import os
basedir = os.path.abspath(os.path.dirname(__file__))

# stores all config terms

class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'lucky19'

    # takes location of apps database, providing fallback when environ does not define the variable
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    # disable feature that signals app every time a change is about to be made in the db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
