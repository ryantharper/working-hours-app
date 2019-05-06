from app import create_app, db
#from flask import render_template
from app.models import User, Work

app=create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db':db, 'User':User, 'Work':Work}
