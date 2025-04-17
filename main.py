from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import g4f
import subprocess
import sys
import os
from deep_translator import GoogleTranslator

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
            return redirect(url_for('chat_page'))
        else:
            pass
    return render_template("login.html", form=form)


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


@app.route('/python', methods=['GET', 'POST'])
def run_code():
    if request.method == 'POST':
        code = request.form['code']
        user_input = request.form.get('input', '')
        output = ""
        error = ""
        try:
            inputs = user_input.strip().splitlines()
            with open('temp_code.py', 'w', encoding='utf-8') as f:
                f.write(code)
            with open('temp_input.txt', 'w', encoding='utf-8') as f:
                f.write("\n".join(inputs))
            process = subprocess.Popen(
                ['python', 'temp_code.py'],
                stdin=open('temp_input.txt', 'r'),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            stdout, stderr = process.communicate()
            os.remove('temp_code.py')
            os.remove('temp_input.txt')
            output = stdout
            error = stderr

        except Exception as e:
            error = str(e)
            if os.path.exists('temp_code.py'):
                os.remove('temp_code.py')
            if os.path.exists('temp_input.txt'):
                os.remove('temp_input.txt')
        return render_template('comp.html',
                               code=code,
                               user_input=user_input,
                               output=output,
                               error=error)

    return render_template('comp.html',
                         code='''# Пример кода
a = int(input("Введите первое число: "))
b = int(input("Введите второе число: "))
print(f"Сумма: {a + b}")''',
                         user_input='10\n20')


@app.route('/translate', methods=['GET', 'POST'])
def translate_text():
    if request.method == 'POST':
        text_to_translate = request.form['text']
        target_language = request.form.get('target_lang')
        if not text_to_translate.strip():
            translated_text = ''
        else:
            try:
                translated_text = GoogleTranslator(source='auto', target=target_language).translate(text_to_translate)
            except Exception as e:
                print(f'Ошибка перевода: {e}')
                translated_text = f'Перевод невозможен: ошибка'
    else:
        translated_text = None

    return render_template('translator.html', translation_result=translated_text)


@app.route('/menu', methods=['GET', 'POST'])
def menu():
    return render_template("")

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=8080, host='127.0.0.1')
