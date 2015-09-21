import os
import tempfile
import logging
# from threading import Thread
from flask import Flask
app = Flask(__name__)

def clean_dir(cleardir, keep_job=None):
    if os.path.exists(cleardir):
        for root, dirs, files in os.walk(cleardir, topdown=False):
            for name in files:
                if name == "taskfile_{0}.zip".format(keep_job):
                    continue
                os.remove(os.path.join(root, name))
            for name in dirs:
                if name == str(keep_job):
                    continue
                os.rmdir(os.path.join(root, name))

try:
    # Load config.py if available
    import config
    app.config.update(
        FLAMENCO_MANAGER = config.Config.FLAMENCO_MANAGER,
        TMP_FOLDER = config.Config.TMP_FOLDER,
        PORT = config.Config.PORT,
    )
except ImportError:
    # If we don't find the config.py we use the following defaults
    logging.info("Configuration file not found, using defaults")
    app.config['FLAMENCO_MANAGER'] = 'localhost:7777'
    app.config['TMP_FOLDER'] = tempfile.gettempdir()
    app.config['PORT'] = 5000

# Clean the temp folder from previous sessions
tmp_folder = os.path.join(app.config['TMP_FOLDER'], app.config['WORKER_STORAGE_DIR'])
if not os.path.exists(tmp_folder):
    os.mkdir(tmp_folder)

clean_dir(tmp_folder)

# Use multiprocessing to register the client the worker to the server
# while the worker app starts up
#def run(user_config=None):
#    config = controllers.app.config
#
#    if user_config:
#        config.from_object(user_config)
#
#    controllers.FLAMENCO_SERVER = config['FLAMENCO_MANAGER']
#
#    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
#        register_thread = Thread(target=controllers.register_worker)
#        register_thread.setDaemon(False)
#        register_thread.start()
#
#    controllers.app.run(config['HOST'], config['PORT'])
