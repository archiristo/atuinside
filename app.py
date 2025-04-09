from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from flask_migrate import Migrate
import re
import os
from werkzeug.utils import secure_filename
from datetime import datetime
from models import db, ForumTopic, ForumComment, User, Projects,Event
from database import create_app
from sqlalchemy.exc import IntegrityError
from flask_mail import Mail, Message

app = create_app()


@app.route('/')
def index():
    return render_template('index.html')

mail = Mail()
### Mail kısımları birazdan...
def create_app():
    app = Flask(__name__)
    # ...
 #   app.config['MAIL_SERVER'] = 'smtp.gmail.com'
  #  app.config['MAIL_PORT'] = 587
   # app.config['MAIL_USE_TLS'] = True
    #app.config['MAIL_USERNAME'] = 'iriskoca@gmail.com'
    #app.config['MAIL_PASSWORD'] = 'jnah izvb eywm ypeu'  # Google App Password
    #mail.init_app(app)
    return app

def send_notification(to, subject, body):
    msg = Message(subject, recipients=[to], body=body, sender='iriskoca@gmail.com')
    mail.send(msg)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        confirm_password = request.form['confirm-password']

        if not first_name or not last_name:
            return "Ad ve soyad boş bırakılamaz!", 400

        if not re.match(r'^[a-zA-Z0-9._%+-]+@(?:atu\.edu\.tr|ogr\.atu\.edu\.tr)$', email):
            flash('Sadece @atu.edu.tr veya @ogr.atu.edu.tr uzantılı e-postalar kabul edilir.', 'danger')
            return redirect(url_for('register'))
        
        if password != confirm_password:
            flash('Şifreler eşleşmiyor.', 'danger')
            return redirect(url_for('register'))

        # E-posta adresinin zaten kayıtlı olup olmadığını kontrol et
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Bu e-posta zaten kayıtlı!', 'danger')
            return redirect(url_for('register'))

        hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
        new_user = User(email=email, password=hashed_password, first_name=first_name, last_name=last_name)

        # Kullanıcıyı ekle
        db.session.add(new_user)
        
        # Rolu belirle (öğrenci veya öğretmen)
        if re.match(r'^[a-zA-Z0-9._%+-]+@(?:ogr\.atu\.edu\.tr)$', email):
            new_user.role = 'student'
        elif re.match(r'^[a-zA-Z0-9._%+-]+@(?:atu\.edu\.tr)$', email):
            new_user.role = 'teacher'

        # Commit işlemi
        db.session.commit()

        flash('Kayıt başarılı!', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        
        if user and check_password_hash(user.password, password):
            session['user_id'] = user.id
            session['email'] = user.email
            session['first_name'] = user.first_name if user.first_name else "Unknown"
            session['last_name'] = user.last_name if user.last_name else "Unknown"
            
            flash('Giriş başarılı!', 'success')
            
            if email.endswith('@atu.edu.tr'):
                return redirect(url_for('teacher_dashboard'))
                
            elif email.endswith('@ogr.atu.edu.tr'):
                return redirect(url_for('student_dashboard'))
                
        else:
            flash('Geçersiz e-posta veya şifre.', 'danger')
            return redirect(url_for('login'))
    return render_template('login.html')

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'user_id' not in session or not session['email'].endswith('@atu.edu.tr'):
        return redirect(url_for('login'))
    else:
        user = User.query.get(session['user_id'])
        topic = ForumTopic.query.order_by(ForumTopic.created_at.desc()).limit(5).all()
        projects = Projects.query.filter_by(status='open').limit(5).all()
        events = Event.query.all()
        return render_template('teacher_dashboard.html', user=user, events=events, topic=topic, projects=projects)

@app.route('/student_dashboard')
def student_dashboard():
    if 'user_id' not in session or not session['email'].endswith('@ogr.atu.edu.tr'):
        return redirect(url_for('login'))
    else:
        user = User.query.get(session['user_id'])
        topics = ForumTopic.query.order_by(ForumTopic.created_at.desc()).limit(5).all()
        project_announcements = Projects.query.filter_by(status='open').limit(5).all()
        events = Event.query.all()
        return render_template('student_dashboard.html', user=user, topics=topics, project_announcements=project_announcements, events=events)

users = {}  

@app.route('/studentprofile')
def studentprofile():
    if 'user_id' not in session or not session['email'].endswith('@ogr.atu.edu.tr'):
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=session['email']).first()
    name = users.get(session['first_name'], {})
    surname = users.get(session['last_name'], {})
    return render_template('studentprofile.html', user=user, name=name, surname=surname)

@app.route('/teacherprofile')
def teacherprofile():
    if 'user_id' not in session or not session['email'].endswith('@atu.edu.tr'):
        return redirect(url_for('login'))

    user = User.query.filter_by(email=session['email']).first()
    name = users.get(session['first_name'], {})
    surname = users.get(session['last_name'], {})
    return render_template('teacherprofile.html', user=user, name=name, surname=surname)

projects = []  # Tüm proje ilanlarını tutacak liste

@app.route('/create-project', methods=['GET', 'POST'])
def create_project():
    if 'user_id' not in session or not session['email'].endswith('@atu.edu.tr'):
        return redirect(url_for('login'))  # Sadece hocalar proje ekleyebilir

    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        created_by = session.get('first_name', '') + " " + session.get('last_name', '')
        email = session['email']

        new_project = Projects(title=title, description=description, created_by=created_by, status='open')
        db.session.add(new_project)
        db.session.commit()
        students = User.query.filter_by(role='student').all()
        #for student in students:
         #   msg = Message("Yeni Proje Duyurusu!",
          #                sender="iriskoca@gmail.com",
           #               recipients=[student.email])
            #msg.body = f"Yeni bir proje eklendi: {title}"
            #mail.send(msg)
        return redirect(url_for('project_list'))

    return render_template('create_project.html')

