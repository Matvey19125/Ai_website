from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, make_response
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
import time
import os
from deep_translator import GoogleTranslator
from werkzeug.utils import secure_filename
import shutil
import re


def allowed_file(filename):
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


app = Flask(__name__)
app.config['NOTES_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'notes')
app.config['PROJECTS_FOLDER'] = 'static/projects'
app.config['UPLOAD_FOLDER'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'uploads')
app.config['SECRET_KEY'] = 'negt7821-Igoryan'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///password.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = 'static/uploads'
app.config['MAX_CONTENT_LENGTH'] = 1000000 * 1024 * 1024
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


class ChatMessage(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    text = db.Column(db.String(500), nullable=False)
    user = db.relationship('User', backref='messages')


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
    theme = request.cookies.get('theme', 'light')
    if request.method == 'POST':
        user_input = request.form.get('user_input')
        if user_input:
            try:
                response = g4f.ChatCompletion.create(
                    model="gpt-4",
                    messages=[{"role": "user", "content": user_input}]
                )
                return render_template('chat.html', theme=theme, response=response, user_input=user_input)
            except Exception as e:
                return render_template('chat.html', theme=theme, error=str(e))
    return render_template('chat.html', theme=theme)


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
    save_code_to_file(os.path.join(project_folder, 'main.py'), '''# Ваш код Python
print("Привет, мир!")''')
    flash(f'Проект "{project_name}" успешно создан', 'success')
    return redirect(url_for('run_code'))


def save_code_to_file(filepath, code):
    lines = [line.rstrip() for line in code.splitlines()]
    while lines and not lines[-1]:
        lines.pop()
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(lines))
        f.write('\n')


@app.route('/save_project/<project_name>', methods=['POST'])
@login_required
def save_project(project_name):
    theme = request.cookies.get('theme', 'light')
    code = request.form.get('code', '')
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    project_folder = os.path.join(user_folder, secure_filename(project_name))
    if not os.path.exists(project_folder):
        flash('Проект не найден', 'error')
        return redirect(url_for('run_code'))

    try:
        save_code_to_file(os.path.join(project_folder, 'main.py'), code)
        flash('Проект успешно сохранен', 'success')
    except Exception as e:
        flash(f'Ошибка при сохранении проекта: {str(e)}', 'error')
    return redirect(url_for('load_project', project_name=project_name, theme=theme))


@app.route('/load_project/<project_name>')
@login_required
def load_project(project_name):
    theme = request.cookies.get('theme', 'light')
    user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
    project_folder = os.path.join(user_folder, secure_filename(project_name))
    if not os.path.exists(project_folder):
        flash('Проект не найден', 'error')
        return redirect(url_for('run_code'))
    main_file = os.path.join(project_folder, 'main.py')
    if os.path.exists(main_file):
        with open(main_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            while lines and lines[-1].strip() == '':
                lines.pop()
            code = ''.join(lines) + '\n'
    else:
        code = '# Файл main.py не найден\n'

    return render_template('comp.html',
                           theme=theme,
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
    theme = request.cookies.get('theme', 'light')
    if request.method == 'POST':
        code = request.form.get('code', '').rstrip()
        user_input = request.form.get('input', '')
        project_name = request.form.get('project_name', '')
        output = ""
        error = ""
        if project_name:
            user_folder = os.path.join(app.config['PROJECTS_FOLDER'], str(current_user.id))
            project_folder = os.path.join(user_folder, secure_filename(project_name))

            if os.path.exists(project_folder):
                try:
                    save_code_to_file(os.path.join(project_folder, 'main.py'), code)
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
                               theme=theme,
                               user_input=user_input,
                               output=output,
                               error=error,
                               project_name=project_name,
                               projects=get_user_projects(current_user.id))
    return render_template('comp.html',
                           theme=theme,
                           code='''# Пример кода
a = int(input())
b = int(input())
print(a + b)''',
                           user_input='10\n20',
                           projects=get_user_projects(current_user.id))


@app.route('/delete_project/<project_name>', methods=['POST'])
@login_required
def delete_project(project_name):
    theme = request.cookies.get('theme', 'light')
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
    theme = request.cookies.get('theme', 'light')
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
            theme=theme,
            translation_result=translated_text
        )
    else:
        return render_template('translator.html', theme=theme)


@app.route('/menu')
def menu():
    theme = request.cookies.get('theme', 'light')
    return render_template("menu.html", theme=theme)


@app.route('/set_theme', methods=['POST'])
def set_theme():
    theme = request.form.get('theme', 'light')
    resp = make_response(redirect(url_for('menu')))
    resp.set_cookie('theme', theme, max_age=30*24*60*60)
    return resp


@app.route('/logout')
def logout():
    resp = make_response(redirect('/'))
    resp.set_cookie('theme', '', expires=0)
    return resp


@app.route('/music', methods=['GET', 'POST'])
@login_required
def music():
    theme = request.cookies.get('theme', 'light')
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
    return render_template("music.html", theme=theme, existing_files=existing_files)


@app.route("/videos", methods=['GET', 'POST'])
@login_required
def video():
    theme = request.cookies.get('theme', 'light')
    def allowed_file(filename):
        return '.' in filename and \
            filename.rsplit('.', 1)[1].lower() in {'mp4', 'avi', 'mov', 'mkv', 'webm'}
    if request.method == 'POST':
        if 'videoFiles[]' not in request.files:
            flash('No file part', 'error')
            return redirect(request.url)
        files = request.files.getlist('videoFiles[]')
        user_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', str(current_user.id))
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
        return redirect(url_for('video'))
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', str(current_user.id))
    existing_videos = []
    if os.path.exists(user_folder):
        existing_videos = sorted(os.listdir(user_folder))
        existing_videos = [{'filename': f} for f in existing_videos if allowed_file(f)]
    view_video = request.args.get('view')
    return render_template("video.html",
                         theme=theme,
                         existing_videos=existing_videos,
                         view_video=view_video)


@app.route('/add_note', methods=['POST'])
@login_required
def add_note():
    note_title = request.form.get('note_title', '').strip()
    note_content = request.form.get('note_content', '').strip()
    if not note_title or not note_content:
        flash('Заголовок и содержание заметки не могут быть пустыми', 'error')
        return redirect(url_for('notes'))
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(current_user.id))
    os.makedirs(user_folder, exist_ok=True)
    original_title = note_title
    safe_name = safe_filename(note_title)
    if not safe_name:
        safe_name = f"note_{int(time.time())}"

    filename = f"{safe_name}.txt"
    filepath = os.path.join(user_folder, filename)

    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        title_filepath = os.path.join(user_folder, f"{safe_name}.title")
        with open(title_filepath, 'w', encoding='utf-8') as f:
            f.write(original_title)

        flash('Заметка успешно сохранена', 'success')
    except Exception as e:
        flash(f'Ошибка при сохранении заметки: {str(e)}', 'error')

    return redirect(url_for('notes'))


