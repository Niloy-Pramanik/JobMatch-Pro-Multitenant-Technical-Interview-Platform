from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, send_file
from flask_sqlalchemy import SQLAlchemy
from flask_mail import Mail, Message
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime, timedelta
from io import BytesIO
import os
import json
import csv
from sqlalchemy import func, text, and_, or_

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'

# SQLAlchemy Database configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+pymysql://root:sakibonlockdown@localhost:3306/job_matching_system'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# File upload configuration
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'pdf', 'doc', 'docx'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max file size

# Mail configuration
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'your-email@gmail.com'
app.config['MAIL_PASSWORD'] = 'your-app-password'
mail = Mail(app)

@app.context_processor
def inject_datetime():
    return {
        'datetime': datetime,
        'timedelta': timedelta,
        'now': datetime.now()
    }



# --- MODELS ---
class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    user_type = db.Column(db.Enum('candidate', 'employer', 'admin', 'interviewer', 'manager'), nullable=False)
    first_name = db.Column(db.String(100), nullable=False)
    last_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    
    candidate_profile = db.relationship('CandidateProfile', backref='user', uselist=False)
    company = db.relationship('Company', backref='user', uselist=False)


class Company(db.Model):
    __tablename__ = 'companies'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    company_name = db.Column(db.String(255), nullable=False)
    industry = db.Column(db.String(100))
    company_size = db.Column(db.Enum('1-10', '11-50', '51-200', '201-500', '500+'))
    location = db.Column(db.String(255))
    description = db.Column(db.Text)
    website = db.Column(db.String(255))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    job_postings = db.relationship('JobPosting', backref='company', lazy=True)

class CandidateProfile(db.Model):
    __tablename__ = 'candidate_profiles'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    experience_years = db.Column(db.Integer, default=0)
    education_level = db.Column(db.Enum('High School', 'Bachelor', 'Master', 'PhD', 'Other'))
    current_position = db.Column(db.String(255))
    location = db.Column(db.String(255))
    salary_expectation = db.Column(db.Numeric(10, 2))
    cv_file_path = db.Column(db.String(500))
    cv_content = db.Column(db.LargeBinary)
    cv_filename = db.Column(db.String(255))
    cv_mimetype = db.Column(db.String(100))
    summary = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = db.relationship('JobApplication', backref='candidate', lazy=True)

class JobPosting(db.Model):
    __tablename__ = 'job_postings'
    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey('companies.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=False)
    requirements = db.Column(db.Text)
    location = db.Column(db.String(255))
    job_type = db.Column(db.Enum('Full-time', 'Part-time', 'Contract', 'Internship'))
    experience_required = db.Column(db.Integer, default=0)
    salary_min = db.Column(db.Numeric(10, 2))
    salary_max = db.Column(db.Numeric(10, 2))
    application_deadline = db.Column(db.Date)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    applications = db.relationship('JobApplication', backref='job', lazy=True)

class JobApplication(db.Model):
    __tablename__ = 'job_applications'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate_profiles.id'), nullable=False)
    cover_letter = db.Column(db.Text)
    application_status = db.Column(db.Enum('applied', 'under_review', 'shortlisted', 'interview_scheduled', 'rejected', 'hired'), default='applied')
    exam_score = db.Column(db.Numeric(5, 2))
    applied_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

# MCQ Exam Models
class MCQExam(db.Model):
    __tablename__ = 'mcq_exams'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    exam_title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    duration_minutes = db.Column(db.Integer, default=60)
    total_questions = db.Column(db.Integer, default=0)
    passing_score = db.Column(db.Numeric(5, 2), default=60.00)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    questions = db.relationship('MCQQuestion', backref='exam', lazy=True)

class MCQQuestion(db.Model):
    __tablename__ = 'mcq_questions'
    id = db.Column(db.Integer, primary_key=True)
    exam_id = db.Column(db.Integer, db.ForeignKey('mcq_exams.id'), nullable=False)
    question_text = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(500), nullable=False)
    option_b = db.Column(db.String(500), nullable=False)
    option_c = db.Column(db.String(500), nullable=False)
    option_d = db.Column(db.String(500), nullable=False)
    correct_answer = db.Column(db.Enum('A', 'B', 'C', 'D'), nullable=False)
    points = db.Column(db.Integer, default=1)
    difficulty_level = db.Column(db.Enum('Easy', 'Medium', 'Hard'), default='Medium')
    category = db.Column(db.String(100))

class ExamAttempt(db.Model):
    __tablename__ = 'exam_attempts'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate_profiles.id'), nullable=False)
    exam_id = db.Column(db.Integer, db.ForeignKey('mcq_exams.id'), nullable=False)
    score = db.Column(db.Numeric(5, 2))
    total_questions = db.Column(db.Integer)
    correct_answers = db.Column(db.Integer)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    completed_at = db.Column(db.DateTime)
    status = db.Column(db.Enum('in_progress', 'completed', 'abandoned'), default='in_progress')
    time_spent = db.Column(db.Integer)  # in seconds

class CandidateAnswer(db.Model):
    __tablename__ = 'candidate_answers'
    id = db.Column(db.Integer, primary_key=True)
    attempt_id = db.Column(db.Integer, db.ForeignKey('exam_attempts.id'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('mcq_questions.id'), nullable=False)
    selected_answer = db.Column(db.Enum('A', 'B', 'C', 'D'))
    is_correct = db.Column(db.Boolean)
    time_spent = db.Column(db.Integer)  # time spent on this question in seconds

class Skill(db.Model):
    __tablename__ = 'skills'
    id = db.Column(db.Integer, primary_key=True)
    skill_name = db.Column(db.String(100), unique=True, nullable=False)
    category = db.Column(db.String(50))
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class CandidateSkill(db.Model):
    __tablename__ = 'candidate_skills'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate_profiles.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    proficiency_level = db.Column(db.Enum('Beginner', 'Intermediate', 'Advanced', 'Expert'), default='Intermediate')
    years_experience = db.Column(db.Integer, default=0)

class JobRequiredSkill(db.Model):
    __tablename__ = 'job_required_skills'
    id = db.Column(db.Integer, primary_key=True)
    job_id = db.Column(db.Integer, db.ForeignKey('job_postings.id'), nullable=False)
    skill_id = db.Column(db.Integer, db.ForeignKey('skills.id'), nullable=False)
    importance = db.Column(db.Enum('Required', 'Preferred', 'Nice to have'), default='Required')
    min_years_experience = db.Column(db.Integer, default=0)

class Message(db.Model):
    __tablename__ = 'messages'
    id = db.Column(db.Integer, primary_key=True)
    sender_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    receiver_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'))
    subject = db.Column(db.String(255))
    message_text = db.Column(db.Text, nullable=False)
    is_read = db.Column(db.Boolean, default=False)
    sent_at = db.Column(db.DateTime, default=datetime.utcnow)
    thread_id = db.Column(db.String(100))  # For message threading
    attachment_path = db.Column(db.String(500))

class Notification(db.Model):
    __tablename__ = 'notifications'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(255), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.Enum('application', 'message', 'exam', 'job_match', 'system'), default='system')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    action_url = db.Column(db.String(500))

class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    table_name = db.Column(db.String(50), nullable=False)
    operation_type = db.Column(db.Enum('INSERT', 'UPDATE', 'DELETE', 'DOWNLOAD_CV'), nullable=False)  # Added 'DOWNLOAD_CV'
    record_id = db.Column(db.Integer, nullable=False)
    old_values = db.Column(db.Text) # JSON string
    new_values = db.Column(db.Text) # JSON string
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)


class ApplicationStatusHistory(db.Model):
    __tablename__ = 'application_status_history'
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'), nullable=False)
    old_status = db.Column(db.String(50))
    new_status = db.Column(db.String(50), nullable=False)
    changed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    changed_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)


#New models

# Add these new models to main.py

class InterviewRoom(db.Model):
    __tablename__ = 'interview_rooms'
    id = db.Column(db.Integer, primary_key=True)
    room_name = db.Column(db.String(255), nullable=False)
    room_code = db.Column(db.String(50), unique=True, nullable=False)
    job_application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'), nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    duration_minutes = db.Column(db.Integer, default=60)
    status = db.Column(db.Enum('scheduled', 'active', 'completed', 'cancelled'), default='scheduled')
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime)
    ended_at = db.Column(db.DateTime)
    
    application = db.relationship('JobApplication', backref='interview_room')
    participants = db.relationship('InterviewParticipant', backref='room', lazy=True)
    feedback = db.relationship('InterviewFeedback', backref='room', lazy=True)
    code_sessions = db.relationship('CodeSession', backref='room', lazy=True)

class InterviewParticipant(db.Model):
    __tablename__ = 'interview_participants'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('interview_rooms.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.Enum('candidate', 'interviewer', 'observer'), nullable=False)
    joined_at = db.Column(db.DateTime)
    left_at = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=False)
    
    user = db.relationship('User', backref='interview_participations')

