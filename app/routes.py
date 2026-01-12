from flask import render_template, request, jsonify, session, redirect, url_for, current_app as app
from app import db
from app.models import Questions, SessionQuiz, SessionAnswer
import json
from datetime import datetime, timezone

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Afficher le dashboard avec les statistiques d'étude"""
    # Récupérer toutes les sessions de quiz
    all_sessions = SessionQuiz.query.all()
    
    # Récupérer TOUTES les réponses (y compris les doublons par question)
    all_answers = SessionAnswer.query.all()
    
    # Créer un dictionnaire : question_id -> dernière réponse (chronologiquement)
    last_answer_by_question = {}
    for answer in all_answers:
        question_id = answer.question_id
        # Garder seulement la réponse la plus récente (la plus haute ID)
        if question_id not in last_answer_by_question or answer.id > last_answer_by_question[question_id].id:
            last_answer_by_question[question_id] = answer
    
    # Utiliser seulement la dernière réponse par question
    unique_answers = list(last_answer_by_question.values())
    
    # Calculer les statistiques globales (basées sur les réponses uniques)
    total_answers = len(unique_answers)
    correct_answers = sum(1 for a in unique_answers if a.is_correct)
    incorrect_answers = total_answers - correct_answers
    
    overall_score = (correct_answers / total_answers * 100) if total_answers > 0 else 0
    
    # Calculer le pourcentage de progression globale (par rapport au total de la BD)
    total_questions_in_db = Questions.query.count()
    progression_percentage = (total_answers / total_questions_in_db * 100) if total_questions_in_db > 0 else 0
    
    # Récupérer les statistiques par thème (basées sur les réponses uniques)
    theme_stats_dict = {}
    for answer in unique_answers:
        question = Questions.query.get(answer.question_id)
        if question:
            theme = question.theme
            if theme not in theme_stats_dict:
                theme_stats_dict[theme] = {'correct': 0, 'total': 0}
            
            theme_stats_dict[theme]['total'] += 1
            if answer.is_correct:
                theme_stats_dict[theme]['correct'] += 1
    
    theme_data = []
    for theme, stats in sorted(theme_stats_dict.items()):
        total = stats['total']
        correct = stats['correct']
        percentage = (correct / total * 100) if total > 0 else 0
        theme_data.append({
            'name': theme,
            'correct': correct,
            'total': total,
            'percentage': round(percentage, 1)
        })
    
    # Récupérer l'historique des quiz (derniers 10)
    recent_sessions = SessionQuiz.query.order_by(SessionQuiz.id_session.desc()).limit(10).all()
    
    session_history = []
    for sess in recent_sessions:
        answers = SessionAnswer.query.filter(SessionAnswer.session_id == sess.id_session).all()
        correct = sum(1 for a in answers if a.is_correct)
        total = len(answers)
        session_history.append({
            'session_id': sess.id_session,
            'score': round(sess.score, 1) if sess.score else 0,
            'correct': correct,
            'total': total,
            'date': sess.created_at.strftime('%d/%m/%Y %H:%M') if sess.created_at else 'N/A'
        })
    
    return render_template('dashboard.html',
                         overall_score=round(overall_score, 1),
                         total_answers=total_answers,
                         correct_answers=correct_answers,
                         incorrect_answers=incorrect_answers,
                         progression_percentage=round(progression_percentage, 1),
                         total_questions_in_db=total_questions_in_db,
                         theme_stats=theme_data,
                         session_history=session_history,
                         total_sessions=len(all_sessions))

@app.route('/quiz/config', methods=['GET', 'POST'])
def quiz_config():
    """Page de configuration du quiz avec sélection des options"""
    if request.method == 'GET':
        # Récupérer les thèmes disponibles
        themes = db.session.query(Questions.theme).distinct().all()
        themes = [t[0] for t in themes]
        
        return render_template('quiz/config.html', themes=themes)
    
    elif request.method == 'POST':
        # Récupérer les paramètres du formulaire
        data = request.get_json()
        
        # Valider les données
        selected_themes = data.get('themes', [])
        num_questions = int(data.get('num_questions', 10))
        show_answers = data.get('show_answers', 'end')  # 'go' ou 'end'
        question_filters = data.get('question_filters', ['new', 'answered', 'incorrect'])
        
        if not selected_themes or num_questions <= 0:
            return jsonify({'error': 'Paramètres invalides'}), 400
        
        # Générer le quiz avec filtres
        questions = generate_quiz_questions(selected_themes, num_questions, question_filters)
        
        if not questions:
            return jsonify({'error': 'Pas de questions disponibles pour ces thèmes et filtres'}), 400
        
        # Créer une session de quiz
        quiz_session = SessionQuiz(
            score=0,
            param_quiz=json.dumps({
                'themes': selected_themes,
                'num_questions': num_questions,
                'show_answers': show_answers,
                'question_filters': question_filters,
                'total_questions': len(questions)
            })
        )
        db.session.add(quiz_session)
        db.session.commit()
        
        # Stocker les IDs des questions en session
        session['quiz_session_id'] = quiz_session.id_session
        session['quiz_questions'] = [q.id for q in questions]
        session['quiz_config'] = {
            'show_answers': show_answers,
            'total_questions': len(questions)
        }
        
        return jsonify({
            'session_id': quiz_session.id_session,
            'redirect_url': url_for('quiz_page', session_id=quiz_session.id_session)
        }), 200

