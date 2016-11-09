
def setup_app(app):
    from . import eve_hooks

    eve_hooks.setup_app(app)
