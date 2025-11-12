from flask import Flask, render_template, request, redirect, url_for
import pandas as pd
import os

app = Flask(__name__)

# Load the cleaned career data from CSV (expects columns: Required_Degree, Required_Skills, Required_Interests, Career)
CSV_PATH = 'careers.csv'
if os.path.exists(CSV_PATH):
    df = pd.read_csv(CSV_PATH)
    # Normalize column names and values for robust matching
    df.columns = [c.strip() for c in df.columns]
    df['Required_Degree'] = df['Required_Degree'].astype(str).str.strip().str.lower()
    df['Required_Skills'] = df['Required_Skills'].astype(str).str.strip()
    df['Required_Interests'] = df['Required_Interests'].astype(str).str.strip()
    # Extract unique skills and interests for dropdowns
    all_skills = df['Required_Skills'].dropna().apply(lambda x: [i.strip() for i in x.split(',')])
    flat_skills = sorted(set(skill for sublist in all_skills for skill in sublist))

    all_interests = df['Required_Interests'].dropna().apply(lambda x: [i.strip() for i in x.split(',')])
    flat_interests = sorted(set(interest for sublist in all_interests for interest in sublist))
else:
    print(f"Error: '{CSV_PATH}' not found. Please ensure the file is in the correct directory.")
    df = pd.DataFrame(columns=['Required_Degree', 'Required_Skills', 'Required_Interests', 'Career'])

def recommend_career(user_skills, user_degree, user_interests):
    if df.empty:
        return "No career data available.", None

    # Normalize user input
    user_skills_set = set(skill.strip().lower() for skill in str(user_skills).replace(';', ',').split(',') if skill.strip())
    user_interests_set = set(interest.strip().lower() for interest in str(user_interests).replace(';', ',').split(',') if interest.strip())
    user_degree_norm = str(user_degree).strip().lower()

    # Filter by degree (match exact normalized degree or 'any')
    degree_filter = (df['Required_Degree'] == user_degree_norm) | (df['Required_Degree'] == 'any')
    filtered_careers = df[degree_filter].copy()

    if filtered_careers.empty:
        return "No careers found matching your degree. Try broadening your search.", None

    def calculate_match_score(row):
        # Normalize row skill/interest lists
        req_skills = set(s.strip().lower() for s in str(row.get('Required_Skills', '')).replace(';', ',').split(',') if s.strip())
        req_interests = set(i.strip().lower() for i in str(row.get('Required_Interests', '')).replace(';', ',').split(',') if i.strip())
        req_degree = str(row.get('Required_Degree', '')).strip().lower()

        skill_score = len(user_skills_set & req_skills)
        interest_score = len(user_interests_set & req_interests)
        degree_score = 1 if req_degree == user_degree_norm else 0  # Give 1 point if degree matches exactly

        return skill_score + interest_score + degree_score

    filtered_careers.loc[:, 'match_score'] = filtered_careers.apply(calculate_match_score, axis=1)

    # If you want to be less strict, lower threshold to 1; keep 2 for stronger matches
    threshold = 2
    qualified_careers = filtered_careers[filtered_careers['match_score'] >= threshold]

    if qualified_careers.empty:
        # fallback: show best partial match (even if score is 0)
        best_match = filtered_careers.sort_values(by='match_score', ascending=False).iloc[0]
        career_title = str(best_match['Career']).strip()
        required_skills = str(best_match['Required_Skills']).strip()
        return f"You might explore: {career_title}. Your current profile has a weak match, but it's a starting point.", required_skills

    # Return top match and its required skills
    best_match = qualified_careers.sort_values(by='match_score', ascending=False).iloc[0]
    career_title = str(best_match['Career']).strip()
    required_skills = str(best_match['Required_Skills']).strip()

    return career_title, required_skills

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
        name = request.form.get('name')
        email = request.form.get('email')
        message = request.form.get('message')
        # Here you would typically handle the form submission
        # For now, we'll just redirect back with a success parameter
        return redirect(url_for('contact') + '?success=true')
    return render_template('contact.html')

@app.route('/recommend', methods=['POST'])
def recommend():
    user_skills = ', '.join(request.form.getlist('skills'))
    user_interests = ', '.join(request.form.getlist('interests'))
    user_degree = request.form.get('degree').strip()

    # Call with correct argument order: (skills, degree, interests)
    career, skills = recommend_career(user_skills, user_degree, user_interests)

    # Pass explicit variables to template for reliable rendering
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