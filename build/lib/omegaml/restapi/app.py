from flask import Flask
from flask_restplus import Api
from werkzeug.utils import redirect

app = Flask(__name__)
api = Api(app)


@app.route('/docs')
def docs():
    return redirect("https://omegaml.github.io/omegaml/", code=302)
