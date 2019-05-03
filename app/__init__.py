from flask import Flask
from config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_moment import Moment
from flask_bootstrap import Bootstrap

app = Flask(__name__)
app.config.from_object(Config) # read and apply config terms

login = LoginManager(app)
login.login_view = 'login'

# create database and db migration instances
db = SQLAlchemy(app) # db engine
migrate = Migrate(app, db) # migration engine

bootstrap = Bootstrap(app)
moment = Moment(app)

app.jinja_env.filters['zip'] = zip

from app import routes, models
