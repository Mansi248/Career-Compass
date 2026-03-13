from flask import Flask, render_template, request, redirect, url_for,session
from flask_cors import CORS
import pandas as pd
import os
import json
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
# Added a Secret Key for forms and sessions
app.config['SECRET_KEY'] = 'your_secret_key_here'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///'+ os.path.join(basedir, 'career_compass.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Initialize DB and CORS with the app
db = SQLAlchemy(app)
CORS(app, supports_credentials=True)

# --- THE MODELS ---

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True) # Fixed: removed extra .db
    username = db.Column(db.String(20), unique=True, nullable=False)
    password = db.Column(db.String(60), nullable=False)
    resumes = db.relationship('Resume', backref='author', lazy=True)

class Resume(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False, default="My Resume")
    date_created = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    content = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)

# Load and normalize career data
CSV_PATH = 'careers.csv'
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    df.columns = [c.strip() for c in df.columns]
    df['Required_Degree'] = df['Required_Degree'].astype(str).str.strip().str.lower()
    df['Required_Skills'] = df['Required_Skills'].astype(str).str.strip()
    df['Required_Interests'] = df['Required_Interests'].astype(str).str.strip()
else:
    print(f"Error: '{CSV_PATH}' not found.")
    df = pd.DataFrame(columns=['Required_Degree', 'Required_Skills', 'Required_Interests', 'Career'])

def recommend_career(user_skills, user_degree, user_interests):
    if df.empty:
        return "No career data available.", None

    user_skills_set = set(skill.strip().lower() for skill in str(user_skills).replace(';', ',').split(',') if skill.strip())
    user_interests_set = set(interest.strip().lower() for interest in str(user_interests).replace(';', ',').split(',') if interest.strip())
    user_degree_norm = str(user_degree).strip().lower()

    degree_filter = (df['Required_Degree'] == user_degree_norm) | (df['Required_Degree'] == 'any')
    filtered_careers = df[degree_filter].copy()

    if filtered_careers.empty:
        return "No careers found matching your degree. Try broadening your search.", None

    def calculate_match_score(row):
        req_skills = set(s.strip().lower() for s in str(row.get('Required_Skills', '')).replace(';', ',').split(',') if s.strip())
        req_interests = set(i.strip().lower() for i in str(row.get('Required_Interests', '')).replace(';', ',').split(',') if i.strip())
        req_degree = str(row.get('Required_Degree', '')).strip().lower()

        skill_score = len(user_skills_set & req_skills)
        interest_score = len(user_interests_set & req_interests)
        degree_score = 1 if req_degree == user_degree_norm else 0

        return skill_score + interest_score + degree_score

    filtered_careers['match_score'] = filtered_careers.apply(calculate_match_score, axis=1)
    qualified_careers = filtered_careers[filtered_careers['match_score'] >= 2]

    if qualified_careers.empty:
        best_match = filtered_careers.sort_values(by='match_score', ascending=False).iloc[0]
        return f"You might explore: {best_match['Career'].strip()}. Your current profile has a weak match.", best_match['Required_Skills'].strip()

    best_match = qualified_careers.sort_values(by='match_score', ascending=False).iloc[0]
    return best_match['Career'].strip(), best_match['Required_Skills'].strip()

@app.route('/')
def home():
    all_skills = df['Required_Skills'].dropna().apply(lambda x: [i.strip() for i in x.split(',')])
    flat_skills = sorted(set(skill for sublist in all_skills for skill in sublist))

    all_interests = df['Required_Interests'].dropna().apply(lambda x: [i.strip() for i in x.split(',')])
    flat_interests = sorted(set(interest for sublist in all_interests for interest in sublist))

    return render_template('index.html', skills=flat_skills, interests=flat_interests)

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'GET':
        return render_template('register.html')

    if request.method == 'POST':
        user_name = request.form.get('username')
        user_pwd = request.form.get('password')

        # Check if username already exists
        existing_user = User.query.filter_by(username=user_name).first()
        if existing_user:
            return "Username already taken! Try another."

        # Create new user and save to database
        new_user = User(username=user_name, password=user_pwd)
        db.session.add(new_user)
        db.session.commit()

        return redirect(url_for('login')) # Redirect to login page after success


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_name = request.form.get('username')
        user_pwd = request.form.get('password')

        # Get the 'next' destination from the URL (if it exists)
        next_page = request.args.get('next')

        user = User.query.filter_by(username=user_name).first()

        if user and user.password == user_pwd:
            session['user_id'] = user.id
            session['username'] = user.username

            # SMART REDIRECT:
            if next_page:
                return redirect(url_for(next_page))
            else:
                return redirect(url_for('home')) # Default for normal logins
        else:
            return "Invalid username or password!"

    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home'))

