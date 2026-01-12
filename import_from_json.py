import json
from app import create_app, db
from app.models import Questions

app = create_app()

def import_from_json(json_file):
    """Importe les questions depuis le fichier JSON dans la base de données"""
    with open(json_file, 'r', encoding='utf-8') as f:
        questions_data = json.load(f)
    
    with app.app_context():
        # Vérifier si des questions existent déjà
        existing_count = Questions.query.count()
        if existing_count > 0:
            response = input(f"La base de données contient déjà {existing_count} questions. Continuer ? (y/n): ")
            if response.lower() != 'y':
                print("Import annulé.")
                return
            # Supprimer les questions existantes
            Questions.query.delete()
            db.session.commit()
            print("Questions existantes supprimées.")
        
        # Ajouter les questions du JSON
        added_count = 0
        for i, q_data in enumerate(questions_data, 1):
            try:
                # Convertir les options du format dictionnaire au format liste
                if isinstance(q_data.get('options'), dict):
                    options_list = [
                        q_data['options'].get('A', ''),
                        q_data['options'].get('B', ''),
                        q_data['options'].get('C', ''),
                        q_data['options'].get('D', '')
                    ]
                else:
                    options_list = q_data.get('options', [])
                
                # Convertir la réponse correcte de lettre à index
                correct = q_data.get('correct', '')
                if isinstance(correct, str) and correct in 'ABCD':
                    correct_index = ord(correct) - ord('A')
                else:
                    correct_index = int(correct) if isinstance(correct, (int, str)) and str(correct).isdigit() else 0
                
                # Extraire le thème
                theme = q_data.get('theme', 'General').strip()
                
                # Limiter l'explication
                explanation = q_data.get('explanation', '')
                if len(explanation) > 1000:
                    explanation = explanation[:997] + "..."
                
                question = Questions(
                    text=q_data.get('text', ''),
                    options=options_list,
                    correct=correct_index,
                    explanation=explanation,
                    theme=theme
                )
                db.session.add(question)
                added_count += 1
                
                if i % 100 == 0:
                    print(f"[{i}/{len(questions_data)}] Traitement en cours...")
                
            except Exception as e:
                print(f"Erreur à la ligne {i}: {e}")
                continue
        
        # Commiter les changements
        db.session.commit()
        print(f"\n✓ {added_count} questions ont été importées avec succès !")
        
        # Afficher les statistiques
        total = Questions.query.count()
        themes = db.session.query(Questions.theme).distinct().all()
        print(f"Total questions: {total}")
        print(f"Nombre de thèmes: {len(themes)}")
        print(f"Thèmes: {', '.join([t[0][:50] for t in themes[:10]])}")

if __name__ == "__main__":
    import os
    json_file = "cisa_questions.json"
    
    if not os.path.exists(json_file):
        print(f"Erreur: Le fichier {json_file} n'existe pas.")
    else:
        print("Import du fichier JSON dans la base de données...")
        import_from_json(json_file)
