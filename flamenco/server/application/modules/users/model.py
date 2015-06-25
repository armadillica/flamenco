import hashlib, urllib
import datetime

from application import db

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True)
    username = db.Column(db.String(255), unique=True)
    password = db.Column(db.String(255))
    active = db.Column(db.Boolean())
    deleted = db.Column(db.Boolean())
    confirmed_at = db.Column(db.DateTime())
    first_name = db.Column(db.String(255))
    last_name = db.Column(db.String(255))
    last_login_at = db.Column(db.DateTime())
    current_login_at = db.Column(db.DateTime())
    last_login_ip = db.Column(db.String(100))
    current_login_ip = db.Column(db.String(100))
    login_count = db.Column(db.Integer)

    # roles = db.relationship('Role', secondary='roles_users',
    #                         backref=db.backref('users', lazy='dynamic'))

    def gravatar(self, size=64, consider_settings=True):
        parameters = {'s':str(size), 'd':'mm'}
        return "https://www.gravatar.com/avatar/" + \
            hashlib.md5(self.email.lower()).hexdigest() + \
            "?" + urllib.urlencode(parameters)

    def __str__(self):
        return self.email

# TODO use later when our implementaiton becomes more complete

# class Role(db.Model):
#     id = db.Column(db.Integer(), primary_key=True)
#     name = db.Column(db.String(80), unique=True)
#     description = db.Column(db.String(255))

#     def __str__(self):
#         return self.name


# roles_users = db.Table('roles_users',
#     db.Column('user_id', db.Integer(), db.ForeignKey('user.id')),
#     db.Column('role_id', db.Integer(), db.ForeignKey('role.id')))


# class UserOauth(db.Model):
#     id = db.Column(db.Integer(), primary_key=True)
#     user_id = db.Column(db.Integer(), db.ForeignKey('user.id'), nullable=False)
#     service = db.Column(db.String(80), nullable=False)
#     service_user_id = db.Column(db.String(80))
#     token = db.Column(db.String(255))

#     def __str__(self):
#         return self.service_user_id

