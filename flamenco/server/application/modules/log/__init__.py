from application import db
from application.modules.log.model import Log

def log_to_database(item_id, category, log):
    """General purpose function for storing logs in the database.
    """
    log = Log(
        item_id=item_id,
        category=category,
        log=log)
    db.session.add(log)
    db.session.commit()


def log_from_database(item_id, category):
    return Log.query.filter_by(item_id=item_id, category=category).all()
