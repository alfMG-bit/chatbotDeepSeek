from flask import Flask, render_template, request, redirect, url_for, session, flash, make_response
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import date, datetime, timedelta
import os, pdfplumber, markdown, pdfkit
from chatbot import promt_analize, chat_with_deepseek
from io import BytesIO
from sqlalchemy.ext.hybrid import hybrid_property



app = Flask(__name__)
app.config['SECRET_KEY'] = '' #write your secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
app.config['UPLOAD_FOLDER'] = 'uploads'

def read_pdf_files(pdf_file):
    full_text = ""
    with pdfplumber.open(pdf_file) as pdf:
        for page in pdf.pages:
            full_text += page.extract_text() + "\n"
    return full_text.strip()

class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.String(100), primary_key=True)
    password = db.Column(db.String(30), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    hierarchy = db.Column(db.String(30), default='estudiante')
    date_birth = db.Column(db.DateTime, nullable=False)

    @hybrid_property
    def age(self):
        hoy = date.today()
        return hoy.year - self.date_birth.year - (
            (hoy.month, hoy.day) < (self.date_birth.month, self.date_birth.day)
        )

    def __repr__(self):
        return f'<User {self.id}>'


class Student(db.Model):
    id = db.Column(db.String(100), db.ForeignKey('user.id'), primary_key = True)
    education_area = db.Column(db.String(100), nullable = False)
    document_type = db.Column(db.String(100), nullable = False)
    times = db.Column(db.Integer, default = 0)

    user = db.relationship('User', backref = db.backref('student', uselist = False))

    def __repr__(self):
        return f'<Student {self.id}>'

class Activity(db.Model):
    id = db.Column(db.String(50), primary_key = True)
    teacher_id = db.Column(db.String(100), db.ForeignKey('user.id'), nullable = False)
    creation_date = db.Column(db.DateTime, default = datetime.utcnow)
    evaluation_content = db.Column(db.Text)
    expiration_date = db.Column(db.DateTime, default = lambda: datetime.utcnow() + timedelta(hours=72))

    teacher = db.relationship('User', backref = 'activities')

    def is_valid(self):
        return datetime.utcnow() < self.expiration_date
    
class StudentSubmission(db.Model):
    id = db.Column(db.Integer, primary_key = True)
    student_id = db.Column(db.String(100), db.ForeignKey('user.id'))
    activity_id = db.Column(db.String(50), db.ForeignKey('activity.id'))
    submission_date = db.Column(db.DateTime, default = datetime.utcnow)
    
    student = db.relationship('User', backref = 'submissions')
    activity = db.relationship('Activity', backref = 'submissions')
    
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods = ['GET','POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        user = User.query.get(email)

        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['user_name'] = user.name
            session['user_hierarchy'] = user.hierarchy
            flash('Login exitoso', 'success')
            
            return redirect(url_for('dashboard'))
        else:
            flash('Correo o contraseña incorrectos', 'danger')

    return render_template('login.html')

@app.route('/register', methods = ['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        confirm_password = request.form['confirm_password']
        date_birth_str = request.form['date_birth']
        date_birth = datetime.strptime(date_birth_str, '%Y-%m-%d')

        errors = []
        if len(password) < 8:
            errors.append("La contraseña debe tener al menos 8 caracteres")
        if not any(c.isupper() for c in password):
            errors.append("La contraseña debe contener al menos una mayúscula")
        if not any(c.isdigit() for c in password):
            errors.append("La contraseña debe contener al menos un número")
        if not any(c in '!@#$%^&*' for c in password):
            errors.append("La contraseña debe contener al menos un carácter especial (!@#$%^&*)")
        
        if errors:
            for error in errors:
                flash(error, 'error')
            return redirect(url_for('register'))

        if password != confirm_password:
            flash('Las contraseñas no coinciden', 'danger')
            return redirect(url_for('register'))
        
        existing_user = User.query.get(email)
        if existing_user:
            flash('Este correo ya está registrado', 'danger')
            return redirect(url_for('register'))
        
        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(id=email, password=hashed_password, name=name, hierarchy='estudiante', date_birth=date_birth)

        db.session.add(new_user)
        db.session.commit()

        flash('Registro exitoso, inice sesión', 'success')
        return redirect(url_for('login'))
    
    return render_template('register.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', name=session.get('user_name'), hierarchy=session.get('user_hierarchy'))

@app.route('/logout')
def logout():
    session.clear()
    flash('Has cerrado sesión', 'info')
    return redirect(url_for('login'))

@app.route('/student_view')
def student_view():
 hierarchy = session.get('user_hierarchy')
 if hierarchy == "estudiante":
     student = Student.query.get(session['user_id'])
     return render_template('student_view.html', student = student)
 
@app.route('/save_student_data', methods = ['POST'])
def save_student_data():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    age_range = request.form.get('age')
    education_area = request.form.get('education_area')
    document_type = request.form.get('doc_type')
    user_id = session['user_id']

    student = Student.query.get(user_id)

    if student:
        student.education_area = education_area
        student.document_type = document_type
        student.times = student.times + 1
    else:
        student = Student(
            id = user_id,
            education_area = education_area,
            document_type = document_type
        )
        db.session.add(student)
    
    try:
        db.session.commit()
        flash('Tus datos se han guardado correctamente', 'success')

        return redirect(url_for('verify_activity'))
    
    except Exception as e:
        db.session.rollback()
        flash('Error al guardar tus datos', 'error')
        print(f"Error: {e}")

@app.route('/analize_document', methods = ['GET','POST'])
def analize_document():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    student_id = Student.query.get(session['user_id'])
    activity_id = session.get('current_activity_id')
    activity = Activity.query.get(activity_id)
    result = None
    pdf_ready = False
    
    if request.method == 'POST':
        
        rubric_content = activity.evaluation_content
        doc_type = student_id.document_type

        file = request.files.get('pdf_file')
        if file and file.filename.endswith('pdf'):
            filename = secure_filename(f"hw_{activity}_{student_id}.pdf")
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            file_content = read_pdf_files(filepath)

            content = promt_analize(doc_type,rubric_content,file_content)
            result = chat_with_deepseek(content)
            
            session['analysis_result'] = result
            pdf_ready = True
            
            if os.path.exists(filepath):
                os.remove(filepath)
            
            return render_template('analize_document.html', result = result, pdf_ready = pdf_ready, activity_id = activity_id)
            
    return render_template('analize_document.html', result = None, pdf_ready = False)

@app.route('/teacher_view', methods = ['GET', 'POST'])
def teacher_view():
    hierarchy = session.get('user_hierarchy')
    if hierarchy != "docente":
        return redirect(url_for('login'))
    if request.method == 'POST':
        
        evaluation_type = request.form.get('evaluation_type')
        activity_id = request.form.get('activity_id')


        if not activity_id or len(activity_id) < 5:
            flash('ID actividad inválido', 'danger')
            return redirect(url_for('teacher_view'))
        
        new_activiy = Activity(
            id = activity_id,
            teacher_id = session['user_id']
        )

        if evaluation_type == 'pdf':
            file = request.files.get('rubric_file')
            if file and file.filename.endswith('.pdf'):
                filename = secure_filename(f"rubric_{activity_id}.pdf")
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                rubric_content = read_pdf_files(filepath)
                new_activiy.evaluation_content = rubric_content
            else:
                flash('Archivo PDF inválido', 'error')
                return redirect(url_for('teacher_view'))
            
        elif evaluation_type == 'text':
            rubric_content = request.form.get('rubric_text')
            if not rubric_content or len(rubric_content) < 50:
                flash('El texto de la rúbrica debe tener al menos 50 caracteres', 'error')
                return redirect(url_for('teacher_view'))
            new_activiy.evaluation_content = rubric_content

        else:
            print("Wrong evaluation type")

        db.session.add(new_activiy)
        db.session.commit()
        flash('Actividad creada exitosamente', 'success')
        return redirect(url_for('teacher_view'))
    
    return render_template('teacher_view.html')
        
@app.route('/verify_activity', methods = ['GET', 'POST'])
def verify_activity():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        teacher_id = request.form.get('teachers_email')
        activity_id = request.form.get('activity_name')

        activity = Activity.query.filter_by(id = activity_id, teacher_id = teacher_id).first()

        if not activity:
            flash(f'Verifica el ID del docente y la actividad, Actividad {activity_id} no encontrada', 'danger')
            return redirect(url_for('verify_activity'))
        
        submission = StudentSubmission(
            student_id = session['user_id'],
            activity_id = activity_id
        )
        session['current_activity_id'] = activity_id
        db.session.add(submission)
        db.session.commit()

        return redirect(url_for('analize_document'))
    
    return render_template('verify_activity.html')

@app.route('/download_analysis')
def download_analysis():
    if 'analysis_result' not in session:
        flash('No hay resultados para descargar','danger')
        return redirect(url_for('analize_document'))
    
    activity_id = session.get('current_activity_id')
    html_content = markdown.markdown(session['analysis_result'])

    options = {
        'encoding': 'UTF-8',
        'quiet': '',
        'margin-top': '10mm',
        'margin-right': '10mm',
        'margin-bottom': '10mm',
        'margin-left': '10mm',
    }
    
    config = pdfkit.configuration(wkhtmltopdf=r'')#write the route for your wkhtmltopdf.exe
    
    pdf = pdfkit.from_string(html_content, False, options=options, configuration=config)
    
    response = make_response(pdf)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=analisis_{activity_id}.pdf'

    return response

if __name__ == '__main__':
    app.run(debug=True)