@app.route('/delete_note/<filename>', methods=['POST'])
@login_required
def delete_note(filename):
    theme = request.cookies.get('theme', 'light')
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(current_user.id))
    filepath = os.path.join(user_folder, secure_filename(filename))

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash('Заметка успешно удалена', 'success')
        except Exception as e:
            flash(f'Ошибка при удалении заметки: {str(e)}', 'error')
    else:
        flash('Заметка не найдена', 'error')

    return redirect(url_for('notes'))


@app.route("/notes", methods=['GET', 'POST'])
@login_required
def notes():
    theme = request.cookies.get('theme', 'light')
    notes = get_user_notes(current_user.id)
    return render_template("notes.html", theme=theme, notes=notes)


def get_user_notes(user_id):
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(user_id))
    notes = []
    if os.path.exists(user_folder):
        for filename in os.listdir(user_folder):
            if filename.endswith('.txt'):
                filepath = os.path.join(user_folder, filename)
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    title = filename[:-4] if filename.endswith('.txt') else filename
                    notes.append({
                        'title': title,
                        'content': content,
                        'filename': filename,
                        'editing': False
                    })
                except Exception as e:
                    print(f'Ошибка чтения заметки {filename}: {str(e)}')
    return sorted(notes, key=lambda x: x['title'])


@app.route('/edit_note/<filename>')
@login_required
def edit_note(filename):
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(current_user.id))
    filepath = os.path.join(user_folder, secure_filename(filename))

    if not os.path.exists(filepath):
        flash('Заметка не найдена', 'error')
        return redirect(url_for('notes'))
    notes = get_user_notes(current_user.id)
    for note in notes:
        note['editing'] = (note['filename'] == filename)
    theme = request.cookies.get('theme', 'light')
    return render_template("notes.html", theme=theme, notes=notes)


