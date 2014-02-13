from server import controllers
import model
import os

# here is default configuration. Just in case if user will not provide one.
# application is configured to run on local-host and port 9999
controllers.app.config.update(
    DEBUG=False,
    HOST='localhost',
    PORT=9999,
    DATABASE=os.path.join(os.path.dirname(controllers.__file__), '..', 'brender.sqlite')
)

def serve(user_config=None):
    config = controllers.app.config

    if user_config:
        config.from_object(user_config)

    model.DATABASE = config['DATABASE']
    model.create_database()

    # set SEVER_NAME value according to application configuration
    config.update(
        SERVER_NAME="%s:%d" % (config['HOST'], config['PORT'])
    )

    # run application
    controllers.app.run(
        controllers.app.config['HOST'],
        controllers.app.config['PORT']
    )
