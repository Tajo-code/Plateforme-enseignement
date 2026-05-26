# models/travail.py
import datetime
import uuid
from config import get_db, get_bucket

db = None

def _db():
    global db
    if db is None:
        db = get_db()
    return db

class Travail:
    """
    Cycle : soumis → corrigé → publié
    """
    STATUTS = ["soumis", "corrigé", "publié"]
    FORMATS = ["Devoir individuel", "Travail de groupe", "QCM", "Rédaction", "Exposé"]

    def __init__(self, eleve_id: str, eleve_nom: str, prof_id: str,
                 classe: str, matiere: str, discipline: str, format_travail: str = "Devoir individuel"):
        self.id             = str(uuid.uuid4())
        self.eleve_id       = eleve_id
        self.eleve_nom      = eleve_nom
        self.prof_id        = prof_id
        self.classe         = classe
        self.matiere        = matiere
        self.discipline     = discipline
        self.format_travail = format_travail
        self.date_soumis    = datetime.datetime.now().isoformat()
        self.statut         = "soumis"
        self.contenu_texte  = ""
        self.fichier_url    = ""
        self.nom_fichier    = ""
        self.note           = None
        self.remarques      = ""
        self.date_corrige   = None
        self.date_publie    = None
        self.note_auto      = None   # note attribuée automatiquement
        self.difficultes    = []     # difficultés détectées

    def soumettre_texte(self, contenu: str) -> None:
        self.contenu_texte = contenu
        self.sauvegarder()

    def soumettre_fichier(self, fichier_bytes: bytes, nom_fichier: str) -> str:
        bucket = get_bucket()
        chemin = f"travaux/{self.prof_id}/{self.classe}/{self.eleve_id}/{self.id}_{nom_fichier}"
        blob = bucket.blob(chemin)
        blob.upload_from_string(fichier_bytes, content_type="application/octet-stream")
        blob.make_public()
        self.fichier_url = blob.public_url
        self.nom_fichier = nom_fichier
        self.sauvegarder()
        return self.fichier_url

    @staticmethod
    def corriger(travail_id: str, note: float, remarques: str) -> None:
        if not (0 <= note <= 20):
            raise ValueError("La note doit être entre 0 et 20.")
        _db().collection("travaux").document(travail_id).update({
            "note":         note,
            "remarques":    remarques,
            "statut":       "corrigé",
            "date_corrige": datetime.datetime.now().isoformat(),
        })

    @staticmethod
    def publier(travail_id: str) -> None:
        _db().collection("travaux").document(travail_id).update({
            "statut":      "publié",
            "date_publie": datetime.datetime.now().isoformat(),
        })

    @staticmethod
    def get(travail_id: str) -> dict | None:
        doc = _db().collection("travaux").document(travail_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    def sauvegarder(self) -> None:
        _db().collection("travaux").document(self.id).set(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id":             self.id,
            "eleve_id":       self.eleve_id,
            "eleve_nom":      self.eleve_nom,
            "prof_id":        self.prof_id,
            "classe":         self.classe,
            "matiere":        self.matiere,
            "discipline":     self.discipline,
            "format_travail": self.format_travail,
            "date_soumis":    self.date_soumis,
            "statut":         self.statut,
            "contenu_texte":  self.contenu_texte,
            "fichier_url":    self.fichier_url,
            "nom_fichier":    self.nom_fichier,
            "note":           self.note,
            "remarques":      self.remarques,
            "date_corrige":   self.date_corrige,
            "date_publie":    self.date_publie,
            "note_auto":      self.note_auto,
            "difficultes":    self.difficultes,
        }


# ── Exercices QCM avec correction automatique ──────────────────────
class ExerciceQCM:
    """Exercice à choix multiples avec correction et note automatiques."""

    def __init__(self, titre: str, matiere: str, classe: str,
                 prof_id: str, questions: list[dict]):
        self.id        = str(uuid.uuid4())
        self.titre     = titre
        self.matiere   = matiere
        self.classe    = classe
        self.prof_id   = prof_id
        self.questions = questions  # [{question, choix, bonne_reponse, difficulte}]
        self.date_creation = datetime.datetime.now().isoformat()

    def sauvegarder(self) -> None:
        _db().collection("exercices_qcm").document(self.id).set(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id":            self.id,
            "titre":         self.titre,
            "matiere":       self.matiere,
            "classe":        self.classe,
            "prof_id":       self.prof_id,
            "questions":     self.questions,
            "date_creation": self.date_creation,
        }

    @staticmethod
    def corriger_automatiquement(exercice_id: str, eleve_id: str,
                                  reponses: dict) -> dict:
        """
        Corrige automatiquement un QCM et retourne note + difficultés détectées.
        reponses = {question_id: reponse_choisie}
        """
        doc = _db().collection("exercices_qcm").document(exercice_id).get()
        if not doc.exists:
            return {"note": 0, "difficultes": []}

        exercice = doc.to_dict()
        questions = exercice.get("questions", [])
        total = len(questions)
        correctes = 0
        difficultes = []

        for q in questions:
            q_id = q.get("id", "")
            bonne = q.get("bonne_reponse", "")
            reponse_eleve = reponses.get(q_id, "")
            if reponse_eleve == bonne:
                correctes += 1
            else:
                difficultes.append(q.get("difficulte", q.get("question", "")))

        note = round((correctes / total) * 20, 1) if total > 0 else 0

        # Sauvegarder le résultat
        _db().collection("resultats_qcm").add({
            "exercice_id": exercice_id,
            "eleve_id":    eleve_id,
            "note":        note,
            "difficultes": difficultes,
            "date":        datetime.datetime.now().isoformat(),
        })

        # Mettre à jour les difficultés de l'élève
        eleve_doc = _db().collection("users").document(eleve_id).get()
        if eleve_doc.exists:
            eleve_data = eleve_doc.to_dict()
            diffi_existantes = eleve_data.get("difficultes", {})
            matiere = exercice.get("matiere", "")
            diffi_existantes[matiere] = list(set(
                diffi_existantes.get(matiere, []) + difficultes
            ))
            _db().collection("users").document(eleve_id).update({
                "difficultes": diffi_existantes
            })

        return {"note": note, "correctes": correctes, "total": total,
                "difficultes": difficultes}