@app.route('/explore')
def explore():
    return render_template('explore.html')

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        # Handle form submission (e.g., save or email)
        return redirect(url_for('contact') + '?success=true')
    return render_template('contact.html')

@app.route('/recommend', methods=['POST'])
def recommend():
    user_skills = ', '.join(request.form.getlist('skills'))
    user_interests = ', '.join(request.form.getlist('interests'))
    user_degree = request.form.get('degree', '').strip()

    career, skills = recommend_career(user_skills, user_degree, user_interests)

    return render_template(
        'results.html',
        career=career,
        required_skills=skills,
        user_skills=user_skills,
        user_interests=user_interests,
        user_degree=user_degree
    )

@app.route('/create_resume')
def create_resume():
    if 'user_id' not in session:
        # We add a 'next' variable to the URL: /login?next=create_resume
        return redirect(url_for('login', next='create_resume'))
    return render_template('create_resume.html')

@app.route('/save_resume', methods=['POST'])
def save_resume():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # 1. Collect ALL fields from the new form
    title = request.form.get('resume_title')

    # This dictionary must match what resume_template.html expects
    resume_details = {
        "full_name": request.form.get('full_name'),
        "phone": request.form.get('phone'),
        "city": request.form.get('city'),
        "email": request.form.get('email'),
        "summary": request.form.get('summary'),
        "job_title": request.form.get('job_title'),
        "company": request.form.get('company'),
        "job_date": request.form.get('job_date'),
        # This splits the text area into a list for the bullet points
        "experience_bullets": request.form.get('experience').split('\n') if request.form.get('experience') else [],
        "university": request.form.get('university'),
        "degree": request.form.get('degree'),
        "grad_date": request.form.get('grad_date'),
        "skills": request.form.get('skills')
    }

    # 2. Save to Database
    new_resume = Resume(
        title=title,
        content=json.dumps(resume_details),
        user_id=session['user_id']
    )

    db.session.add(new_resume)
    db.session.commit()

    # 3. Redirect to history to see the new entry
    return redirect(url_for('history'))

@app.route('/history')
def history():
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Get all resumes belonging to the logged-in user
    user_resumes = Resume.query.filter_by(user_id=session['user_id']).order_by(Resume.date_created.desc()).all()

    return render_template('history.html', resumes=user_resumes)

@app.route('/delete_resume/<int:resume_id>', methods=['POST'])
def delete_resume(resume_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Find the resume
    resume_to_delete = Resume.query.get_or_404(resume_id)

    # Security: Ensure it belongs to the logged-in user
    if resume_to_delete.user_id != session['user_id']:
        return "Unauthorized", 403

    # Delete from database
    db.session.delete(resume_to_delete)
    db.session.commit()

    return redirect(url_for('history'))

@app.route('/view_resume/<int:resume_id>')
def view_resume(resume_id):
    if 'user_id' not in session:
        return redirect(url_for('login'))

    # Fetch the specific resume
    resume = Resume.query.get_or_404(resume_id)

    # Security: Ensure this resume belongs to the logged-in user
    if resume.user_id != session['user_id']:
        return "Access Denied", 403

    # Convert the JSON string back into a dictionary
    data = json.loads(resume.content)

    return render_template('resume_template.html', resume=resume, data=data)

if __name__ == '__main__':
    app.run(debug=True)
