from dashboard import controllers

controllers.app.config.update(
    SECRET_KEY='A0Zr98j/3yX R~XHH!jmN]LWX/,?RT',
    DEBUG=False,
    HOST='localhost',
    PORT=8888,
    BRENDER_SERVER='localhost:9999'
)

def serve(user_config=None):
    config = controllers.app.config

    if user_config:
        config.from_object(user_config)

	config.update(
		SERVER_NAME="%s:%s" % (config['HOST'], config['PORT'])
    )
    controllers.BRENDER_SERVER = config['BRENDER_SERVER']
    controllers.app.run(config['HOST'], config['PORT'])
