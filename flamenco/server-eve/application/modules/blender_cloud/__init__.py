
def setup_app(app, url_prefix):
    from . import texture_libs, home_project

    texture_libs.setup_app(app, url_prefix=url_prefix)
    home_project.setup_app(app, url_prefix=url_prefix)
