from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from config import Config


db = SQLAlchemy()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Expose some Python builtins to Jinja templates (used in templates)
    app.jinja_env.globals.update(enumerate=enumerate, chr=chr, max=max, min=min, range=range)


    db.init_app(app)

    with app.app_context():
        from . import models 
        from . import routes
        db.create_all()

    return app