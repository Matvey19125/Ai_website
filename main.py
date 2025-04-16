from flask import Flask, render_template, redirect, url_for, request
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import g4f
import subprocess
import sys

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


@app.route('/python', methods=['GET', 'POST']) # ИГорь брадт тут делать надо WW
def home():
    output = None
    current_code = ""
    console_history = []
    waiting_for_input = False
    input_prompt = ""
    stored_code = ""
    original_code = ""
    partial_input = False
    if request.method == 'POST':
        if 'clear' in request.form:
            console_history = []
            current_code = ""
            stored_code = ""
            original_code = ""
            waiting_for_input = False
            partial_input = False
        elif 'console_input' in request.form:
            user_input = request.form['console_input']
            if waiting_for_input:
                if not partial_input:
                    console_history.append(f"{input_prompt}{user_input}")
                else:
                    console_history[-1] = console_history[-1] + "\n" + user_input
                if user_input.endswith('\\'):
                    partial_input = True
                    input_prompt = "... "
                    return render_template('comp.html',
                                           current_code=original_code,
                                           console_history=console_history,
                                           waiting_for_input=True,
                                           input_prompt=input_prompt)
                full_code = stored_code + "\n__input_value = '''" + user_input + "'''"

                try:
                    process = subprocess.Popen(
                        [sys.executable, "-c", full_code],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    try:
                        stdout, stderr = process.communicate(timeout=5)
                        output = stdout if stdout else stderr
                        console_history.extend(output.splitlines())
                    except subprocess.TimeoutExpired:
                        process.kill()
                        console_history.append("Ошибка: Превышено время выполнения (5 секунд)")

                    waiting_for_input = False
                    partial_input = False
                    current_code = original_code
                    stored_code = ""

                except Exception as e:
                    console_history.append(f"Ошибка: {str(e)}")
                    waiting_for_input = False
                    partial_input = False
                    stored_code = ""
                    current_code = original_code

            else:
                current_code = user_input
                try:
                    if "input(" in user_input:
                        original_code = user_input
                        stored_code = user_input
                        waiting_for_input = True
                        input_parts = user_input.split("input(")
                        if len(input_parts) > 1:
                            prompt_part = input_parts[1].split(")")[0]
                            input_prompt = prompt_part.strip(" '\"") + ": "
                        else:
                            input_prompt = ": "
                        console_history.append(f">>> {user_input}")
                        console_history.append(f"Введите данные: {input_prompt}")
                        return render_template('comp.html',
                                               current_code=original_code,
                                               console_history=console_history,
                                               waiting_for_input=True,
                                               input_prompt=input_prompt)
                    process = subprocess.Popen(
                        [sys.executable, "-c", user_input],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    try:
                        stdout, stderr = process.communicate(timeout=5)
                        output = stdout if stdout else stderr
                        console_history.append(f">>> {user_input}")
                        console_history.extend(output.splitlines())
                    except subprocess.TimeoutExpired:
                        process.kill()
                        console_history.append(f">>> {user_input}")
                        console_history.append("Ошибка: Превышено время выполнения (5 секунд)")

                except Exception as e:
                    console_history.append(f">>> {user_input}")
                    console_history.append(f"Ошибка: {str(e)}")

        else:
            current_code = request.form['code']
            original_code = current_code
            try:
                if "input(" in current_code:
                    stored_code = current_code
                    waiting_for_input = True
                    input_parts = current_code.split("input(")
                    if len(input_parts) > 1:
                        prompt_part = input_parts[1].split(")")[0]
                        input_prompt = prompt_part.strip(" '\"") + ": "
                    else:
                        input_prompt = ": "
                    console_history.append(f">>> {current_code}")
                    console_history.append(f"Введите данные: {input_prompt}")
                else:
                    process = subprocess.Popen(
                        [sys.executable, "-c", current_code],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.PIPE,
                        text=True
                    )

                    try:
                        stdout, stderr = process.communicate(timeout=5)
                        output = stdout if stdout else stderr
                        console_history.append(f">>> {current_code}")
                        console_history.extend(output.splitlines())
                    except subprocess.TimeoutExpired:
                        process.kill()
                        console_history.append(f">>> {current_code}")
                        console_history.append("Ошибка: Превышено время выполнения (5 секунд)")

            except Exception as e:
                console_history.append(f">>> {current_code}")
                console_history.append(f"Ошибка: {str(e)}")

    return render_template('comp.html',
                           current_code=current_code,
                           console_history=console_history,
                           waiting_for_input=waiting_for_input,
                           input_prompt=input_prompt)

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=8080, host='127.0.0.1')
