
def setup_app(app, url_prefix):
    from . import texture_libs

    texture_libs.setup_app(app, url_prefix=url_prefix)
