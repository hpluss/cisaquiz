from app import db
from datetime import datetime, timezone


class Questions(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    text = db.Column(db.Text, nullable=False)
    options = db.Column(db.JSON, nullable=False)  # Liste de réponses possibles
    correct = db.Column(db.Integer, nullable=False)  # Index de la bonne réponse (0-based)
    explanation = db.Column(db.Text, nullable=True)
    theme = db.Column(db.String(100), nullable=False)
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Questions id={self.id} theme='{self.theme}'>"


class SessionQuiz(db.Model):
    __tablename__ = 'sessionQuiz'
    id_session = db.Column(db.Integer, primary_key=True, autoincrement=True)
    score = db.Column(db.Float, nullable=False, default=0)  # Score total
    theme_results = db.Column(db.JSON, nullable=True)  # Résultats par thème
    duration = db.Column(db.Integer, nullable=True)  # Durée en secondes
    param_quiz = db.Column(db.JSON, nullable=True)  # Paramètres du quiz
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<SessionQuiz id_session={self.id_session} score={self.score}>"


class SessionAnswer(db.Model):
    __tablename__ = 'session_answers'
    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    session_id = db.Column(db.Integer, db.ForeignKey('sessionQuiz.id_session'), nullable=False)
    question_id = db.Column(db.Integer, db.ForeignKey('questions.id'), nullable=False)
    user_answer = db.Column(db.Integer, nullable=False)  # Index de la réponse donnée
    is_correct = db.Column(db.Boolean, nullable=False)


    def __repr__(self):
        return f"<SessionAnswer session={self.session_id} question={self.question_id}>"

