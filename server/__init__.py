from server import controllers
import model
import os

# This is the default server configuration, in case the user will not provide one.
# The Application is configured to run on local-host and port 9999
# The brender.sqlite database will be created inside of the server folder
controllers.app.config.update(
    DEBUG=False,
    HOST='localhost',
    PORT=9999,
    DATABASE=os.path.join(os.path.dirname(controllers.__file__), 'brender.sqlite')
)

def serve(user_config=None):
    config = controllers.app.config

    if user_config:
        config.from_object(user_config)

    model.DATABASE = config['DATABASE']
    model.create_database()

    # Set SEVER_NAME value according to application configuration
    config.update(
        SERVER_NAME="%s:%d" % (config['HOST'], config['PORT'])
    )

    #controllers.app.run(host='0.0.0.0')
    
    # Run application
    controllers.app.run(
        controllers.app.config['HOST'],
        controllers.app.config['PORT'],
    )
