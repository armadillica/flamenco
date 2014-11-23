from flask import send_file, Blueprint
from os.path import exists
from os import pardir

#from server import RENDER_PATH

render = Blueprint('render', __name__)

@render.route('/')
def index():
    return "Not Authorized", 403

@render.route('/<path:path>')
def get_render(path):
    #img = RENDER_PATH + "/" + path
    if not exists(img):
        return "Not Found", 404

    #print os.path.abspath(".")
    # TODO Find something less disgusting to get the path
    return send_file(pardir + "/" + img)