@app.route('/quiz/config/questions-count', methods=['POST'])
def get_questions_count():
    """Obtenir le nombre de questions disponibles pour les thèmes sélectionnés"""
    data = request.get_json()
    selected_themes = data.get('themes', [])
    question_filters = data.get('question_filters', ['new', 'answered', 'incorrect'])
    
    if not selected_themes:
        return jsonify({'count': 0}), 200
    
    # Compter les questions selon les filtres
    from sqlalchemy.sql.expression import func
    
    # Récupérer les IDs des questions répondues correctement et incorrectement
    answered_correct = db.session.query(SessionAnswer.question_id).filter(
        SessionAnswer.is_correct == True
    ).all()
    answered_correct = [q[0] for q in answered_correct]
    
    answered_incorrect = db.session.query(SessionAnswer.question_id).filter(
        SessionAnswer.is_correct == False
    ).all()
    answered_incorrect = [q[0] for q in answered_incorrect]
    
    # Récupérer les IDs de toutes les questions répondues
    answered_any = db.session.query(SessionAnswer.question_id).all()
    answered_any = [q[0] for q in answered_any]
    
    # Construire la requête de base
    query = Questions.query.filter(Questions.theme.in_(selected_themes))
    
    # Appliquer les filtres
    filtered_questions = []
    
    if 'new' in question_filters:
        # Questions non répondues
        new_questions = query.filter(~Questions.id.in_(answered_any)).all()
        filtered_questions.extend(new_questions)
    
    if 'answered' in question_filters:
        # Questions répondues correctement
        answered_q = query.filter(Questions.id.in_(answered_correct)).all()
        filtered_questions.extend(answered_q)
    
    if 'incorrect' in question_filters:
        # Questions répondues incorrectement
        incorrect_q = query.filter(Questions.id.in_(answered_incorrect)).all()
        filtered_questions.extend(incorrect_q)
    
    # Supprimer les doublons
    unique_ids = set()
    unique_questions = []
    for q in filtered_questions:
        if q.id not in unique_ids:
            unique_ids.add(q.id)
            unique_questions.append(q)
    
    count = len(unique_questions)
    
    return jsonify({'count': count}), 200

@app.route('/quiz/<int:session_id>', methods=['GET'])
def quiz_page(session_id):
    """Page principale du quiz"""
    # Vérifier que la session existe
    quiz_session = SessionQuiz.query.get_or_404(session_id)
    
    # Récupérer les paramètres du quiz
    params = json.loads(quiz_session.param_quiz) if quiz_session.param_quiz else {}
    
    # Récupérer les questions de cette session
    question_ids = session.get('quiz_questions', [])
    if not question_ids:
        return redirect(url_for('quiz_config'))
    
    # Récupérer les réponses depuis la session Flask (pas depuis la BD)
    quiz_answers = session.get('quiz_answers', {})
    answered_count = len(quiz_answers)
    
    # Déterminer la question actuelle
    current_question_index = answered_count
    
    if current_question_index >= len(question_ids):
        # Quiz terminé
        return redirect(url_for('quiz_results', session_id=session_id))
    
    # Récupérer la question actuelle
    current_question_id = question_ids[current_question_index]
    question = Questions.query.get_or_404(current_question_id)
    
    return render_template('quiz/session.html',
                         session_id=session_id,
                         question=question,
                         question_number=current_question_index + 1,
                         total_questions=len(question_ids),
                         show_answers=params.get('show_answers', 'end'))

