from flask import Flask
from flask_restplus import Api
from werkzeug.utils import redirect

app = Flask(__name__)
api = Api(app)

# ensure slashes in URIs are matched as specified
# see https://stackoverflow.com/a/33285603/890242
app.url_map.strict_slashes = True
# use Flask json encoder to support datetime
app.config['RESTPLUS_JSON'] = {'cls': app.json_encoder}


@app.route('/docs')
def docs():
    return redirect("https://omegaml.github.io/omegaml/", code=302)
