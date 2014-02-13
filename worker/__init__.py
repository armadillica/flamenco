import os
from threading import Thread
from worker import controllers

controllers.app.config.update(
    DEBUG=False,
    HOST='127.0.0.1',
    PORT=5000,
    BRENDER_SERVER='localhost:9999'
)

# we use muliprocessing to register the client the worker to the server
# while the worker app starts up
def serve(user_config=None):
    config = controllers.app.config

    if user_config:
        config.from_object(user_config)

	config.update(
		SERVER_NAME="%s:%s" % (config['HOST'], config['PORT'])
    )
    controllers.BRENDER_SERVER = config['BRENDER_SERVER']

    if os.environ.get('WERKZEUG_RUN_MAIN') != 'true':
        register_thread = Thread(target=controllers.register_worker)
        register_thread.setDaemon(False)
        register_thread.start()

    controllers.app.run(config['HOST'], config['PORT'])
