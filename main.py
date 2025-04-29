from flask import Flask, render_template, redirect, url_for, request, jsonify, flash
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, current_user, login_required
from flask_wtf import FlaskForm
from wtforms.validators import DataRequired, Email, Length
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import DataRequired, Email
from werkzeug.security import generate_password_hash, check_password_hash
import g4f
import subprocess
import sys
import os
from deep_translator import GoogleTranslator
from werkzeug.utils import secure_filename
import shutil


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['PROJECTS_FOLDER'] = 'static/projects'
app.config['SECRET_KEY'] = 'negt7821-Igoryan'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///password.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB limit
ALLOWED_EXTENSIONS = {'mp3', 'wav', 'ogg', 'm4a', 'flac'}
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'output'


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password = db.Column(db.String(128), nullable=False)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)


class RegistrationForm(FlaskForm):
    email = StringField('Email', validators=[
        DataRequired(message='Это поле обязательно'),
        Email(message='Некорректный адрес электронной почты')
    ])
    password = PasswordField('Пароль', validators=[
        DataRequired(message='Это поле обязательно'),
        Length(min=8, message='Пароль должен содержать минимум 8 символов')
    ])
    submit = SubmitField('Зарегистрироваться')


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/', methods=['GET', 'POST'])
def main_reg():
    form = RegistrationForm()
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
        return redirect(url_for('menu'))
    return render_template('register.html', form=form)


@app.route("/output", methods=['GET', 'POST'])
def output():
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user:
            if user.check_password(form.password.data):
                login_user(user)
                return redirect(url_for('menu'))
            else:
                flash('Неверный пароль', 'error')
        else:
            flash('Пользователь с таким email не найден', 'error')
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


@app.route('/create_project', methods=['POST'])
@login_required
def create_project():
    project_name = request.form.get('project_name')
    if not project_name:
        flash('Не указано название проекта', 'error')
        return redirect(url_for('run_code'))
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    project_folder = os.path.join(user_folder, secure_filename(project_name))
    if os.path.exists(project_folder):
        flash('Проект с таким именем уже существует', 'error')
        return redirect(url_for('run_code'))
    os.makedirs(project_folder)
    with open(os.path.join(project_folder, 'main.py'), 'w', encoding='utf-8') as f:
        f.write('''# Ваш код Python
print("Привет, мир!")''')
    flash(f'Проект "{project_name}" успешно создан', 'success')
    return redirect(url_for('run_code'))


@app.route('/save_project/<project_name>', methods=['POST'])
@login_required
def save_project(project_name):
    code = request.form.get('code', '').rstrip()
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    project_folder = os.path.join(user_folder, secure_filename(project_name))
    if not os.path.exists(project_folder):
        flash('Проект не найден', 'error')
        return redirect(url_for('run_code'))
    try:
        with open(os.path.join(project_folder, 'main.py'), 'w', encoding='utf-8') as f:
            f.write(code)
        flash('Проект успешно сохранен', 'success')
    except Exception as e:
        flash(f'Ошибка при сохранении проекта: {str(e)}', 'error')
    return redirect(url_for('load_project', project_name=project_name))


@app.route('/load_project/<project_name>')
@login_required
def load_project(project_name):
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    project_folder = os.path.join(user_folder, secure_filename(project_name))
    if not os.path.exists(project_folder):
        flash('Проект не найден', 'error')
        return redirect(url_for('run_code'))
    main_file = os.path.join(project_folder, 'main.py')
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            code = f.read().rstrip() + "\n"
    else:
        code = '# Файл main.py не найден'

    return render_template('comp.html',
                           code=code,
                           project_name=project_name,
                           projects=get_user_projects(current_user.id))


def get_user_projects(user_id):
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(user_id))
    if os.path.exists(user_folder):
        return sorted([d for d in os.listdir(user_folder)
                       if os.path.isdir(os.path.join(user_folder, d))])
    return []


@app.route('/python', methods=['GET', 'POST'])
@login_required
def run_code():
    if request.method == 'POST':
        code = request.form.get('code', '')
        code = code.rstrip()
        user_input = request.form.get('input', '')
        project_name = request.form.get('project_name', '')
        output = ""
        error = ""
        if project_name:
            user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
            project_folder = os.path.join(user_folder, secure_filename(project_name))

            if os.path.exists(project_folder):
                try:
                    with open(os.path.join(project_folder, 'main.py'), 'w', encoding='utf-8') as f:
                        f.write(code)
                        # Добавляем один перенос строки в конце файла
                        f.write('\n')
                except Exception as e:
                    flash(f'Ошибка при сохранении проекта: {str(e)}', 'error')
        try:
            inputs = user_input.strip().splitlines()
            with open('temp_code.py', 'w', encoding='utf-8') as f:
                f.write(code)
                f.write('\n')
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
                               error=error,
                               project_name=project_name,
                               projects=get_user_projects(current_user.id))
    return render_template('comp.html',
                           code='''# Пример кода
a = int(input())
b = int(input())
print(a + b)''',
                           user_input='10\n20',
                           projects=get_user_projects(current_user.id))


