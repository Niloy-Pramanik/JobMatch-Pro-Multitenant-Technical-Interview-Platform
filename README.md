# JobMatch Pro - Multi tenant Interview Platform

## Overview
JobMatch Pro is a comprehensive job matching system built with Flask that connects job seekers with employers. The platform facilitates the entire recruitment process from job posting to candidate selection, including features like skill matching, online assessments, and interview scheduling.

## Features

### Role-Based Access
- **Job Seekers**: Create profiles, upload CVs, apply for jobs, take assessments
- **Employers**: Post job openings, review applications, conduct interviews
- **Admins**: Manage users, generate reports, oversee platform operations
- **Interviewers**: Conduct and evaluate interviews
- **Managers**: Oversee recruitment processes

### Job Posting & Application
- Employers can create detailed job listings with requirements and qualifications
- Candidates can search and apply for suitable positions
- Application tracking system for both employers and candidates

### Profile Management
- Comprehensive user profiles for candidates and employers
- Skill management system with proficiency levels
- CV upload and management

### Advanced Matching Algorithm
- Skill-based job matching for candidates
- Candidate recommendations for employers based on skill match
- Experience and education level filtering

### Assessment System
- MCQ exam creation and management
- Automated scoring and result analysis
- Performance tracking for candidates

### Interview Management
- Interview scheduling and coordination
- Feedback and evaluation system
- Candidate progress tracking

### Search & Filters
- Advanced job search with multiple filters
- Candidate search for employers
- Skill-based filtering

## Tech Stack

### Backend
- **Flask**: Python web framework
- **MySQL**: Database management
- **SQLAlchemy**: ORM for database operations
- **Flask-Mail**: Email notifications
- **Flask-Bcrypt**: Password hashing and security

### Frontend
- **HTML/CSS/JavaScript**: Frontend development
- **Bootstrap**: Responsive design
- **Jinja2**: Templating engine

## Installation & Setup

### Prerequisites
- Python 3.8+
- MySQL Server
- Git

### Steps

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd FLASK-DBMS-PROJECT-master
   ```

2. **Create and activate a virtual environment**
   ```bash
   # On Windows
   python -m venv venv
   venv\Scripts\activate
   
   # On macOS/Linux
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set up the database**
   - Create a MySQL database named `job_matching_system`
   - Import the database schema from `skill_db.sql`
   ```bash
   mysql -u root -p job_matching_system < skill_db.sql
   ```

5. **Configure the application**
   - Update the database connection string in `PROJECT/main.py`
   - Update email configuration in `config.json`

6. **Run the application**
   ```bash
   cd PROJECT
   python main.py
   ```

7. **Access the application**
   - Open your browser and navigate to `http://localhost:5000`

## Usage Guide

### For Employers
1. Register as an employer
2. Create a company profile
3. Post job openings with detailed requirements
4. Review applications and schedule interviews
5. Create assessments for candidates

### For Job Seekers
1. Register as a candidate
2. Complete your profile with skills and experience
3. Upload your CV
4. Search and apply for jobs
5. Take assessments and attend interviews

### For Interviewers
1. Log in with interviewer credentials
2. Access the interviewer dashboard
3. View scheduled interviews
4. Conduct interviews and provide feedback
5. Make recommendations on candidates

### For Managers
1. Log in with manager credentials
2. Access the manager dashboard
3. Oversee recruitment processes
4. Review interviewer feedback
5. Make final hiring decisions

## Project Structure
```
FLASK-DBMS-PROJECT-master/
├── PROJECT/
│   ├── main.py            # Main application file
│   ├── static/            # Static assets
│   └── templates/         # HTML templates
├── README.md              # Project documentation
├── config.json            # Configuration settings
├── requirements.txt       # Python dependencies
├── skill_db.sql           # Database schema
└── static/uploads/        # Uploaded files storage
```

## Contributor
- https://github.com/Knocktern
  
