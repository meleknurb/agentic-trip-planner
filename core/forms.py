# core/forms.py

from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Length
from wtforms.validators import EqualTo

class RegisterForm(FlaskForm):
    username = StringField('Username', validators=[
        DataRequired('Please enter a username.'),
        Length(min=3, max=50, message='Username must be between 3 and 50 characters.')
    ])
    password = PasswordField('Password', validators=[
        DataRequired('Please enter a password.'),
        Length(min=5, message='Password must be at least 5 characters long.')
    ])
    submit = SubmitField('Register')

class LoginForm(FlaskForm):
    username = StringField('Username', validators=[DataRequired('Please enter your username.')])
    password = PasswordField('Password', validators=[DataRequired('Please enter your password.')])
    submit = SubmitField('Login')

class UpdatePasswordForm(FlaskForm):
    current_password = PasswordField('Current Password', validators=[DataRequired()])
    new_password = PasswordField('New Password', validators=[
        DataRequired('Please enter a new password.'),
        Length(min=5, message='Password must be at least 5 characters long.')
    ])
    confirm_new_password = PasswordField('Confirm New Password', validators=[
        DataRequired('Please confirm your new password.'),
        EqualTo('new_password', message='Passwords do not match.')
    ])
    submit = SubmitField('Save Password')