@app.route('/delete_project/<project_name>', methods=['POST'])
@login_required
def delete_project(project_name):
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    project_folder = os.path.join(user_folder, secure_filename(project_name))

    if os.path.exists(project_folder):
        shutil.rmtree(project_folder)
        flash(f'Проект "{project_name}" успешно удален', 'success')
    else:
        flash('Проект не найден', 'error')
    return redirect(url_for('run_code'))

@app.route('/translate', methods=['GET', 'POST'])
def translate_text():
    if request.method == 'POST':
        text_to_translate = request.form['text'].strip()
        target_language = request.form.get('target_lang')

        if not text_to_translate:
            translated_text = ''
        else:
            try:
                translated_text = GoogleTranslator(source='auto', target=target_language).translate(text_to_translate)
            except Exception as e:
                print(f'Ошибка перевода: {e}')
                translated_text = f'Перевод невозможен: ошибка'

        return render_template(
            'translator.html',
            original_text=text_to_translate,
            translation_result=translated_text
        )
    else:
        return render_template('translator.html')


@app.route('/menu', methods=['GET', 'POST'])
def menu():
    return render_template("menu.html")


@app.route('/music', methods=['GET', 'POST'])
@login_required
def music():
    if request.method == 'POST':
        if 'musicFiles[]' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        files = request.files.getlist('musicFiles[]')
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
        os.makedirs(user_folder, exist_ok=True)
        uploaded_files = []
        for file in files:
            if file.filename == '':
                flash('No selected file', 'error')
                continue
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_folder, filename)
                if os.path.exists(filepath):
                    flash(f'File {filename} already exists', 'warning')
                    continue
                file.save(filepath)
                uploaded_files.append(filename)
                flash(f'File {filename} successfully uploaded', 'success')

        return redirect(url_for('music'))
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    existing_files = []
    if os.path.exists(user_folder):
        existing_files = sorted(os.listdir(user_folder))
    return render_template("music.html", existing_files=existing_files)


@app.route('/delete_track', methods=['POST'])
@login_required
def delete_track():
    filename = request.form.get('filename')
    if not filename:
        flash('Не указано имя файла для удаления', 'error')
        return redirect(url_for('music'))

    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], str(current_user.id))
    filepath = os.path.join(user_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'Файл {filename} успешно удален', 'success')
    else:
        flash(f'Файл {filename} не найден', 'error')

    return redirect(url_for('music'))


@app.route("/razvil", methods=["GET", "POST"])
def razvil():
    return render_template("razvil.html")


@app.route('/books', methods=['GET', 'POST'])
@login_required
def pdf_upload():
    def allowed_file(filename):
        return '.' in filename and filename.rsplit('.', 1)[1].lower() == 'pdf'
    REQUIRED_BOOK = "Ваш первый учебник.pdf"
    static_books_dir = os.path.join(app.static_folder, 'books')
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs', str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    required_book_src = os.path.join(static_books_dir, REQUIRED_BOOK)
    required_book_dst = os.path.join(user_folder, REQUIRED_BOOK)

    if not os.path.exists(required_book_dst) and os.path.exists(required_book_src):
        try:
            shutil.copy2(required_book_src, required_book_dst)
            flash(f'Обязательный учебник {REQUIRED_BOOK} был добавлен в вашу библиотеку', 'info')
        except Exception as e:
            flash(f'Не удалось скопировать обязательный учебник: {str(e)}', 'error')
    if request.method == 'POST':
        if 'pdfFiles[]' not in request.files:
            flash('No file part', 'error')
            return redirect(url_for('pdf_upload'))
        files = request.files.getlist('pdfFiles[]')
        uploaded_files = []
        for file in files:
            if file.filename == '':
                flash('No selected file', 'error')
                continue
            if file and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                filepath = os.path.join(user_folder, filename)
                if os.path.exists(filepath):
                    flash(f'File {filename} already exists', 'warning')
                    continue
                file.save(filepath)
                uploaded_files.append(filename)
                flash(f'File {filename} successfully uploaded', 'success')
            else:
                flash(f'File {file.filename} is not a PDF', 'error')
        return redirect(url_for('pdf_upload'))
    existing_files = []
    if os.path.exists(user_folder):
        existing_files = sorted([f for f in os.listdir(user_folder) if f.lower().endswith('.pdf')])

    return render_template("document.html", existing_files=existing_files)


@app.route('/delete_book/<filename>', methods=['POST'])
@login_required
def delete_book(filename):
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'pdfs', str(current_user.id))
    filepath = os.path.join(user_folder, filename)

    if os.path.exists(filepath):
        os.remove(filepath)
        flash(f'Файл {filename} успешно удалён', 'success')
    else:
        flash(f'Файл {filename} не найден', 'error')

    return redirect(url_for('pdf_upload'))


def allowed_pdf_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'pdf'}


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(port=8080, host='127.0.0.1')