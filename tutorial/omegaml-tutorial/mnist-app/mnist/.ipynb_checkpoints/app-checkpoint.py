from flask import Flask, Blueprint, request, render_template

def create_app(server=None, uri=None, **kwargs):
    # we always need the create_app() function
    import omegaml as om 
    
    if server is None:
        server = Flask(__name__)

    # create a component that serves our app
    # -- a Blueprint is a little web app 
    # -- the omegaml apphub will create a server and we attach the blueprint
    bp = Blueprint('myapp', __name__,
                   url_prefix=uri,
                   static_folder='static',
                   template_folder='templates')

    # our main page
    # -- it will load at the uri= (url_prefix=)
    # -- which will be /apps/<userid>/<appname>
    @bp.route('/')
    def index():
        return render_template('grid.html')

    # the prediction api
    # -- it will take the image data from input (request.json)
    # -- pass it to the runtime
    # -- return the result
    @bp.route('/predict', methods=['POST'])
    def predict():
        data = request.json
        model = om.runtime.model('mnist')
        result = model.predict(data['image'])
        digit = str(result.get()[0])
        return {"result": digit}

    server.register_blueprint(bp)

    # apphub configuration
    server.config['APP_TITLE'] = 'omega-ml dashboard'
    # configure claims requirements
    server.config['JWT_CLAIMS_RULES'] = {
        'require': {
            r'.*/predict': {
                'sourceGroups': '.*',
            }
        }
    }
    server.config['APPHUB_APP_SECURE_NOPROTECT'] = (f'{uri}/?$', '.*/login.*', '.*/logout.*', '.*/authorize', '.*/static/.*', '.*/healthz')
    server.config['APPHUB_AUTHORIZE_OMEGA'] = False
    return server

if __name__ == '__main__':
    server = create_app()
    server.run(debug=True)
    
                   
    