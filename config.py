import os
from dotenv import load_dotenv

basedir = os.path.abspath(os.path.dirname(__file__))

load_dotenv(os.path.join(basedir, '.env'))

# stores all config terms
class Config(object):
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'lucky19'

    # takes location of apps database, providing fallback when environ does not define the variable
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or 'sqlite:///' + os.path.join(basedir, 'app.db')
    # disable feature that signals app every time a change is about to be made in the db
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    '''
    MAIL_SERVER = os.environ.get('MAIL_SERVER')
    MAIL_PORT = int(os.environ.get('MAIL_PORT') or 25)
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS') is not None
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    ADMINS = ['harper.ryan196@gmail.com']
    '''