@app.route('/update_note/<filename>', methods=['POST'])
@login_required
def update_note(filename):
    note_title = request.form.get('note_title', '').strip()
    note_content = request.form.get('note_content', '').strip()
    if not note_title or not note_content:
        flash('Заголовок и содержание заметки не могут быть пустыми', 'error')
        return redirect(url_for('notes'))
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(current_user.id))
    old_filepath = os.path.join(user_folder, secure_filename(filename))
    old_titlepath = os.path.join(user_folder, f"{filename[:-4]}.title")
    safe_name = safe_filename(note_title)
    new_filename = f"{safe_name}.txt"
    new_filepath = os.path.join(user_folder, new_filename)
    new_titlepath = os.path.join(user_folder, f"{safe_name}.title")
    try:
        with open(old_filepath, 'w', encoding='utf-8') as f:
            f.write(note_content)
        with open(old_titlepath, 'w', encoding='utf-8') as f:
            f.write(note_title)
        if old_filepath != new_filepath:
            if os.path.exists(new_filepath):
                flash('Заметка с таким названием уже существует', 'error')
                return redirect(url_for('notes'))
            os.rename(old_filepath, new_filepath)
            os.rename(old_titlepath, new_titlepath)
        flash('Заметка успешно обновлена', 'success')
    except Exception as e:
        flash(f'Ошибка при обновлении заметки: {str(e)}', 'error')
    return redirect(url_for('notes'))


def safe_filename(filename):
    filename = translit(filename, 'ru', reversed=True)
    filename = secure_filename(filename)
    filename = re.sub(r'-+', '-', filename)
    return filename


def translit(text, lang_code, reversed=False):
    trans_dict = {
        'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'yo',
        'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'y', 'к': 'k', 'л': 'l', 'м': 'm',
        'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
        'ф': 'f', 'х': 'h', 'ц': 'ts', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
        'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'yu', 'я': 'ya'
    }

    if reversed:
        text = text.lower()
        for rus, eng in trans_dict.items():
            text = text.replace(eng, rus)
        return text
    else:
        result = []
        for char in text.lower():
            result.append(trans_dict.get(char, char))
        return ''.join(result)


def get_user_notes(user_id):
    user_folder = os.path.join(app.config['NOTES_FOLDER'], str(user_id))
    notes = []

    if os.path.exists(user_folder):
        for filename in os.listdir(user_folder):
            if filename.endswith('.txt') and not filename.endswith('.title'):
                filepath = os.path.join(user_folder, filename)
                title_filepath = os.path.join(user_folder, f"{filename[:-4]}.title")
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        content = f.read()
                    if os.path.exists(title_filepath):
                        with open(title_filepath, 'r', encoding='utf-8') as f:
                            title = f.read()
                    else:
                        title = translit(filename[:-4], 'ru', reversed=True)
                    notes.append({
                        'title': title,
                        'content': content,
                        'filename': filename,
                        'editing': False
                    })
                except Exception as e:
                    print(f'Ошибка чтения заметки {filename}: {str(e)}')

    return sorted(notes, key=lambda x: x['title'])


@app.route('/delete_video/<filename>', methods=['POST'])
@login_required
def delete_video(filename):
    user_folder = os.path.join(app.config['UPLOAD_FOLDER'], 'videos', str(current_user.id))
    filepath = os.path.join(user_folder, secure_filename(filename))

    if os.path.exists(filepath):
        try:
            os.remove(filepath)
            flash(f'Video {filename} successfully deleted', 'success')
        except Exception as e:
            flash(f'Error deleting video: {str(e)}', 'error')
    else:
        flash('Video file not found', 'error')

    return redirect(url_for('video'))


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


@app.route('/books', methods=['GET', 'POST'])
@login_required
def pdf_upload():
    theme = request.cookies.get('theme', 'light')
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

    return render_template("document.html", theme=theme, existing_files=existing_files)


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


@app.route('/community_chat', methods=['GET', 'POST'])
@login_required
def communication():
    theme = request.cookies.get('theme', 'light')
    if request.method == 'POST':
        message_text = request.form.get('message')
        if message_text and message_text.strip():
            new_message = ChatMessage(
                user_id=current_user.id,
                text=message_text.strip()
            )
            db.session.add(new_message)
            db.session.commit()
            return redirect(url_for('communication'))
    messages = db.session.query(ChatMessage, User).join(User).order_by(ChatMessage.id).all()
    formatted_messages = []
    for msg, user in messages:
        formatted_messages.append({
            'text': msg.text,
            'is_current_user': msg.user_id == current_user.id,
            'user': user.email.split('@')[0]
        })
    return render_template("communication.html",
                           theme=theme,
                           messages=formatted_messages)


if __name__ == '__main__':
    with app.app_context():
        db.create_all()
        notes_folder = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static', 'notes')
        os.makedirs(notes_folder, exist_ok=True)
    app.run(port=8080, host='127.0.0.1')