@app.route('/projects')
def project_list():
    email = session.get('email', '')

    if email.endswith('@ogr.atu.edu.tr'):
        # Öğrenciler tüm açık ilanları görür
        open_projects = Projects.query.filter_by(status='open').all()
    else:
        # Hocalar sadece kendi ilanlarını görür
        open_projects = Projects.query.filter_by(created_by = session.get('first_name', '') + " " + session.get('last_name', '')).all()

    return render_template('project_list.html', projects=open_projects)


@app.route('/close-project/<int:project_id>')
def close_project(project_id):
    created_by = session.get('first_name', '') + " " + session.get('last_name', '')

    for project in projects:
        if project['id'] == project_id and project['created_by'] == created_by:
            project['status'] = 'closed'
            break

    return redirect(url_for('project_list'))

forum_topics = []  # Forum başlıklarını ve yorumları saklayan liste

UPLOAD_FOLDER = 'static/uploads'

@app.route('/create_topic', methods=['GET', 'POST'])
def create_topic():
    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = session.get('first_name') + " "+ session.get('last_name')

        new_topic = ForumTopic(
            title=title,
            content=content,
            author=author,
        )
        db.session.add(new_topic)
        db.session.commit()
        return redirect('/forum')

    # GET isteğinde kategori listesi vs. dönebilirsin
    return render_template('create_topic.html')


@app.route('/forum')
def forum():
    topics = ForumTopic.query.order_by(ForumTopic.created_at.desc()).all()
    return render_template('forum.html', topics=topics)

@app.route('/topic/<int:topic_id>', methods=['GET', 'POST'])
def view_topic(topic_id):
    topic = ForumTopic.query.get_or_404(topic_id)
    
    if request.method == 'POST':
        comment_text = request.form['comment']
        author = session.get('first_name') + " "+ session.get('last_name')

        new_comment = ForumComment(topic_id=topic.id, author=author, text=comment_text)
        db.session.add(new_comment)
        db.session.commit()
        topic_author = User.query.filter_by(email=topic.author).first()
        if topic_author and topic_author.email != author:  # Kendi yorumuna mail atmasın
            msg = Message("Forumda yeni yorum var!",
                      sender="seninmailin@gmail.com",
                      recipients=[topic_author.email])
            msg.body = f"{topic.title} başlıklı foruma yeni bir yorum geldi."
            mail.send(msg)

    
    comments = ForumComment.query.filter_by(topic_id=topic.id).all()
    return render_template('topic.html', topic=topic, comments=comments)

admins = ["240603045@ogr.atu.edu.tr"]  # Buraya admin e-postalarını ekleyebiliriz

@app.route('/admin')
def admin_panel():
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403  # Eğer admin değilse erişimi engelle
    users = User.query.all()
    projects = Projects.query.all()
    topic = ForumTopic.query.all()
    events = Event.query.all()
    comment = ForumComment.query.all()
    return render_template('admin.html', users=users, projects=projects, topic=topic, events=events, comment=comment)

@app.route('/delete-user/<int:user_id>')
def delete_user(user_id):
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403
    
    user = User.query.get(user_id) # Veritabanından kullanıcıyı çek
    if user:
        db.session.delete(user)
        db.session.commit()  # Kalıcı olarak sil

    return redirect(url_for('admin_panel'))

@app.route('/delete-project/<int:project_id>')
def delete_project(project_id):
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403
    
    projects = Projects.query.get(project_id)
    if projects:
        db.session.delete(projects)
        db.session.commit()

    return redirect(url_for('admin_panel'))

@app.route('/delete-topic/<int:topic_id>')
def delete_topic(topic_id):
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403

    topic = ForumTopic.query.get(topic_id)
    if topic:
        db.session.delete(topic)
        db.session.commit()

    return redirect(url_for('admin_panel'))

@app.route('/delete-comment/<int:comment_id>')
def delete_comment(comment_id):
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403

    comment = ForumComment.query.get(comment_id)
    if comment:
        db.session.delete(comment)
        db.session.commit()

    return redirect(url_for('admin_panel'))

events = []

@app.route('/get-events')
def get_events():
    events = Event.query.all()
    event_list = [
        {
            "id": event.id,
            "title": event.title,
            "start": event.date.strftime("%Y-%m-%d"),  # Doğru tarih alanı
        }
        for event in events
    ]
    return jsonify(event_list)

@app.route('/add-event', methods=['GET', 'POST'])
def add_event():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    elif session['email'] not in admins:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        title = request.form['title']
        date = datetime.strptime(request.form['date'], '%Y-%m-%d')

        new_event = Event(title=title, date=date)
        db.session.add(new_event)
        db.session.commit()

        return redirect(url_for('admin_panel'))

    return render_template('add_event.html')

@app.route('/delete-event/<int:event_id>')
def delete_event(event_id):
    if 'user_id' not in session or session['email'] not in admins:
        return "Yetkisiz erişim!", 403

    events = Event.query.get(event_id)
    if events:
        db.session.delete(events)
        db.session.commit()

    return redirect(url_for('admin_panel'))

if __name__ == '__main__':
    app.run(debug=True)