@app.route('/quiz/<int:session_id>/answer', methods=['POST'])
def submit_answer(session_id):
    """Soumettre une réponse pour une question (stockée en session, pas en BD)"""
    quiz_session = SessionQuiz.query.get_or_404(session_id)
    
    data = request.get_json()
    question_id = int(data.get('question_id'))
    user_answer = int(data.get('answer'))
    
    # Récupérer la question
    question = Questions.query.get_or_404(question_id)
    
    # Vérifier si la réponse est correcte
    is_correct = (user_answer == question.correct)
    
    # Stocker la réponse en session Flask (pas en BD pour le moment)
    if 'quiz_answers' not in session:
        session['quiz_answers'] = {}
    
    session['quiz_answers'][str(question_id)] = {
        'user_answer': user_answer,
        'is_correct': is_correct
    }
    session.modified = True
    
    response = {
        'is_correct': is_correct,
        'correct_answer': question.correct,
        'explanation': question.explanation
    }
    
    return jsonify(response), 200

@app.route('/quiz/<int:session_id>/results', methods=['GET'])
def quiz_results(session_id):
    """Afficher et enregistrer les résultats du quiz"""
    quiz_session = SessionQuiz.query.get_or_404(session_id)
    
    # Récupérer les paramètres du quiz
    params = json.loads(quiz_session.param_quiz) if quiz_session.param_quiz else {}
    
    # Récupérer les réponses depuis la session Flask
    quiz_answers = session.get('quiz_answers', {})
    question_ids = session.get('quiz_questions', [])
    
    # Enregistrer toutes les réponses en BD maintenant
    for question_id_str, answer_data in quiz_answers.items():
        question_id = int(question_id_str)
        session_answer = SessionAnswer(
            session_id=session_id,
            question_id=question_id,
            user_answer=answer_data['user_answer'],
            is_correct=answer_data['is_correct']
        )
        db.session.add(session_answer)
    
    db.session.commit()
    
    # Calculer le score
    correct_count = sum(1 for a in quiz_answers.values() if a['is_correct'])
    total_count = len(quiz_answers)
    score_percentage = (correct_count / total_count * 100) if total_count > 0 else 0
    
    # Mettre à jour la session avec le score
    quiz_session.score = score_percentage
    db.session.commit()
    
    # Préparer les résultats détaillés
    results_detail = []
    for question_id_str, answer_data in quiz_answers.items():
        question_id = int(question_id_str)
        question = Questions.query.get(question_id)
        if question:
            results_detail.append({
                'question': question.text,
                'user_answer': question.options[answer_data['user_answer']],
                'correct_answer': question.options[question.correct],
                'is_correct': answer_data['is_correct'],
                'explanation': question.explanation,
                'theme': question.theme
            })
    
    # Nettoyer la session
    if 'quiz_answers' in session:
        del session['quiz_answers']
    if 'quiz_questions' in session:
        del session['quiz_questions']
    session.modified = True
    
    return render_template('quiz/results.html',
                         session_id=session_id,
                         score=score_percentage,
                         correct_count=correct_count,
                         total_count=total_count,
                         results=results_detail,
                         params=params)

def generate_quiz_questions(themes, num_questions, question_filters=['new', 'answered', 'incorrect']):
    """Générer une liste aléatoire de questions selon les thèmes et les filtres"""
    from sqlalchemy.sql.expression import func
    
    # Récupérer les IDs des questions répondues correctement et incorrectement
    answered_correct = db.session.query(SessionAnswer.question_id).filter(
        SessionAnswer.is_correct == True
    ).all()
    answered_correct = [q[0] for q in answered_correct]
    
    answered_incorrect = db.session.query(SessionAnswer.question_id).filter(
        SessionAnswer.is_correct == False
    ).all()
    answered_incorrect = [q[0] for q in answered_incorrect]
    
    # Récupérer les IDs de toutes les questions répondues
    answered_any = db.session.query(SessionAnswer.question_id).all()
    answered_any = [q[0] for q in answered_any]
    
    # Construire la requête de base
    base_query = Questions.query.filter(Questions.theme.in_(themes))
    
    # Appliquer les filtres
    filtered_questions = []
    
    if 'new' in question_filters:
        # Questions non répondues
        new_questions = base_query.filter(~Questions.id.in_(answered_any)).all()
        filtered_questions.extend(new_questions)
    
    if 'answered' in question_filters:
        # Questions répondues correctement
        answered_q = base_query.filter(Questions.id.in_(answered_correct)).all()
        filtered_questions.extend(answered_q)
    
    if 'incorrect' in question_filters:
        # Questions répondues incorrectement
        incorrect_q = base_query.filter(Questions.id.in_(answered_incorrect)).all()
        filtered_questions.extend(incorrect_q)
    
    # Supprimer les doublons en gardant l'ordre aléatoire
    unique_ids = set()
    unique_questions = []
    for q in filtered_questions:
        if q.id not in unique_ids:
            unique_ids.add(q.id)
            unique_questions.append(q)
    
    # Mélanger et limiter
    import random
    random.shuffle(unique_questions)
    
    return unique_questions[:num_questions]