from flask import Flask, render_template, request, redirect, url_for
from flask_cors import CORS
import pandas as pd
import os

app = Flask(__name__)
CORS(app, supports_credentials=True)  # Enable CORS for mobile and cross-origin support

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

if __name__ == '__main__':
    app.run(debug=True)
