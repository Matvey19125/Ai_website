from flask import Flask, render_template, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

app.config['SECRET_KEY'] = 'your-secret-key-here'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///password.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired()])
    password = PasswordField('Пароль', validators=[DataRequired()])
    submit = SubmitField('Зарегистрироваться')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/', methods=['GET', 'POST'])
def main_reg():
    form = LoginForm()
    if form.validate_on_submit():
        existing_user = User.query.filter_by(email=form.email.data).first()
        if existing_user:
            return render_template('register.html',
                                   form=form,
                                   message="Пользователь с таким email уже существует")

        new_user = User(email=form.email.data)

        new_user.set_password(form.password.data)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('output'))

    return render_template('register.html', form=form)


@app.route("/output", methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user)
            return redirect(url_for('main'))
        else:
            pass
    return render_template("login.html", form=form)

@app.route("/main")
def main():
    return "Вошел"

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=8080, host='127.0.0.1')


    @app.route("/chat", methods=['GET', 'POST'])
    @login_required
    def chat_page():
        if request.method == 'POST':
            user_input = request.form.get('user_input')
            if user_input:
                try:
                    response = g4f.ChatCompletion.create(
                        model="gpt-4",
                        messages=[{"role": "user", "content": user_input}]
                    )
                    return render_template('chat.html', response=response, user_input=user_input)
                except Exception as e:
                    return render_template('chat.html', error=str(e))

        return render_template('chat.html')