class InterviewFeedback(db.Model):
    __tablename__ = 'interview_feedback'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('interview_rooms.id'), nullable=False)
    interviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    candidate_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    technical_score = db.Column(db.Integer)
    communication_score = db.Column(db.Integer)
    problem_solving_score = db.Column(db.Integer)
    overall_rating = db.Column(db.Enum('excellent', 'good', 'average', 'poor'))
    feedback_text = db.Column(db.Text)
    recommendation = db.Column(db.Enum('hire', 'maybe', 'reject'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    interviewer = db.relationship('User', foreign_keys=[interviewer_id])
    candidate = db.relationship('User', foreign_keys=[candidate_id])

class CodeSession(db.Model):
    __tablename__ = 'code_sessions'
    id = db.Column(db.Integer, primary_key=True)
    room_id = db.Column(db.Integer, db.ForeignKey('interview_rooms.id'), nullable=False)
    session_name = db.Column(db.String(255), default='Coding Session')
    language = db.Column(db.String(50), default='javascript')
    code_content = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# Add this new model after the existing models in main.py

class InterviewerRecommendation(db.Model):
    __tablename__ = 'interviewer_recommendations'
    
    id = db.Column(db.Integer, primary_key=True)
    application_id = db.Column(db.Integer, db.ForeignKey('job_applications.id'), nullable=False)
    recommended_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    interviewer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    recommendation_notes = db.Column(db.Text)
    status = db.Column(db.Enum('pending', 'accepted', 'rejected', 'not_selected'), default='pending')  # UPDATED
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    application = db.relationship('JobApplication', backref='interviewer_recommendations')
    recommender = db.relationship('User', foreign_keys=[recommended_by])
    interviewer = db.relationship('User', foreign_keys=[interviewer_id])



# --- UTILITY FUNCTIONS ---
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def create_notification(user_id, title, message, notification_type='system', action_url=None):
    """Create a new notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        action_url=action_url
    )
    db.session.add(notification)
    db.session.commit()

def log_activity(table_name, operation_type, record_id, old_values=None, new_values=None, user_id=None):
    """Log activity for audit trail"""
    activity = ActivityLog(
        table_name=table_name,
        operation_type=operation_type,
        record_id=record_id,
        old_values=json.dumps(old_values) if old_values else None,
        new_values=json.dumps(new_values) if new_values else None,
        user_id=user_id
    )
    db.session.add(activity)
    db.session.commit()

from decimal import Decimal

def calculate_job_match_score(candidate_id, job_id):
    """Calculate match score between candidate and job"""
    candidate = CandidateProfile.query.get(candidate_id)
    job = JobPosting.query.get(job_id)
    
    if not candidate or not job:
        return 0

    score = 0
    max_score = 100

    # Experience match (30 points)
    if candidate.experience_years >= job.experience_required:
        score += 30
    elif candidate.experience_years >= job.experience_required * 0.7:
        score += 20
    elif candidate.experience_years >= job.experience_required * 0.5:
        score += 10

    # Skills match (50 points)
    required_skills = JobRequiredSkill.query.filter_by(job_id=job_id).all()
    candidate_skills = CandidateSkill.query.filter_by(candidate_id=candidate_id).all()
    candidate_skill_ids = [cs.skill_id for cs in candidate_skills]

    if required_skills:
        matched_skills = 0
        total_weight = 0
        for req_skill in required_skills:
            weight = 3 if req_skill.importance == 'Required' else 2 if req_skill.importance == 'Preferred' else 1
            total_weight += weight
            if req_skill.skill_id in candidate_skill_ids:
                matched_skills += weight

        if total_weight > 0:
            score += int((matched_skills / total_weight) * 50)
    else:
        score += 25  # No specific skills required

    # Location match (10 points)
    if candidate.location and job.location:
        if candidate.location.lower() in job.location.lower() or job.location.lower() in candidate.location.lower():
            score += 10
        else:
            score += 5  # Partial match

    # Salary expectation match (10 points) - FIXED LINE
    if candidate.salary_expectation and job.salary_min and job.salary_max:
        # Convert float to Decimal for proper comparison
        multiplier = Decimal('1.2')  # Convert 1.2 to Decimal
        if job.salary_min <= candidate.salary_expectation <= job.salary_max:
            score += 10
        elif candidate.salary_expectation <= job.salary_max * multiplier:
            score += 5

    return min(score, max_score)


# --- ROUTES ---

@app.route('/')
def index():
    # If user is logged in, redirect to their appropriate dashboard
    if 'user_id' in session:
        user_type = session.get('user_type')
        if user_type == 'candidate':
            return redirect(url_for('candidate_dashboard'))
        elif user_type == 'employer':
            return redirect(url_for('employer_dashboard'))
        elif user_type == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif user_type == 'manager':
            return redirect(url_for('manager_dashboard'))
        elif user_type == 'interviewer':
            return redirect(url_for('interviewer_dashboard'))
    
    # For non-logged-in users, show the main landing page
    total_jobs = JobPosting.query.filter_by(is_active=True).count()
    total_companies = Company.query.count()
    total_candidates = CandidateProfile.query.count()
    total_applications = JobApplication.query.count()
    
    recent_jobs = db.session.query(JobPosting, Company).join(Company).filter(
        JobPosting.is_active == True
    ).order_by(JobPosting.created_at.desc()).limit(6).all()
    
    return render_template('index.html',
                          total_jobs=total_jobs,
                          total_companies=total_companies,
                          total_candidates=total_candidates,
                          total_applications=total_applications,
                          recent_jobs=recent_jobs)


@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user_type = request.form['user_type']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form.get('phone', '')
        
        password_hash = generate_password_hash(password)
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already registered. Please use a different email.', 'error')
            return render_template('register.html')
        
        try:
            new_user = User(
                email=email,
                password_hash=password_hash,
                user_type=user_type,
                first_name=first_name,
                last_name=last_name,
                phone=phone
            )
            db.session.add(new_user)
            db.session.flush()
            
            if user_type == 'candidate':
                candidate_profile = CandidateProfile(user_id=new_user.id)
                db.session.add(candidate_profile)
            elif user_type == 'employer':
                company_name = request.form.get('company_name', '')
                company = Company(user_id=new_user.id, company_name=company_name)
                db.session.add(company)
            
            db.session.commit()
            
            # Log activity
            log_activity('users', 'INSERT', new_user.id, 
                        new_values={'email': email, 'user_type': user_type})
            
            # Create welcome notification
            create_notification(new_user.id, 'Welcome!', 
                              f'Welcome to our job matching platform, {first_name}!')
            
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Registration failed: {str(e)}', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        
        user = User.query.filter_by(email=email, is_active=True).first()
        
        if user and check_password_hash(user.password_hash, password):
            # Update last login
            user.last_login = datetime.utcnow()
            db.session.commit()
            
            session['user_id'] = user.id
            session['user_type'] = user.user_type
            session['user_name'] = f"{user.first_name} {user.last_name}"
            
            # Log activity
            log_activity('users', 'UPDATE', user.id,
                        old_values={'last_login': None},
                        new_values={'last_login': user.last_login.isoformat()},
                        user_id=user.id)
            
            # Updated redirect logic for all user types
            if user.user_type == 'candidate':
                return redirect(url_for('candidate_dashboard'))
            elif user.user_type == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif user.user_type == 'interviewer':
                return redirect(url_for('interviewer_dashboard'))
            elif user.user_type == 'manager':
                return redirect(url_for('manager_dashboard'))
            else:  # employer
                return redirect(url_for('employer_dashboard'))
        else:
            flash('Invalid email or password', 'error')
    
    return render_template('login.html')


@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'info')
    return redirect(url_for('index'))

# --- CANDIDATE ROUTES ---

@app.route('/candidate/dashboard')
def candidate_dashboard():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    profile = user.candidate_profile

    # Get recent applications
    applications = db.session.query(JobApplication, JobPosting, Company).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobApplication.candidate_id == profile.id
    ).order_by(JobApplication.applied_at.desc()).limit(5).all()

    # Get smart recommendations based on skills and experience
    recommendations = get_job_recommendations(profile.id)

    # Get notifications
    notifications = Notification.query.filter_by(
        user_id=session['user_id'], is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()

    # Get exam invitations
    exam_invitations = db.session.query(MCQExam, JobPosting, Company).join(
        JobPosting, MCQExam.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        JobApplication, JobApplication.job_id == JobPosting.id
    ).filter(
        JobApplication.candidate_id == profile.id,
        MCQExam.is_active == True,
        ~MCQExam.id.in_(
            db.session.query(ExamAttempt.exam_id).filter_by(
                candidate_id=profile.id, status='completed'
            )
        )
    ).all()

    # ADD THIS: Get upcoming interviews for candidate
    upcoming_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting, Company).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobApplication.candidate_id == profile.id,
        InterviewRoom.status.in_(['scheduled', 'active']),
        InterviewRoom.scheduled_time >= datetime.utcnow()
    ).order_by(InterviewRoom.scheduled_time.asc()).all()

    return render_template('candidate_dashboard.html',
                          user=user,
                          profile=profile,
                          applications=applications,
                          recommendations=recommendations,
                          notifications=notifications,
                          exam_invitations=exam_invitations,
                          upcoming_interviews=upcoming_interviews)  # ADD THIS


def get_job_recommendations(candidate_id):
    """Get personalized job recommendations for a candidate"""
    candidate = CandidateProfile.query.get(candidate_id)
    if not candidate:
        return []
    
    # Get jobs the candidate hasn't applied to
    applied_job_ids = db.session.query(JobApplication.job_id).filter_by(
        candidate_id=candidate_id
    ).subquery()
    
    available_jobs = db.session.query(JobPosting, Company).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobPosting.is_active == True,
        ~JobPosting.id.in_(applied_job_ids)
    ).all()
    
    # Calculate match scores and sort
    job_matches = []
    for job, company in available_jobs:
        match_score = calculate_job_match_score(candidate_id, job.id)
        if match_score > 30:  # Only show jobs with decent match
            job_matches.append({
                'job': job,
                'company': company,
                'match_score': match_score
            })
    
    # Sort by match score
    job_matches.sort(key=lambda x: x['match_score'], reverse=True)
    
    return job_matches[:10]  # Return top 10 matches

@app.route('/candidate/profile', methods=['GET', 'POST'])
def candidate_profile():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    # Get available skills and candidate's current skills
    available_skills = Skill.query.order_by(Skill.category, Skill.skill_name).all()
    candidate_skills = db.session.query(CandidateSkill, Skill).join(Skill).filter(
        CandidateSkill.candidate_id == profile.id
    ).all()
    
    if request.method == 'POST':
        try:
            # Store old values for logging
            old_values = {
                'experience_years': profile.experience_years,
                'education_level': profile.education_level,
                'current_position': profile.current_position,
                'location': profile.location,
                'salary_expectation': float(profile.salary_expectation) if profile.salary_expectation else None,
                'summary': profile.summary
            }
            
            # Update user info
            user.first_name = request.form['first_name']
            user.last_name = request.form['last_name']
            user.phone = request.form.get('phone', '')
            
            # Update candidate profile
            profile.experience_years = int(request.form.get('experience_years', 0))
            profile.education_level = request.form.get('education_level') if request.form.get('education_level') else None
            profile.current_position = request.form.get('current_position', '')
            profile.location = request.form.get('location', '')
            profile.salary_expectation = float(request.form['salary_expectation']) if request.form.get('salary_expectation') else None
            profile.summary = request.form.get('summary', '')
            
            # CRITICAL FIX: Handle CV file upload
            cv_file = request.files.get('cv_file')
            if cv_file and cv_file.filename and allowed_file(cv_file.filename):
                try:
                    # Read file content as binary
                    file_content = cv_file.read()
                    
                    # Save CV to database
                    profile.cv_content = file_content
                    profile.cv_filename = secure_filename(cv_file.filename)
                    profile.cv_mimetype = cv_file.mimetype
                    
                    # Optional: Also save to file system
                    if not os.path.exists(app.config['UPLOAD_FOLDER']):
                        os.makedirs(app.config['UPLOAD_FOLDER'])
                    
                    filename = secure_filename(cv_file.filename)
                    file_path = os.path.join(app.config['UPLOAD_FOLDER'], f"cv_{profile.id}_{filename}")
                    profile.cv_file_path = file_path
                    
                    # Reset file pointer and save to filesystem (optional)
                    cv_file.seek(0)
                    cv_file.save(file_path)
                    
                    flash('CV uploaded successfully!', 'success')
                except Exception as e:
                    flash(f'Error uploading CV: {str(e)}', 'warning')
            
            # Handle skills
            selected_skills = request.form.getlist('skills[]')
            
            # Remove old skills
            CandidateSkill.query.filter_by(candidate_id=profile.id).delete()
            
            # Add new skills
            for skill_id in selected_skills:
                proficiency = request.form.get(f'proficiency_{skill_id}', 'Intermediate')
                years_exp = int(request.form.get(f'years_{skill_id}', 0))
                
                candidate_skill = CandidateSkill(
                    candidate_id=profile.id,
                    skill_id=int(skill_id),
                    proficiency_level=proficiency,
                    years_experience=years_exp
                )
                db.session.add(candidate_skill)
            
            db.session.commit()
            
            # Log activity
            new_values = {
                'experience_years': profile.experience_years,
                'education_level': profile.education_level,
                'current_position': profile.current_position,
                'location': profile.location,
                'salary_expectation': float(profile.salary_expectation) if profile.salary_expectation else None,
                'summary': profile.summary
            }
            
            log_activity('candidate_profiles', 'UPDATE', profile.id,
                        old_values=old_values, new_values=new_values, user_id=session['user_id'])
            
            # Create notification for profile update
            create_notification(session['user_id'], 'Profile Updated',
                              'Your profile has been successfully updated. Check your new job recommendations!',
                              'system', url_for('candidate_recommendations'))
            
            flash('Profile updated successfully! Check your job recommendations.', 'success')
            return redirect(url_for('candidate_recommendations'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {str(e)}', 'error')
    
    return render_template('candidate_profile_edit.html',
                         user=user,
                         profile=profile,
                         available_skills=available_skills,
                         candidate_skills=candidate_skills)



@app.route('/candidate/applications')
def candidate_applications():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    # Get applications with status history
    applications = db.session.query(JobApplication, JobPosting, Company).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobApplication.candidate_id == profile.id
    ).order_by(JobApplication.applied_at.desc()).all()
    
    # Get status history for each application
    application_histories = {}
    for app, job, company in applications:
        history = ApplicationStatusHistory.query.filter_by(
            application_id=app.id
        ).order_by(ApplicationStatusHistory.changed_at.desc()).all()
        application_histories[app.id] = history
    
    return render_template('candidate_applications.html',
                         applications=applications,
                         application_histories=application_histories,
                         user=user,
                         profile=profile)

@app.route('/candidate/recommendations')
def candidate_recommendations():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    recommendations = get_job_recommendations(profile.id)
    
    return render_template('candidate_recommendations.html',
                         recommendations=recommendations,
                         user=user,
                         profile=profile)

@app.route('/candidate/skill_analysis')
def candidate_skill_analysis():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    # Get candidate's skills
    candidate_skills = db.session.query(CandidateSkill, Skill).join(Skill).filter(
        CandidateSkill.candidate_id == profile.id
    ).all()
    
    # Get detailed job analysis
    recommendations = get_job_recommendations(profile.id)
    
    # Analyze skill gaps
    skill_gap_analysis = []
    for rec in recommendations[:5]:  # Top 5 recommendations
        job = rec['job']
        required_skills = db.session.query(JobRequiredSkill, Skill).join(Skill).filter(
            JobRequiredSkill.job_id == job.id
        ).all()
        
        candidate_skill_ids = [cs.skill_id for cs, _ in candidate_skills]
        missing_skills = []
        matching_skills = []
        
        for req_skill, skill in required_skills:
            if skill.id in candidate_skill_ids:
                matching_skills.append({
                    'skill': skill,
                    'importance': req_skill.importance
                })
            else:
                missing_skills.append({
                    'skill': skill,
                    'importance': req_skill.importance
                })
        
        skill_gap_analysis.append({
            'job': job,
            'company': rec['company'],
            'match_score': rec['match_score'],
            'matching_skills': matching_skills,
            'missing_skills': missing_skills
        })
    
    return render_template('candidate_skill_analysis.html',
                         skill_gap_analysis=skill_gap_analysis,
                         candidate_skills=candidate_skills,
                         user=user,
                         profile=profile)


@app.route('/candidate/interviews')
def candidate_interviews():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))

    user = User.query.get(session['user_id'])
    profile = user.candidate_profile

    # Get upcoming interviews
    upcoming_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting, Company).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobApplication.candidate_id == profile.id,
        InterviewRoom.status.in_(['scheduled', 'active']),
        InterviewRoom.scheduled_time >= datetime.utcnow()
    ).order_by(InterviewRoom.scheduled_time.asc()).all()

    # Get past interviews
    past_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting, Company).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).filter(
        JobApplication.candidate_id == profile.id,
        InterviewRoom.status == 'completed'
    ).order_by(InterviewRoom.ended_at.desc()).limit(10).all()

    return render_template('candidate_interviews.html',
                          user=user,
                          profile=profile,
                          upcoming_interviews=upcoming_interviews,
                          past_interviews=past_interviews)


# --- EMPLOYER ROUTES ---

@app.route('/employer/dashboard')
def employer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    # Get job postings with application counts
    job_postings = db.session.query(
        JobPosting,
        func.count(JobApplication.id).label('application_count')
    ).outerjoin(JobApplication).filter(
        JobPosting.company_id == company.id
    ).group_by(JobPosting.id).order_by(JobPosting.created_at.desc()).all()
    
    # Get recent applications
    applications = db.session.query(JobApplication, JobPosting, CandidateProfile, User).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).filter(
        JobPosting.company_id == company.id
    ).order_by(JobApplication.applied_at.desc()).limit(10).all()
    
    # Get notifications
    notifications = Notification.query.filter_by(
        user_id=session['user_id'], is_read=False
    ).order_by(Notification.created_at.desc()).limit(5).all()
    
    # Get analytics data
    analytics = get_employer_analytics(company.id)
    
    return render_template('employer_dashboard.html',
                         user=user,
                         company=company,
                         job_postings=job_postings,
                         applications=applications,
                         notifications=notifications,
                         analytics=analytics)

def get_employer_analytics(company_id):
    """Get analytics data for employer dashboard"""
    # Total applications this month
    current_month = datetime.now().replace(day=1)
    total_applications = db.session.query(JobApplication).join(JobPosting).filter(
        JobPosting.company_id == company_id,
        JobApplication.applied_at >= current_month
    ).count()
    
    # Applications by status
    status_counts = db.session.query(
        JobApplication.application_status,
        func.count(JobApplication.id)
    ).join(JobPosting).filter(
        JobPosting.company_id == company_id
    ).group_by(JobApplication.application_status).all()
    
    # Top performing jobs (by application count)
    top_jobs = db.session.query(
        JobPosting.title,
        func.count(JobApplication.id).label('app_count')
    ).outerjoin(JobApplication).filter(
        JobPosting.company_id == company_id
    ).group_by(JobPosting.id).order_by(func.count(JobApplication.id).desc()).limit(5).all()
    
    return {
        'total_applications': total_applications,
        'status_counts': dict(status_counts),
        'top_jobs': top_jobs
    }

@app.route('/employer/jobs')
def employer_jobs():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    job_postings = db.session.query(
        JobPosting,
        func.count(JobApplication.id).label('application_count')
    ).outerjoin(JobApplication).filter(
        JobPosting.company_id == company.id
    ).group_by(JobPosting.id).order_by(JobPosting.created_at.desc()).all()
    
    return render_template('employer_jobs.html',
                         job_postings=job_postings,
                         user=user,
                         company=company)


@app.route('/employer/job/<int:job_id>/exam', methods=['GET', 'POST'])
def manage_job_exam(job_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    # Verify job belongs to this employer
    job = JobPosting.query.filter_by(id=job_id, company_id=company.id).first()
    if not job:
        flash('Job not found.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    # Get existing exam
    exam = MCQExam.query.filter_by(job_id=job_id).first()
    
    if request.method == 'POST':
        if not exam:
            # Create new exam
            exam = MCQExam(
                job_id=job_id,
                exam_title=request.form.get('exam_title'),
                description=request.form.get('description'),
                duration_minutes=int(request.form.get('duration_minutes', 60)),
                passing_score=float(request.form.get('passing_score', 60.0))
            )
            db.session.add(exam)
        else:
            # Update existing exam
            exam.exam_title = request.form.get('exam_title')
            exam.description = request.form.get('description')
            exam.duration_minutes = int(request.form.get('duration_minutes', 60))
            exam.passing_score = float(request.form.get('passing_score', 60.0))
        
        db.session.commit()
        flash('Exam details saved successfully!', 'success')
        return redirect(url_for('manage_exam_questions', exam_id=exam.id))
    
    return render_template('manage_job_exam.html', job=job, exam=exam)

@app.route('/employer/exam/<int:exam_id>/questions')
def manage_exam_questions(exam_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    # Verify exam belongs to this employer
    exam = db.session.query(MCQExam).join(JobPosting).filter(
        MCQExam.id == exam_id,
        JobPosting.company_id == company.id
    ).first()
    
    if not exam:
        flash('Exam not found.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    questions = MCQQuestion.query.filter_by(exam_id=exam_id).all()
    return render_template('manage_exam_questions.html', exam=exam, questions=questions)

@app.route('/employer/exam/<int:exam_id>/add_question', methods=['GET', 'POST'])
def add_exam_question(exam_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        question = MCQQuestion(
            exam_id=exam_id,
            question_text=request.form.get('question_text'),
            option_a=request.form.get('option_a'),
            option_b=request.form.get('option_b'),
            option_c=request.form.get('option_c'),
            option_d=request.form.get('option_d'),
            correct_answer=request.form.get('correct_answer'),
            points=int(request.form.get('points', 1))
        )
        db.session.add(question)
        db.session.commit()
        flash('Question added successfully!', 'success')
        return redirect(url_for('manage_exam_questions', exam_id=exam_id))
    
    exam = MCQExam.query.get_or_404(exam_id)
    return render_template('add_exam_question.html', exam=exam)


@app.route('/create_job', methods=['GET', 'POST'])
def create_job():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    if request.method == 'GET':
        skills = Skill.query.order_by(Skill.category, Skill.skill_name).all()
        return render_template('create_job.html', skills=skills)
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    if not company:
        flash('Company profile not found', 'error')
        return redirect(url_for('employer_dashboard'))
    
    try:
        new_job = JobPosting(
            company_id=company.id,
            title=request.form['title'],
            description=request.form['description'],
            requirements=request.form.get('requirements', ''),
            location=request.form.get('location', ''),
            job_type=request.form['job_type'],
            experience_required=int(request.form.get('experience_required', 0)),
            salary_min=float(request.form['salary_min']) if request.form.get('salary_min') else None,
            salary_max=float(request.form['salary_max']) if request.form.get('salary_max') else None,
            application_deadline=datetime.strptime(request.form['application_deadline'], '%Y-%m-%d').date() if request.form.get('application_deadline') else None
        )
        
        db.session.add(new_job)
        db.session.flush()
        
        # Add required skills
        required_skills = request.form.getlist('required_skills[]')
        for skill_id in required_skills:
            if skill_id:
                importance = request.form.get(f'importance_{skill_id}', 'Required')
                min_years = int(request.form.get(f'min_years_{skill_id}', 0))
                job_skill = JobRequiredSkill(
                    job_id=new_job.id,
                    skill_id=int(skill_id),
                    importance=importance,
                    min_years_experience=min_years
                )
                db.session.add(job_skill)
        
        # ADDED: Handle exam creation if requested
        create_exam = request.form.get('create_exam') == 'on'
        if create_exam:
            exam_title = request.form.get('exam_title', f'{new_job.title} - Technical Assessment')
            exam_description = request.form.get('exam_description', 'Technical assessment for this position')
            duration_minutes = int(request.form.get('exam_duration', 60))
            passing_score = float(request.form.get('exam_passing_score', 60.0))
            
            new_exam = MCQExam(
                job_id=new_job.id,
                exam_title=exam_title,
                description=exam_description,
                duration_minutes=duration_minutes,
                passing_score=passing_score,
                is_active=True
            )
            db.session.add(new_exam)
            db.session.flush()
            
            # Log exam creation
            log_activity('mcq_exams', 'INSERT', new_exam.id,
                        new_values={'exam_title': exam_title, 'job_id': new_job.id},
                        user_id=session['user_id'])
        
        db.session.commit()
        
        # Log activity
        log_activity('job_postings', 'INSERT', new_job.id,
                    new_values={'title': new_job.title, 'company_id': company.id},
                    user_id=session['user_id'])
        
        # Notify matching candidates
        notify_matching_candidates(new_job.id)
        
        if create_exam:
            flash('Job posted successfully with exam! You can now add questions to the exam.', 'success')
            return redirect(url_for('manage_exam_questions', exam_id=new_exam.id))
        else:
            flash('Job posted successfully!', 'success')
            return redirect(url_for('employer_jobs'))
            
    except Exception as e:
        db.session.rollback()
        flash(f'Error creating job: {str(e)}', 'error')
        return redirect(url_for('create_job'))


def notify_matching_candidates(job_id):
    """Notify candidates who match the job requirements"""
    job = JobPosting.query.get(job_id)
    if not job:
        return
    
    # Get all active candidates
    candidates = CandidateProfile.query.join(User).filter(User.is_active == True).all()
    
    for candidate in candidates:
        match_score = calculate_job_match_score(candidate.id, job_id)
        if match_score >= 70:  # High match threshold
            create_notification(
                candidate.user_id,
                'New Job Match!',
                f'A new job "{job.title}" matches your profile with {match_score}% compatibility!',
                'job_match',
                url_for('job_details', job_id=job_id)
            )

# --- ADMIN ROUTES ---

@app.route('/admin/dashboard')
def admin_dashboard():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    # System statistics
    stats = {
        'total_users': User.query.count(),
        'total_candidates': User.query.filter_by(user_type='candidate').count(),
        'total_employers': User.query.filter_by(user_type='employer').count(),
        'total_jobs': JobPosting.query.count(),
        'active_jobs': JobPosting.query.filter_by(is_active=True).count(),
        'total_applications': JobApplication.query.count(),
        'total_skills': Skill.query.count()
    }
    
    # Recent activity
    recent_activities = ActivityLog.query.order_by(
        ActivityLog.timestamp.desc()
    ).limit(20).all()
    
    # User registration trends (last 30 days)
    thirty_days_ago = datetime.now() - timedelta(days=30)
    daily_registrations = db.session.query(
        func.date(User.created_at).label('date'),
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= thirty_days_ago
    ).group_by(func.date(User.created_at)).all()
    
    return render_template('admin_dashboard.html',
                         stats=stats,
                         recent_activities=recent_activities,
                         daily_registrations=daily_registrations)

@app.route('/admin/users')
def admin_users():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    user_type = request.args.get('user_type', '')
    
    query = User.query
    
    if search:
        query = query.filter(
            or_(
                User.first_name.contains(search),
                User.last_name.contains(search),
                User.email.contains(search)
            )
        )
    
    if user_type:
        query = query.filter(User.user_type == user_type)
    
    users = query.order_by(User.created_at.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin_users.html',
                         users=users,
                         search=search,
                         user_type=user_type)


@app.route('/admin/skills', methods=['GET', 'POST'])
def admin_skills():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_skill':
            skill_name = request.form['skill_name']
            category = request.form['category']
            description = request.form.get('description', '')
            
            existing_skill = Skill.query.filter_by(skill_name=skill_name).first()
            if existing_skill:
                flash('Skill already exists', 'error')
            else:
                new_skill = Skill(
                    skill_name=skill_name,
                    category=category,
                    description=description
                )
                db.session.add(new_skill)
                db.session.commit()
                
                log_activity('skills', 'INSERT', new_skill.id,
                           new_values={'skill_name': skill_name, 'category': category},
                           user_id=session['user_id'])
                
                flash('Skill added successfully', 'success')
        
        elif action == 'bulk_import':
            # Handle CSV upload for bulk skill import
            if 'csv_file' in request.files:
                file = request.files['csv_file']
                if file and file.filename.endswith('.csv'):
                    try:
                        # Process CSV file
                        csv_data = file.read().decode('utf-8')
                        csv_reader = csv.DictReader(csv_data.splitlines())
                        
                        added_count = 0
                        for row in csv_reader:
                            if 'skill_name' in row and row['skill_name']:
                                existing = Skill.query.filter_by(
                                    skill_name=row['skill_name']
                                ).first()
                                
                                if not existing:
                                    new_skill = Skill(
                                        skill_name=row['skill_name'],
                                        category=row.get('category', 'General'),
                                        description=row.get('description', '')
                                    )
                                    db.session.add(new_skill)
                                    added_count += 1
                        
                        db.session.commit()
                        flash(f'Successfully imported {added_count} skills', 'success')
                        
                    except Exception as e:
                        db.session.rollback()
                        flash(f'Error importing skills: {str(e)}', 'error')
    
    # Get skills with pagination
    page = request.args.get('page', 1, type=int)
    category_filter = request.args.get('category', '')
    
    query = Skill.query
    if category_filter:
        query = query.filter(Skill.category == category_filter)
    
    skills = query.order_by(Skill.category, Skill.skill_name).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get unique categories
    categories = db.session.query(Skill.category).distinct().all()
    categories = [cat[0] for cat in categories if cat[0]]
    
    return render_template('admin_skills.html',
                         skills=skills,
                         categories=categories,
                         category_filter=category_filter)

@app.route('/admin/activity_logs')
def admin_activity_logs():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    page = request.args.get('page', 1, type=int)
    table_filter = request.args.get('table', '')
    operation_filter = request.args.get('operation', '')
    
    query = ActivityLog.query
    
    if table_filter:
        query = query.filter(ActivityLog.table_name == table_filter)
    
    if operation_filter:
        query = query.filter(ActivityLog.operation_type == operation_filter)
    
    logs = query.order_by(ActivityLog.timestamp.desc()).paginate(
        page=page, per_page=50, error_out=False
    )
    
    # Get unique table names and operations
    tables = db.session.query(ActivityLog.table_name).distinct().all()
    tables = [table[0] for table in tables]
    
    operations = ['INSERT', 'UPDATE', 'DELETE']
    
    return render_template('admin_activity_logs.html',
                         logs=logs,
                         tables=tables,
                         operations=operations,
                         table_filter=table_filter,
                         operation_filter=operation_filter)

@app.route('/admin/reports')
def admin_reports():
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    # Generate various reports
    reports = {
        'user_growth': get_user_growth_report(),
        'job_statistics': get_job_statistics_report(),
        'application_trends': get_application_trends_report(),
        'skill_demand': get_skill_demand_report()
    }
    
    return render_template('admin_reports.html', reports=reports)

def get_user_growth_report():
    """Generate user growth report"""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    growth_data = db.session.query(
        func.date(User.created_at).label('date'),
        User.user_type,
        func.count(User.id).label('count')
    ).filter(
        User.created_at >= thirty_days_ago
    ).group_by(
        func.date(User.created_at), User.user_type
    ).order_by(func.date(User.created_at)).all()
    
    return growth_data

def get_job_statistics_report():
    """Generate job statistics report"""
    stats = {
        'by_type': db.session.query(
            JobPosting.job_type,
            func.count(JobPosting.id)
        ).group_by(JobPosting.job_type).all(),
        
        'by_location': db.session.query(
            JobPosting.location,
            func.count(JobPosting.id)
        ).group_by(JobPosting.location).order_by(
            func.count(JobPosting.id).desc()
        ).limit(10).all(),
        
        'by_company': db.session.query(
            Company.company_name,
            func.count(JobPosting.id)
        ).join(JobPosting).group_by(Company.id).order_by(
            func.count(JobPosting.id).desc()
        ).limit(10).all()
    }
    
    return stats

def get_application_trends_report():
    """Generate application trends report"""
    thirty_days_ago = datetime.now() - timedelta(days=30)
    
    trends = {
        'daily_applications': db.session.query(
            func.date(JobApplication.applied_at).label('date'),
            func.count(JobApplication.id).label('count')
        ).filter(
            JobApplication.applied_at >= thirty_days_ago
        ).group_by(func.date(JobApplication.applied_at)).all(),
        
        'status_distribution': db.session.query(
            JobApplication.application_status,
            func.count(JobApplication.id)
        ).group_by(JobApplication.application_status).all()
    }
    
    return trends

def get_skill_demand_report():
    """Generate skill demand report"""
    skill_demand = db.session.query(
        Skill.skill_name,
        Skill.category,
        func.count(JobRequiredSkill.id).label('demand_count')
    ).join(JobRequiredSkill).group_by(Skill.id).order_by(
        func.count(JobRequiredSkill.id).desc()
    ).limit(20).all()
    
    return skill_demand

# --- EXPORT ROUTES ---

@app.route('/admin/export/<data_type>')
def admin_export_data(data_type):
    if 'user_id' not in session or session['user_type'] != 'admin':
        return redirect(url_for('login'))
    
    try:
        if data_type == 'users':
            return export_users_csv()
        elif data_type == 'jobs':
            return export_jobs_csv()
        elif data_type == 'applications':
            return export_applications_csv()
        elif data_type == 'skills':
            return export_skills_csv()
        else:
            flash('Invalid export type', 'error')
            return redirect(url_for('admin_reports'))
    
    except Exception as e:
        flash(f'Export failed: {str(e)}', 'error')
        return redirect(url_for('admin_reports'))

def export_users_csv():
    """Export users data to CSV"""
    users = db.session.query(User, CandidateProfile, Company).outerjoin(
        CandidateProfile, User.id == CandidateProfile.user_id
    ).outerjoin(
        Company, User.id == Company.user_id
    ).all()
    
    output = BytesIO()
    output.write('ID,Email,User Type,First Name,Last Name,Phone,Created At,Last Login,Is Active,Experience Years,Education Level,Company Name,Industry\n'.encode())
    
    for user, candidate, company in users:
        row = [
            str(user.id),
            user.email,
            user.user_type,
            user.first_name,
            user.last_name,
            user.phone or '',
            user.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            user.last_login.strftime('%Y-%m-%d %H:%M:%S') if user.last_login else '',
            str(user.is_active),
            str(candidate.experience_years) if candidate else '',
            candidate.education_level or '' if candidate else '',
            company.company_name or '' if company else '',
            company.industry or '' if company else ''
        ]
        output.write(','.join([f'"{field}"' for field in row]).encode() + b'\n')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def export_jobs_csv():
    """Export jobs data to CSV"""
    jobs = db.session.query(JobPosting, Company).join(Company).all()
    
    output = BytesIO()
    output.write('Job ID,Title,Company,Location,Job Type,Experience Required,Salary Min,Salary Max,Created At,Is Active,Applications Count\n'.encode())
    
    for job, company in jobs:
        app_count = JobApplication.query.filter_by(job_id=job.id).count()
        
        row = [
            str(job.id),
            job.title,
            company.company_name,
            job.location or '',
            job.job_type or '',
            str(job.experience_required),
            str(job.salary_min) if job.salary_min else '',
            str(job.salary_max) if job.salary_max else '',
            job.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            str(job.is_active),
            str(app_count)
        ]
        output.write(','.join([f'"{field}"' for field in row]).encode() + b'\n')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'jobs_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def export_applications_csv():
    """Export applications data to CSV"""
    applications = db.session.query(
        JobApplication, JobPosting, Company, CandidateProfile, User
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).all()
    
    output = BytesIO()
    output.write('Application ID,Job Title,Company,Candidate Name,Candidate Email,Status,Applied At,Exam Score\n'.encode())
    
    for app, job, company, candidate, user in applications:
        row = [
            str(app.id),
            job.title,
            company.company_name,
            f"{user.first_name} {user.last_name}",
            user.email,
            app.application_status,
            app.applied_at.strftime('%Y-%m-%d %H:%M:%S'),
            str(app.exam_score) if app.exam_score else ''
        ]
        output.write(','.join([f'"{field}"' for field in row]).encode() + b'\n')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'applications_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

def export_skills_csv():
    """Export skills data to CSV"""
    skills = Skill.query.order_by(Skill.category, Skill.skill_name).all()
    
    output = BytesIO()
    output.write('Skill ID,Skill Name,Category,Description,Usage Count\n'.encode())
    
    for skill in skills:
        usage_count = CandidateSkill.query.filter_by(skill_id=skill.id).count()
        usage_count += JobRequiredSkill.query.filter_by(skill_id=skill.id).count()
        
        row = [
            str(skill.id),
            skill.skill_name,
            skill.category or '',
            skill.description or '',
            str(usage_count)
        ]
        output.write(','.join([f'"{field}"' for field in row]).encode() + b'\n')
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='text/csv',
        as_attachment=True,
        download_name=f'skills_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
    )

# --- EXISTING ROUTES (Updated with new features) ---

@app.route('/jobs')
def browse_jobs():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    location = request.args.get('location', '')
    job_type = request.args.get('job_type', '')
    experience_level = request.args.get('experience_level', '')
    salary_min = request.args.get('salary_min', type=int)
    
    query = db.session.query(JobPosting, Company).join(Company).filter(
        JobPosting.is_active == True
    )
    
    if search:
        query = query.filter(
            or_(
                JobPosting.title.contains(search),
                JobPosting.description.contains(search),
                Company.company_name.contains(search)
            )
        )
    
    if location:
        query = query.filter(JobPosting.location.contains(location))
    
    if job_type:
        query = query.filter(JobPosting.job_type == job_type)
    
    if experience_level:
        exp_ranges = {
            'entry': (0, 2),
            'mid': (3, 7),
            'senior': (8, 15),
            'executive': (15, 50)
        }
        if experience_level in exp_ranges:
            min_exp, max_exp = exp_ranges[experience_level]
            query = query.filter(
                and_(
                    JobPosting.experience_required >= min_exp,
                    JobPosting.experience_required <= max_exp
                )
            )
    
    if salary_min:
        query = query.filter(JobPosting.salary_min >= salary_min)
    
    jobs = query.order_by(JobPosting.created_at.desc()).paginate(
        page=page, per_page=12, error_out=False
    )
    
    return render_template('browse_jobs.html',
                         jobs=jobs,
                         search=search,
                         location=location,
                         job_type=job_type,
                         experience_level=experience_level,
                         salary_min=salary_min)

@app.route('/job/<int:job_id>')
def job_details(job_id):
    job_data = db.session.query(JobPosting, Company).join(Company).filter(
        JobPosting.id == job_id
    ).first()
    
    if not job_data:
        flash('Job not found', 'error')  # Fixed: Added missing closing quote
        return redirect(url_for('browse_jobs'))
    
    job, company = job_data
    
    # Get required skills for this job
    required_skills = db.session.query(JobRequiredSkill, Skill).join(Skill).filter(
        JobRequiredSkill.job_id == job_id
    ).all()
    
    # Check if user has applied
    has_applied = False
    match_score = 0
    if 'user_id' in session and session['user_type'] == 'candidate':
        user = User.query.get(session['user_id'])
        if user.candidate_profile:
            application = JobApplication.query.filter_by(
                job_id=job_id, candidate_id=user.candidate_profile.id
            ).first()
            has_applied = application is not None
            match_score = calculate_job_match_score(user.candidate_profile.id, job_id)
    
    # Get related jobs from same company
    related_jobs = JobPosting.query.filter(
        JobPosting.company_id == company.id,
        JobPosting.id != job_id,
        JobPosting.is_active == True
    ).limit(3).all()
    
    return render_template('job_details.html',
                         job=job,
                         company=company,
                         required_skills=required_skills,
                         has_applied=has_applied,
                         match_score=match_score,
                         related_jobs=related_jobs)


@app.route('/apply/<int:job_id>', methods=['GET', 'POST'])
def apply_job(job_id):
    if 'user_id' not in session or session['user_type'] != 'candidate':
        flash('Please login as a candidate to apply', 'error')
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    if not profile:
        flash('Please complete your profile first', 'error')
        return redirect(url_for('candidate_profile'))
    
    job = JobPosting.query.get_or_404(job_id)
    
    # Check if already applied
    existing_application = JobApplication.query.filter_by(
        job_id=job_id, candidate_id=profile.id
    ).first()
    
    if existing_application:
        flash('You have already applied for this job', 'info')
        return redirect(url_for('job_details', job_id=job_id))
    
    if request.method == 'POST':
        try:
            application = JobApplication(
                job_id=job_id,
                candidate_id=profile.id,
                cover_letter=request.form.get('cover_letter', '')
            )
            
            db.session.add(application)
            db.session.flush()
            
            # Log activity
            log_activity('job_applications', 'INSERT', application.id,
                        new_values={'job_id': job_id, 'candidate_id': profile.id},
                        user_id=session['user_id'])
            
            # Create status history
            status_history = ApplicationStatusHistory(
                application_id=application.id,
                old_status=None,
                new_status='applied',
                changed_by=session['user_id'],
                notes='Initial application submitted'
            )
            db.session.add(status_history)
            
            # Notify employer
            company = job.company
            create_notification(
                company.user_id,
                'New Job Application',
                f'New application received for {job.title} from {user.first_name} {user.last_name}',
                'application',
                url_for('employer_view_application', application_id=application.id)
            )
            
            db.session.commit()
            
            flash('Application submitted successfully!', 'success')
            return redirect(url_for('candidate_applications'))
            
        except Exception as e:
            db.session.rollback()
            flash(f'Error submitting application: {str(e)}', 'error')
    
    return render_template('apply_job.html', job=job, profile=profile)

# MCQ Exam Routes
@app.route('/exam/<int:exam_id>')
def take_exam(exam_id):
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    profile = user.candidate_profile
    
    exam = MCQExam.query.get_or_404(exam_id)
    
    # Check if already completed
    existing_attempt = ExamAttempt.query.filter_by(
        candidate_id=profile.id, exam_id=exam_id, status='completed'
    ).first()
    
    if existing_attempt:
        flash('You have already completed this exam', 'info')
        return redirect(url_for('exam_result', attempt_id=existing_attempt.id))
    
    # Get or create in-progress attempt
    attempt = ExamAttempt.query.filter_by(
        candidate_id=profile.id, exam_id=exam_id, status='in_progress'
    ).first()
    
    if not attempt:
        attempt = ExamAttempt(
            candidate_id=profile.id,
            exam_id=exam_id,
            total_questions=exam.total_questions
        )
        db.session.add(attempt)
        db.session.commit()
    
    # Get questions
    questions = MCQQuestion.query.filter_by(exam_id=exam_id).all()
    
    # Get already answered questions
    answered = db.session.query(CandidateAnswer.question_id).filter_by(
        attempt_id=attempt.id
    ).all()
    answered_ids = [q[0] for q in answered]
    
    return render_template('take_exam.html',
                         exam=exam,
                         attempt=attempt,
                         questions=questions,
                         answered_ids=answered_ids)

@app.route('/exam/submit', methods=['POST'])
def submit_exam():
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    attempt_id = request.form['attempt_id']
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    
    if attempt.status == 'completed':
        flash('Exam already submitted', 'info')
        return redirect(url_for('exam_result', attempt_id=attempt_id))
    
    try:
        # Process answers
        questions = MCQQuestion.query.filter_by(exam_id=attempt.exam_id).all()
        correct_answers = 0
        
        for question in questions:
            selected_answer = request.form.get(f'question_{question.id}')
            if selected_answer:
                is_correct = selected_answer == question.correct_answer
                if is_correct:
                    correct_answers += 1
                
                # Save answer
                answer = CandidateAnswer(
                    attempt_id=attempt.id,
                    question_id=question.id,
                    selected_answer=selected_answer,
                    is_correct=is_correct
                )
                db.session.add(answer)
        
        # Calculate score
        score = (correct_answers / len(questions)) * 100 if questions else 0
        
        # Update attempt
        attempt.completed_at = datetime.utcnow()
        attempt.status = 'completed'
        attempt.correct_answers = correct_answers
        attempt.score = score
        attempt.time_spent = (datetime.utcnow() - attempt.started_at).total_seconds()
        
        # Update job application with exam score
        application = JobApplication.query.filter_by(
            candidate_id=attempt.candidate_id
        ).join(JobPosting).filter(
            JobPosting.id == attempt.exam.job_id
        ).first()
        
        if application:
            application.exam_score = score
        
        db.session.commit()
        
        flash('Exam submitted successfully!', 'success')
        return redirect(url_for('exam_result', attempt_id=attempt_id))
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error submitting exam: {str(e)}', 'error')
        return redirect(url_for('take_exam', exam_id=attempt.exam_id))

@app.route('/exam/result/<int:attempt_id>')
def exam_result(attempt_id):
    if 'user_id' not in session or session['user_type'] != 'candidate':
        return redirect(url_for('login'))
    
    attempt = ExamAttempt.query.get_or_404(attempt_id)
    exam = attempt.exam
    
    # Get detailed results
    answers = db.session.query(CandidateAnswer, MCQQuestion).join(MCQQuestion).filter(
        CandidateAnswer.attempt_id == attempt_id
    ).all()
    
    return render_template('exam_result.html',
                         attempt=attempt,
                         exam=exam,
                         answers=answers)

# Employer Application Management
@app.route('/employer/applications')
def employer_applications():
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    company = user.company
    
    # Check if company exists
    if not company:
        flash('Company profile not found. Please complete your company profile first.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    # Get applications with filters
    status_filter = request.args.get('status', '')
    job_filter = request.args.get('job_id', '')
    
    query = db.session.query(JobApplication, JobPosting, CandidateProfile, User).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).filter(
        JobPosting.company_id == company.id
    )

    if status_filter:
        query = query.filter(JobApplication.application_status == status_filter)
    
    if job_filter:
        query = query.filter(JobPosting.id == int(job_filter))
    
    applications = query.order_by(JobApplication.applied_at.desc()).all()
    
    # Get company jobs for filter
    company_jobs = JobPosting.query.filter_by(company_id=company.id).all()
    
    return render_template('employer_applications.html',
        applications=applications,
        company_jobs=company_jobs,
        company=company,  # ADD THIS LINE
        user=user,        # ADD THIS LINE TOO (for consistency)
        status_filter=status_filter,
        job_filter=job_filter)


@app.route('/employer/application/<int:application_id>')
def employer_view_application(application_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    application_data = db.session.query(
        JobApplication, JobPosting, CandidateProfile, User
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).filter(
        JobApplication.id == application_id
    ).first()
    
    if not application_data:
        flash('Application not found', 'error')
        return redirect(url_for('employer_applications'))
    
    application, job, candidate, user = application_data
    
    # Verify this application belongs to employer's company
    employer = User.query.get(session['user_id'])
    if job.company_id != employer.company.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('employer_applications'))
    
    # Get candidate skills
    candidate_skills = db.session.query(CandidateSkill, Skill).join(Skill).filter(
        CandidateSkill.candidate_id == candidate.id
    ).all()
    
    # Get job required skills
    required_skills = db.session.query(JobRequiredSkill, Skill).join(Skill).filter(
        JobRequiredSkill.job_id == job.id
    ).all()
    
    # Get application status history
    status_history = ApplicationStatusHistory.query.filter_by(
        application_id=application_id
    ).order_by(ApplicationStatusHistory.changed_at.desc()).all()
    
    # Calculate match score
    match_score = calculate_job_match_score(candidate.id, job.id)
    
    # NEW: Get available interviewers for recommendation
    available_interviewers = User.query.filter_by(
        user_type='interviewer', is_active=True
    ).all()
    
    # NEW: Get existing interviewer recommendations
    interviewer_recommendations = InterviewerRecommendation.query.filter_by(
        application_id=application_id
    ).all()
    
    return render_template('employer_view_application.html',
                         application=application,
                         job=job,
                         candidate=candidate,
                         user=user,
                         candidate_skills=candidate_skills,
                         required_skills=required_skills,
                         status_history=status_history,
                         match_score=match_score,
                         available_interviewers=available_interviewers,
                         interviewer_recommendations=interviewer_recommendations)


@app.route('/employer/application/<int:application_id>/update_status', methods=['POST'])
def update_application_status(application_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    application = JobApplication.query.get_or_404(application_id)
    
    # Verify ownership
    employer = User.query.get(session['user_id'])
    if application.job.company_id != employer.company.id:
        flash('Unauthorized access', 'error')
        return redirect(url_for('employer_applications'))
    
    old_status = application.application_status
    new_status = request.form['status']
    notes = request.form.get('notes', '')
    
    try:
        # Update application status
        application.application_status = new_status
        
        # Create status history
        status_history = ApplicationStatusHistory(
            application_id=application_id,
            old_status=old_status,
            new_status=new_status,
            changed_by=session['user_id'],
            notes=notes
        )
        db.session.add(status_history)
        
        # Log activity
        log_activity('job_applications', 'UPDATE', application_id,
                    old_values={'application_status': old_status},
                    new_values={'application_status': new_status},
                    user_id=session['user_id'])
        
        # Notify candidate
        candidate_user = application.candidate.user
        create_notification(
            candidate_user.id,
            'Application Status Updated',
            f'Your application for {application.job.title} has been updated to: {new_status}',
            'application',
            url_for('candidate_applications')
        )
        
        db.session.commit()
        
        flash('Application status updated successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error updating status: {str(e)}', 'error')
    
    return redirect(url_for('employer_view_application', application_id=application_id))

@app.route('/employer/download_cv/<int:candidate_id>')
def download_cv(candidate_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    # Get candidate profile
    candidate = CandidateProfile.query.get_or_404(candidate_id)
    
    # Verify employer has access to this candidate's CV (through applications)
    employer = User.query.get(session['user_id'])
    company = employer.company
    
    # Check if there's an application from this candidate to any of the employer's jobs
    application_exists = db.session.query(JobApplication).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).filter(
        JobApplication.candidate_id == candidate_id,
        JobPosting.company_id == company.id
    ).first()
    
    if not application_exists:
        flash('You do not have permission to download this CV', 'error')
        return redirect(url_for('employer_applications'))
    
    # Check if CV exists
    if not candidate.cv_content or not candidate.cv_filename:
        flash('CV not found for this candidate', 'error')
        return redirect(url_for('employer_applications'))
    
    try:
        # Create BytesIO object from CV content
        cv_file = BytesIO(candidate.cv_content)
        
        # Log the download activity
        log_activity('candidate_profiles', 'DOWNLOAD_CV', candidate_id,
                    new_values={'downloaded_by': session['user_id']},
                    user_id=session['user_id'])
        
        # Return the file
        return send_file(
            cv_file,
            mimetype=candidate.cv_mimetype or 'application/pdf',
            as_attachment=True,
            download_name=candidate.cv_filename
        )
    except Exception as e:
        flash(f'Error downloading CV: {str(e)}', 'error')
        return redirect(url_for('employer_applications'))

@app.route('/employer/recommend_interviewer/<int:application_id>', methods=['POST'])
def recommend_interviewer(application_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    # Verify application belongs to employer
    application = db.session.query(JobApplication).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).filter(
        JobApplication.id == application_id,
        JobPosting.company_id == User.query.get(session['user_id']).company.id
    ).first()
    
    if not application:
        flash('Application not found or unauthorized access', 'error')
        return redirect(url_for('employer_applications'))
    
    interviewer_id = request.form.get('interviewer_id')
    recommendation_notes = request.form.get('recommendation_notes', '')
    
    if not interviewer_id:
        flash('Please select an interviewer', 'error')
        return redirect(url_for('employer_view_application', application_id=application_id))
    
    # Check if recommendation already exists
    existing_recommendation = InterviewerRecommendation.query.filter_by(
        application_id=application_id,
        interviewer_id=interviewer_id,
        status='pending'
    ).first()
    
    if existing_recommendation:
        flash('Recommendation already sent to this interviewer', 'warning')
        return redirect(url_for('employer_view_application', application_id=application_id))
    
    try:
        # Create recommendation (pending)
        recommendation = InterviewerRecommendation(
            application_id=application_id,
            recommended_by=session['user_id'],
            interviewer_id=int(interviewer_id),
            recommendation_notes=recommendation_notes,
            status='pending'
        )
        
        db.session.add(recommendation)
        db.session.flush()
        
        # Log activity
        log_activity('interviewer_recommendations', 'INSERT', recommendation.id,
            new_values={
                'application_id': application_id,
                'interviewer_id': interviewer_id,
                'recommended_by': session['user_id']
            },
            user_id=session['user_id'])

        # Notify ADMIN/MANAGER (not interviewer)
        interviewer = User.query.get(interviewer_id)
        employer = User.query.get(session['user_id'])
        admins = User.query.filter(User.user_type.in_(['admin', 'manager'])).all()
        for admin in admins:
            create_notification(
                admin.id,
                'New Interviewer Recommendation',
                f'Employer {employer.first_name} {employer.last_name} has recommended {interviewer.first_name} {interviewer.last_name} for interviewing candidate {application.candidate.user.first_name} {application.candidate.user.last_name} (Job: {application.job.title}).',
                'system',
                url_for('schedule_interview', application_id=application_id)
            )
        db.session.commit()
        flash('Interviewer recommendation submitted to manager for approval and scheduling.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending recommendation: {str(e)}', 'error')
    return redirect(url_for('employer_view_application', application_id=application_id))


# REMOVE these two routes: interviewer_recommendations and respond_to_recommendation
# They are NOT needed in the new workflow, as interviewers no longer see/respond to recommendations.

# If needed, you can also remove the interviewer_recommendations.html template as it is now obsolete.


@app.route('/admin/interviewer_recommendations')
def manage_interviewer_recommendations():
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))
    
    # Get all recommendations with details
    recommendations = db.session.query(
        InterviewerRecommendation, JobApplication, JobPosting, Company, CandidateProfile, User
    ).join(
        JobApplication, InterviewerRecommendation.application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).order_by(InterviewerRecommendation.created_at.desc()).all()
    
    return render_template('admin/interviewer_recommendations.html', recommendations=recommendations)



#MCQ Question related routes can be added here as needed

@app.route('/employer/exam/question/<int:question_id>/edit', methods=['GET', 'POST'])
def edit_exam_question(question_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    question = MCQQuestion.query.get_or_404(question_id)
    exam = question.exam
    
    # Verify this question belongs to this employer
    user = User.query.get(session['user_id'])
    company = user.company
    
    exam_check = db.session.query(MCQExam).join(JobPosting).filter(
        MCQExam.id == exam.id,
        JobPosting.company_id == company.id
    ).first()
    
    if not exam_check:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    if request.method == 'POST':
        question.question_text = request.form.get('question_text')
        question.option_a = request.form.get('option_a')
        question.option_b = request.form.get('option_b')
        question.option_c = request.form.get('option_c')
        question.option_d = request.form.get('option_d')
        question.correct_answer = request.form.get('correct_answer')
        question.points = int(request.form.get('points', 1))
        question.difficulty_level = request.form.get('difficulty_level', 'Medium')
        question.category = request.form.get('category')
        
        db.session.commit()
        flash('Question updated successfully!', 'success')
        return redirect(url_for('manage_exam_questions', exam_id=exam.id))
    
    return render_template('edit_exam_question.html', question=question, exam=exam)

@app.route('/employer/exam/question/<int:question_id>/delete', methods=['POST'])
def delete_exam_question(question_id):
    if 'user_id' not in session or session['user_type'] != 'employer':
        return redirect(url_for('login'))
    
    question = MCQQuestion.query.get_or_404(question_id)
    exam = question.exam
    
    # Verify this question belongs to this employer
    user = User.query.get(session['user_id'])
    company = user.company
    
    exam_check = db.session.query(MCQExam).join(JobPosting).filter(
        MCQExam.id == exam.id,
        JobPosting.company_id == company.id
    ).first()
    
    if not exam_check:
        flash('Unauthorized access.', 'error')
        return redirect(url_for('employer_dashboard'))
    
    try:
        # Update total questions count in exam
        exam.total_questions = max(0, exam.total_questions - 1)
        
        db.session.delete(question)
        db.session.commit()
        
        flash('Question deleted successfully!', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting question: {str(e)}', 'error')
    
    return redirect(url_for('manage_exam_questions', exam_id=exam.id))



# Messaging System
@app.route('/messages')
def messages():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get conversations (grouped messages)
    conversations = db.session.query(
        Message.thread_id,
        func.max(Message.sent_at).label('last_message_time'),
        func.count(Message.id).label('message_count'),
        func.sum(func.case([(Message.is_read == False, 1)], else_=0)).label('unread_count')
    ).filter(
        or_(Message.sender_id == session['user_id'], Message.receiver_id == session['user_id'])
    ).group_by(Message.thread_id).order_by(func.max(Message.sent_at).desc()).all()
    
    # Get latest message for each conversation
    conversation_details = []
    for conv in conversations:
        latest_message = Message.query.filter_by(thread_id=conv.thread_id).order_by(
            Message.sent_at.desc()
        ).first()
        
        # Get other participant
        other_user_id = latest_message.receiver_id if latest_message.sender_id == session['user_id'] else latest_message.sender_id
        other_user = User.query.get(other_user_id)
        
        conversation_details.append({
            'thread_id': conv.thread_id,
            'other_user': other_user,
            'latest_message': latest_message,
            'unread_count': conv.unread_count,
            'last_time': conv.last_message_time
        })
    
    return render_template('messages.html', conversations=conversation_details)

@app.route('/messages/<thread_id>')
def view_conversation(thread_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Get all messages in thread
    messages = db.session.query(Message, User).join(
        User, Message.sender_id == User.id
    ).filter(
        Message.thread_id == thread_id,
        or_(Message.sender_id == session['user_id'], Message.receiver_id == session['user_id'])
    ).order_by(Message.sent_at.asc()).all()
    
    if not messages:
        flash('Conversation not found', 'error')
        return redirect(url_for('messages'))
    
    # Mark messages as read
    Message.query.filter(
        Message.thread_id == thread_id,
        Message.receiver_id == session['user_id'],
        Message.is_read == False
    ).update({'is_read': True})
    db.session.commit()
    
    # Get other participant
    first_message = messages[0][0]
    other_user_id = first_message.receiver_id if first_message.sender_id == session['user_id'] else first_message.sender_id
    other_user = User.query.get(other_user_id)
    
    return render_template('conversation.html',
                         messages=messages,
                         thread_id=thread_id,
                         other_user=other_user)

@app.route('/send_message', methods=['POST'])
def send_message():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    receiver_id = request.form['receiver_id']
    message_text = request.form['message_text']
    thread_id = request.form.get('thread_id')
    
    # Generate thread_id if not provided
    if not thread_id:
        thread_id = f"{min(session['user_id'], int(receiver_id))}_{max(session['user_id'], int(receiver_id))}"
    
    try:
        message = Message(
            sender_id=session['user_id'],
            receiver_id=receiver_id,
            message_text=message_text,
            thread_id=thread_id
        )
        
        db.session.add(message)
        
        # Create notification for receiver
        sender = User.query.get(session['user_id'])
        create_notification(
            int(receiver_id),
            'New Message',
            f'You have a new message from {sender.first_name} {sender.last_name}',
            'message',
            url_for('view_conversation', thread_id=thread_id)
        )
        
        db.session.commit()
        flash('Message sent successfully', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error sending message: {str(e)}', 'error')
    
    return redirect(url_for('view_conversation', thread_id=thread_id))

# Notifications
from datetime import datetime, timedelta
# ...

@app.route('/notifications')
def notifications():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # --- filtering & pagination -------------------------------
    page        = request.args.get('page', 1, type=int)
    base_q      = Notification.query.filter_by(user_id=session['user_id'])
    if request.args.get('filter') == 'unread':
        base_q = base_q.filter_by(is_read=False)
    if request.args.get('type'):
        base_q = base_q.filter_by(notification_type=request.args['type'])

    notifications = base_q.order_by(Notification.created_at.desc()) \
                          .paginate(page=page, per_page=20, error_out=False)

    # --- date cut-offs that the template will use --------------
    now            = datetime.utcnow()
    today_start    = now.replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start= today_start - timedelta(days=1)
    week_ago       = today_start - timedelta(days=7)

    return render_template(
        'notifications.html',
        notifications   = notifications,
        today_start     = today_start,
        yesterday_start = yesterday_start,
        week_ago        = week_ago
    )

@app.route('/notifications/mark_read/<int:notification_id>')
def mark_notification_read(notification_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    notification = Notification.query.filter_by(
        id=notification_id, user_id=session['user_id']
    ).first()
    
    if notification:
        notification.is_read = True
        db.session.commit()
        
        if notification.action_url:
            return redirect(notification.action_url)
    
    return redirect(url_for('notifications'))

#New routes
# Admin/Manager Routes for Interview Management

@app.route('/admin/interviewers', methods=['GET', 'POST'])
def manage_interviewers():
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        # Add new interviewer
        email = request.form['email']
        password = request.form['password']
        first_name = request.form['first_name']
        last_name = request.form['last_name']
        phone = request.form.get('phone', '')
        
        existing_user = User.query.filter_by(email=email).first()
        if existing_user:
            flash('Email already exists', 'error')
        else:
            password_hash = generate_password_hash(password)
            new_interviewer = User(
                email=email,
                password_hash=password_hash,
                user_type='interviewer',
                first_name=first_name,
                last_name=last_name,
                phone=phone
            )
            db.session.add(new_interviewer)
            db.session.commit()
            flash('Interviewer added successfully', 'success')
            
    interviewers = User.query.filter_by(user_type='interviewer').all()
    return render_template('admin/manage_interviewers.html', interviewers=interviewers)

@app.route('/admin/schedule_interview/<int:application_id>', methods=['GET', 'POST'])
def schedule_interview(application_id):
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))

    application = JobApplication.query.get_or_404(application_id)

    if request.method == 'POST':
        try:
            # Parse datetime without any time restrictions
            scheduled_time_str = request.form['scheduled_time']
            scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%dT%H:%M')

            # Generate unique room code
            room_code = f"INT{application_id}{int(datetime.now().timestamp())}"

            # Create interview room with any datetime
            interview_room = InterviewRoom(
                room_name=f"Interview - {application.job.title}",
                room_code=room_code,
                job_application_id=application_id,
                scheduled_time=scheduled_time,
                duration_minutes=int(request.form.get('duration_minutes', 60)),
                created_by=session['user_id']
            )

            db.session.add(interview_room)
            db.session.flush()

            # Add candidate as participant
            candidate_participant = InterviewParticipant(
                room_id=interview_room.id,
                user_id=application.candidate.user_id,
                role='candidate'
            )
            db.session.add(candidate_participant)

            # Add selected interviewers
            interviewer_ids = request.form.getlist('interviewer_ids[]')
            for interviewer_id in interviewer_ids:
                interviewer_participant = InterviewParticipant(
                    room_id=interview_room.id,
                    user_id=int(interviewer_id),
                    role='interviewer'
                )
                db.session.add(interviewer_participant)

            # UPDATE RECOMMENDATION STATUS
            # Mark selected recommendations as 'accepted' and non-selected as 'not_selected'
            recommendations = InterviewerRecommendation.query.filter_by(
                application_id=application_id, 
                status='pending'
            ).all()

            for rec in recommendations:
                if str(rec.interviewer_id) in interviewer_ids:
                    rec.status = 'accepted'
                else:
                    rec.status = 'not_selected'

            db.session.commit()

            # Send notifications
            create_notification(
                application.candidate.user_id,
                'Interview Scheduled',
                f'Your interview for {application.job.title} has been scheduled for {scheduled_time.strftime("%B %d, %Y at %I:%M %p")}',
                'system',
                url_for('join_interview', room_code=room_code)
            )

            for interviewer_id in interviewer_ids:
                create_notification(
                    int(interviewer_id),
                    'Interview Assignment',
                    f'You have been assigned to interview for {application.job.title} on {scheduled_time.strftime("%B %d, %Y at %I:%M %p")}',
                    'system',
                    url_for('join_interview', room_code=room_code)
                )

            flash('Interview scheduled successfully for 24/7 availability!', 'success')
            return redirect(url_for('admin_dashboard'))

        except ValueError as e:
            flash('Invalid date/time format. Please try again.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error scheduling interview: {str(e)}', 'error')

    # GET REQUEST: Fetch data for the template
    interviewers = User.query.filter_by(user_type='interviewer').all()
    
    # FETCH RECOMMENDATIONS FOR THIS APPLICATION
    recommended_interviewers = db.session.query(InterviewerRecommendation).join(
        User, InterviewerRecommendation.interviewer_id == User.id
    ).filter(
        InterviewerRecommendation.application_id == application_id,
        InterviewerRecommendation.status == 'pending'
    ).all()

    return render_template('admin/schedule_interview.html',
                         application=application,
                         interviewers=interviewers,
                         recommended_interviewers=recommended_interviewers)  # ADD THIS LINE



# Edit Interview Route
@app.route('/admin/edit_interview/<int:interview_id>', methods=['GET', 'POST'])
def edit_interview(interview_id):
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))

    interview_room = InterviewRoom.query.get_or_404(interview_id)
    
    # Get all participants for this interview
    participants = db.session.query(InterviewParticipant, User).join(User).filter(
        InterviewParticipant.room_id == interview_room.id
    ).all()
    
    if request.method == 'POST':
        try:
            # Parse the updated datetime
            scheduled_time_str = request.form['scheduled_time']
            scheduled_time = datetime.strptime(scheduled_time_str, '%Y-%m-%dT%H:%M')
            
            # Store old values for logging
            old_values = {
                'scheduled_time': interview_room.scheduled_time.isoformat(),
                'duration_minutes': interview_room.duration_minutes,
                'status': interview_room.status
            }
            
            # Update interview room details - NO TIME RESTRICTIONS for 24/7 scheduling
            interview_room.scheduled_time = scheduled_time
            interview_room.duration_minutes = int(request.form.get('duration_minutes', 60))
            interview_room.status = request.form.get('status', 'scheduled')
            
            # Handle interviewer updates
            new_interviewer_ids = request.form.getlist('interviewer_ids[]')
            
            # Remove existing interviewers (keep candidate)
            InterviewParticipant.query.filter_by(
                room_id=interview_room.id,
                role='interviewer'
            ).delete()
            
            # Add new interviewers
            for interviewer_id in new_interviewer_ids:
                interviewer_participant = InterviewParticipant(
                    room_id=interview_room.id,
                    user_id=int(interviewer_id),
                    role='interviewer'
                )
                db.session.add(interviewer_participant)
            
            db.session.commit()
            
            # Log activity
            new_values = {
                'scheduled_time': interview_room.scheduled_time.isoformat(),
                'duration_minutes': interview_room.duration_minutes,
                'status': interview_room.status
            }
            
            log_activity('interview_rooms', 'UPDATE', interview_room.id,
                        old_values=old_values, new_values=new_values, 
                        user_id=session['user_id'])
            
            # Send update notifications to all participants
            candidate_participant = next((p for p, u in participants if p.role == 'candidate'), None)
            if candidate_participant:
                create_notification(
                    candidate_participant.user_id,
                    'Interview Updated',
                    f'Your interview for {interview_room.application.job.title} has been rescheduled to {scheduled_time.strftime("%B %d, %Y at %I:%M %p")}',
                    'system',
                    url_for('join_interview', room_code=interview_room.room_code)
                )
            
            # Notify new interviewers
            for interviewer_id in new_interviewer_ids:
                create_notification(
                    int(interviewer_id),
                    'Interview Updated',
                    f'Interview assignment updated for {interview_room.application.job.title} - {scheduled_time.strftime("%B %d, %Y at %I:%M %p")}',
                    'system',
                    url_for('join_interview', room_code=interview_room.room_code)
                )
            
            flash('Interview updated successfully!', 'success')
            return redirect(url_for('manage_interviews'))
            
        except ValueError as e:
            flash('Invalid date/time format. Please try again.', 'error')
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating interview: {str(e)}', 'error')
    
    # Get all interviewers for selection
    all_interviewers = User.query.filter_by(user_type='interviewer').all()
    
    # Get current interviewer IDs
    current_interviewer_ids = [p.user_id for p, u in participants if p.role == 'interviewer']
    
    return render_template('admin/edit_interview.html',
                          interview_room=interview_room,
                          participants=participants,
                          all_interviewers=all_interviewers,
                          current_interviewer_ids=current_interviewer_ids)

# Delete Interview Route
@app.route('/admin/delete_interview/<int:interview_id>', methods=['POST'])
def delete_interview(interview_id):
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))

    interview_room = InterviewRoom.query.get_or_404(interview_id)
    
    # Check if interview can be deleted (only if not completed)
    if interview_room.status == 'completed':
        flash('Cannot delete completed interviews. Contact system administrator.', 'error')
        return redirect(url_for('manage_interviews'))
    
    try:
        # Get participants before deletion for notifications
        participants = db.session.query(InterviewParticipant, User).join(User).filter(
            InterviewParticipant.room_id == interview_room.id
        ).all()
        
        job_title = interview_room.application.job.title
        room_code = interview_room.room_code
        
        # Delete related records in correct order
        # 1. Delete interview feedback (if any)
        InterviewFeedback.query.filter_by(room_id=interview_room.id).delete()
        
        # 2. Delete code sessions (if any)
        CodeSession.query.filter_by(room_id=interview_room.id).delete()
        
        # 3. Delete interview participants
        InterviewParticipant.query.filter_by(room_id=interview_room.id).delete()
        
        # 4. Delete the interview room
        db.session.delete(interview_room)
        
        # Log activity before committing
        log_activity('interview_rooms', 'DELETE', interview_id,
                    old_values={'room_code': room_code, 'job_title': job_title},
                    user_id=session['user_id'])
        
        db.session.commit()
        
        # Notify all participants about cancellation
        for participant, user in participants:
            create_notification(
                participant.user_id,
                'Interview Cancelled',
                f'The interview for {job_title} scheduled in room {room_code} has been cancelled.',
                'system'
            )
        
        flash('Interview deleted successfully and participants notified.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting interview: {str(e)}', 'error')
    
    return redirect(url_for('manage_interviews'))

# Manage Interviews Route (List all interviews)
@app.route('/admin/manage_interviews')
def manage_interviews():
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))
    
    # Get all interviews with related data
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    
    query = db.session.query(
        InterviewRoom, JobApplication, JobPosting, Company, CandidateProfile, User
    ).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    )
    
    if status_filter:
        query = query.filter(InterviewRoom.status == status_filter)
    
    interviews = query.order_by(InterviewRoom.scheduled_time.desc()).paginate(
        page=page, per_page=20, error_out=False
    )
    
    return render_template('admin/manage_interviews.html',
                          interviews=interviews,
                          status_filter=status_filter)

# Cancel Interview Route (soft delete - change status to cancelled)
@app.route('/admin/cancel_interview/<int:interview_id>', methods=['POST'])
def cancel_interview(interview_id):
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))

    interview_room = InterviewRoom.query.get_or_404(interview_id)
    
    if interview_room.status == 'completed':
        flash('Cannot cancel completed interviews.', 'error')
        return redirect(url_for('manage_interviews'))
    
    try:
        # Get participants for notifications
        participants = db.session.query(InterviewParticipant, User).join(User).filter(
            InterviewParticipant.room_id == interview_room.id
        ).all()
        
        # Update status to cancelled
        old_status = interview_room.status
        interview_room.status = 'cancelled'
        
        # Log activity
        log_activity('interview_rooms', 'UPDATE', interview_room.id,
                    old_values={'status': old_status},
                    new_values={'status': 'cancelled'},
                    user_id=session['user_id'])
        
        db.session.commit()
        
        # Notify participants
        job_title = interview_room.application.job.title
        for participant, user in participants:
            create_notification(
                participant.user_id,
                'Interview Cancelled',
                f'The interview for {job_title} has been cancelled. You will be notified if it gets rescheduled.',
                'system'
            )
        
        flash('Interview cancelled successfully and participants notified.', 'success')
        
    except Exception as e:
        db.session.rollback()
        flash(f'Error cancelling interview: {str(e)}', 'error')
    
    return redirect(url_for('manage_interviews'))



# Interview Room Routes
@app.route('/interview/<room_code>')
def join_interview(room_code):
    """Join interview room - simplified approach"""
    try:
        # Get interview room from database using your existing models
        room = InterviewRoom.query.filter_by(room_code=room_code).first_or_404()
        
        # Check if user is authorized to join
        participant = InterviewParticipant.query.filter_by(
            room_id=room.id,
            user_id=session['user_id']
        ).first()
        
        if not participant:
            flash('You are not authorized to join this interview', 'error')
            return redirect(url_for('index'))
        
        # Get all participants
        participants = db.session.query(InterviewParticipant, User).join(User).filter(
            InterviewParticipant.room_id == room.id
        ).all()
        
        return render_template('interview_room.html', 
                             room=room, 
                             participants=participants,
                             current_user_role=participant.role)
        
    except Exception as e:
        flash(f'Error loading interview room: {e}', 'error')
        return redirect(url_for('index'))


@app.route('/api/execute_code', methods=['POST'])
def api_execute_code():
    """API endpoint for code execution in interview rooms"""
    if 'user_id' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
        
    data = request.get_json()
    code = data.get('code', '')
    language = data.get('language', 'javascript')
    
    if not code:
        return jsonify({'error': 'No code provided'}), 400
        
    try:
        import time
        start_time = time.time()
        output = execute_code(code, language)
        execution_time = time.time() - start_time
        
        return jsonify({
            'output': output,
            'execution_time': round(execution_time, 3),
            'language': language
        })
    except Exception as e:
        return jsonify({'error': f'Execution failed: {str(e)}'}), 500

@app.route('/interview/<room_code>/feedback', methods=['GET', 'POST'])
def interview_feedback(room_code):
    if 'user_id' not in session or session['user_type'] != 'interviewer':
        return redirect(url_for('login'))
        
    room = InterviewRoom.query.filter_by(room_code=room_code).first_or_404()
    
    if request.method == 'POST':
        feedback = InterviewFeedback(
            room_id=room.id,
            interviewer_id=session['user_id'],
            candidate_id=room.application.candidate.user_id,
            technical_score=int(request.form.get('technical_score', 0)),
            communication_score=int(request.form.get('communication_score', 0)),
            problem_solving_score=int(request.form.get('problem_solving_score', 0)),
            overall_rating=request.form.get('overall_rating'),
            feedback_text=request.form.get('feedback_text'),
            recommendation=request.form.get('recommendation')
        )
        db.session.add(feedback)
        db.session.commit()
        
        flash('Feedback submitted successfully', 'success')
        return redirect(url_for('interviewer_dashboard'))
        
    return render_template('interview_feedback.html', room=room)

# Dashboard Routes for New User Types
@app.route('/interviewer/dashboard')
def interviewer_dashboard():
    if 'user_id' not in session or session['user_type'] != 'interviewer':
        return redirect(url_for('login'))
    
    user = User.query.get(session['user_id'])
    
    # Get upcoming interviews - FIXED
    upcoming_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting, Company).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        InterviewParticipant, InterviewRoom.id == InterviewParticipant.room_id
    ).filter(
        InterviewParticipant.user_id == session['user_id'],
        InterviewRoom.status.in_(['scheduled', 'active']),
        InterviewRoom.scheduled_time >= datetime.utcnow()  # CHANGED TO utcnow()
    ).order_by(InterviewRoom.scheduled_time.asc()).all()
    
    # Get completed interviews - ALSO FIXED  
    completed_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting, Company).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        InterviewParticipant, InterviewRoom.id == InterviewParticipant.room_id
    ).filter(
        InterviewParticipant.user_id == session['user_id'],
        InterviewRoom.status == 'completed'
    ).order_by(InterviewRoom.ended_at.desc()).limit(5).all()
    
    return render_template('interviewer_dashboard.html',
                         user=user,
                         upcoming_interviews=upcoming_interviews,
                         completed_interviews=completed_interviews)


@app.route('/manager/dashboard')
def manager_dashboard():
    if 'user_id' not in session or session['user_type'] not in ['admin', 'manager']:
        return redirect(url_for('login'))
    
    # Get statistics
    stats = {
        'total_interviews': InterviewRoom.query.count(),
        'scheduled_interviews': InterviewRoom.query.filter_by(status='scheduled').count(),
        'active_interviews': InterviewRoom.query.filter_by(status='active').count(),
        'completed_interviews': InterviewRoom.query.filter_by(status='completed').count(),
        'total_interviewers': User.query.filter_by(user_type='interviewer').count()
    }
    
    # Get recent interviews
    recent_interviews = db.session.query(InterviewRoom, JobApplication, JobPosting).join(
        JobApplication, InterviewRoom.job_application_id == JobApplication.id
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).order_by(InterviewRoom.created_at.desc()).limit(10).all()
    
    # Get applications pending interview scheduling
    pending_applications = db.session.query(
        JobApplication, JobPosting, Company, CandidateProfile, User
    ).join(
        JobPosting, JobApplication.job_id == JobPosting.id
    ).join(
        Company, JobPosting.company_id == Company.id
    ).join(
        CandidateProfile, JobApplication.candidate_id == CandidateProfile.id
    ).join(
        User, CandidateProfile.user_id == User.id
    ).filter(
        JobApplication.application_status.in_(['shortlisted', 'under_review']),
        ~JobApplication.id.in_(
            db.session.query(InterviewRoom.job_application_id).filter(
                InterviewRoom.status.in_(['scheduled', 'active', 'completed'])
            )
        )
    ).order_by(JobApplication.applied_at.desc()).limit(10).all()
    
    return render_template('manager_dashboard.html',
                          stats=stats,
                          recent_interviews=recent_interviews,
                          pending_applications=pending_applications)




# Add all the code execution functions from app.py
import subprocess
import tempfile
import uuid
import requests

# Online execution configuration
ONLINE_EXECUTION_ENABLED = True
PISTON_API_URL = "https://emkc.org/api/v2/piston"

PISTON_LANGUAGE_MAP = {
    'javascript': {'language': 'javascript', 'version': '*'},
    'python': {'language': 'python', 'version': '*'},
    'java': {'language': 'java', 'version': '*'},
    'cpp': {'language': 'cpp', 'version': '*'},
    'c': {'language': 'c', 'version': '*'},
    'csharp': {'language': 'csharp', 'version': '*'},
    'php': {'language': 'php', 'version': '*'},
    'ruby': {'language': 'ruby', 'version': '*'},
    'rust': {'language': 'rust', 'version': '*'},
    'swift': {'language': 'swift', 'version': '*'},
}

def execute_code_online(code, language):
    """Execute code using the Piston API"""
    try:
        if not ONLINE_EXECUTION_ENABLED:
            return "Online code execution is disabled."
            
        language_info = PISTON_LANGUAGE_MAP.get(language)
        if not language_info:
            return f"Language '{language}' is not supported."
            
        # Get available runtimes
        runtimes_response = requests.get(f"{PISTON_API_URL}/runtimes")
        if runtimes_response.status_code != 200:
            return "API Error: Failed to get available runtimes"
            
        runtimes = runtimes_response.json()
        
        # Find the latest version
        lang_name = language_info['language']
        version = None
        for runtime in runtimes:
            if runtime['language'] == lang_name:
                version = runtime['version']
                break
                
        if not version:
            return f"Language '{language}' is not available."
            
        # Execute code
        payload = {
            "language": lang_name,
            "version": version,
            "files": [{"content": code}],
            "stdin": "",
            "args": [],
            "compile_timeout": 10000,
            "run_timeout": 3000,
            "compile_memory_limit": -1,
            "run_memory_limit": -1
        }
        
        response = requests.post(f"{PISTON_API_URL}/execute", json=payload)
        if response.status_code != 200:
            return f"API Error: {response.text}"
            
        result = response.json()
        
        # Check for compilation errors
        if 'compile' in result and result['compile']['code'] != 0:
            return f"Compilation Error: {result['compile']['stderr']}"
            
        # Get run results
        run_result = result.get('run', {})
        stdout = run_result.get('stdout', '')
        stderr = run_result.get('stderr', '')
        exit_code = run_result.get('code', 0)
        
        if exit_code == 0:
            return stdout
        else:
            return f"Execution Error (code {exit_code}): {stderr}"
            
    except Exception as e:
        return f"Online execution error: {str(e)}"

def execute_code(code, language):
    """Execute code via online Piston API only."""
    return execute_code_online(code, language)

# Add similar functions for other languages...


#SocketIO for real-time updates
from flask_socketio import SocketIO, emit, join_room, leave_room
from collections import defaultdict

socketio = SocketIO(app, cors_allowed_origins="*")

# Track interview participants
INTERVIEW_PARTICIPANTS = defaultdict(dict)  # room_id -> { sid: user_info }
SID_TO_INTERVIEW_ROOM = {}  # sid -> room_id

# Update your existing SocketIO events
@socketio.on('join_interview')
def on_join_interview(data):
    room_id = str(data['room'])
    room_code = data['room_code']
    user_role = data['role']
    join_room(room_id)
    
    # Get user info from session
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        user_info = {
            'username': f"{user.first_name} {user.last_name}",
            'role': user_role,
            'user_id': user.id
        }
        
        # Track participant
        INTERVIEW_PARTICIPANTS[room_id][request.sid] = user_info
        SID_TO_INTERVIEW_ROOM[request.sid] = room_id
        
        # Update participant status in database
        participant = InterviewParticipant.query.filter_by(
            room_id=int(room_id),
            user_id=user.id
        ).first()
        if participant:
            participant.joined_at = datetime.utcnow()
            participant.is_active = True
            db.session.commit()
        
        # Send existing participants to the joiner
        others = [
            {'sid': sid, 'username': info['username'], 'role': info['role']}
            for sid, info in INTERVIEW_PARTICIPANTS[room_id].items()
            if sid != request.sid
        ]
        emit('participants', {'participants': others}, to=request.sid)
        
        # Notify others in room
        emit('user_joined', {
            'sid': request.sid,
            'username': user_info['username'],
            'role': user_info['role']
        }, room=room_id, include_self=False)

# Keep your existing offer, answer, ice_candidate, and other events as they are


@socketio.on('leave_interview')
def on_leave_interview(data):
    room_id = str(data['room'])
    leave_room(room_id)
    
    # Cleanup tracking
    user_info = INTERVIEW_PARTICIPANTS[room_id].pop(request.sid, None)
    SID_TO_INTERVIEW_ROOM.pop(request.sid, None)
    
    if user_info and 'user_id' in session:
        # Update participant status in database
        participant = InterviewParticipant.query.filter_by(
            room_id=int(room_id), 
            user_id=user_info['user_id']
        ).first()
        if participant:
            participant.left_at = datetime.utcnow()
            participant.is_active = False
            db.session.commit()
    
    emit('user_left', {
        'sid': request.sid, 
        'username': user_info['username'] if user_info else 'Unknown'
    }, room=room_id)

@socketio.on('disconnect')
def on_interview_disconnect():
    sid = request.sid
    room_id = SID_TO_INTERVIEW_ROOM.pop(sid, None)
    
    if room_id:
        user_info = INTERVIEW_PARTICIPANTS[room_id].pop(sid, None)
        
        if user_info:
            emit('user_left', {
                'sid': sid, 
                'username': user_info['username']
            }, room=room_id)

# WebRTC Signaling Events
@socketio.on('offer')
def on_interview_offer(data):
    to_sid = data.get('to')
    if not to_sid:
        return
    emit('offer', {
        'offer': data['offer'],
        'from': request.sid
    }, to=to_sid)

@socketio.on('answer')
def on_interview_answer(data):
    to_sid = data.get('to')
    if not to_sid:
        return
    emit('answer', {
        'answer': data['answer'],
        'from': request.sid
    }, to=to_sid)

@socketio.on('ice_candidate')
def on_interview_ice_candidate(data):
    to_sid = data.get('to')
    if not to_sid:
        return
    emit('ice_candidate', {
        'candidate': data['candidate'],
        'from': request.sid
    }, to=to_sid)

# Code Editor Events

@app.route('/code_editor/<room_code>')
def code_editor(room_code):
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    # Verify user has access to this room
    room = InterviewRoom.query.filter_by(room_code=room_code).first_or_404()
    
    participant = InterviewParticipant.query.filter_by(
        room_id=room.id,
        user_id=session['user_id']
    ).first()
    
    if not participant:
        flash('You are not authorized to access this code editor', 'error')
        return redirect(url_for('index'))
    
    return render_template('code_editor.html', room_code=room_code)


@socketio.on('code_change')
def on_code_change(data):
    room_id = str(data['room'])
    emit('code_updated', {
        'code': data['code'],
        'language': data.get('language', 'javascript'),
        'from': request.sid
    }, room=room_id, include_self=False)


# At the end of main.py, replace the current if __name__ == '__main__' section:
if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    socketio.run(app, debug=True, host='0.0.0.0', port=5000)


