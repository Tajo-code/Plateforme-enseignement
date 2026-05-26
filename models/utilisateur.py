# models/utilisateur.py
import datetime
from config import get_db

db = None

def _db():
    global db
    if db is None:
        db = get_db()
    return db

def _timestamp():
    return datetime.datetime.now().isoformat()

class Utilisateur:
    def __init__(self, uid, prenom, nom, email, role, telephone=""):
        self.uid       = uid
        self.prenom    = prenom.strip().capitalize()
        self.nom       = nom.strip().upper()
        self.email     = email.strip().lower()
        self.telephone = telephone.strip()
        self.role      = role
        self.date_creation = _timestamp()

    @property
    def nom_complet(self):
        return f"{self.nom} {self.prenom}"

    def to_dict(self):
        return {
            "uid":           self.uid,
            "prenom":        self.prenom,
            "nom":           self.nom,
            "email":         self.email,
            "telephone":     self.telephone,
            "role":          self.role,
            "date_creation": self.date_creation,
            "en_ligne":      False,
        }

    def sauvegarder(self):
        _db().collection("users").document(self.uid).set(self.to_dict())

    @staticmethod
    def get(uid):
        doc = _db().collection("users").document(uid).get()
        return doc.to_dict() if doc.exists else None


class Eleve(Utilisateur):
    CLASSES_VALIDES = {"1": "6e", "2": "5e", "3": "4e", "4": "1ère", "5": "Tle"}

    def __init__(self, uid, prenom, nom, email, telephone, classe, professeur_id):
        super().__init__(uid, prenom, nom, email, "eleve", telephone)
        self.classe        = classe
        self.professeur_id = professeur_id
        self.difficultes   = {}

    def to_dict(self):
        d = super().to_dict()
        d.update({
            "classe":         self.classe,
            "professeur_id":  self.professeur_id,
            "difficultes":    self.difficultes,
        })
        return d

    @staticmethod
    def get_travaux(eleve_id):
        docs = _db().collection("travaux").where("eleve_id", "==", eleve_id).stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_travaux_publies(eleve_id):
        docs = (
            _db().collection("travaux")
            .where("eleve_id", "==", eleve_id)
            .where("statut", "==", "publié")
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_difficultes(eleve_id):
        doc = _db().collection("users").document(eleve_id).get()
        if doc.exists:
            return doc.to_dict().get("difficultes", {})
        return {}

    @staticmethod
    def get_exercices_adaptes(eleve_id, prof_id, classe):
        """Retourne les exercices adaptés aux difficultés de l'élève."""
        difficultes = Eleve.get_difficultes(eleve_id)
        exercices = []
        for matiere, diffi_list in difficultes.items():
            docs = (
                _db().collection("exercices_qcm")
                .where("prof_id", "==", prof_id)
                .where("classe", "==", classe)
                .where("matiere", "==", matiere)
                .stream()
            )
            for doc in docs:
                ex = {"id": doc.id, **doc.to_dict()}
                exercices.append(ex)
        return exercices


class Professeur(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone, matieres):
        super().__init__(uid, prenom, nom, email, "professeur", telephone)
        self.matieres = matieres

    def to_dict(self):
        d = super().to_dict()
        d.update({"matieres": self.matieres})
        return d

    @staticmethod
    def get_eleves(prof_id, classe=None):
        q = _db().collection("users").where("professeur_id", "==", prof_id).where("role", "==", "eleve")
        if classe:
            q = q.where("classe", "==", classe)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]

    @staticmethod
    def get_nb_eleves(prof_id):
        eleves = Professeur.get_eleves(prof_id)
        return len(eleves)

    @staticmethod
    def get_travaux_a_corriger(prof_id, classe=None, eleve_id=None, statut=None):
        q = _db().collection("travaux").where("prof_id", "==", prof_id)
        if classe:
            q = q.where("classe", "==", classe)
        if eleve_id:
            q = q.where("eleve_id", "==", eleve_id)
        if statut:
            q = q.where("statut", "==", statut)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]

    @staticmethod
    def publier_corrections(prof_id):
        docs = (
            _db().collection("travaux")
            .where("prof_id", "==", prof_id)
            .where("statut", "==", "corrigé")
            .stream()
        )
        count = 0
        for doc in docs:
            _db().collection("travaux").document(doc.id).update({
                "statut":      "publié",
                "date_publie": datetime.datetime.now().isoformat(),
            })
            count += 1
        return count

    @staticmethod
    def get_exercices_publies(prof_id, classe=None):
        q = _db().collection("exercices_publies").where("prof_id", "==", prof_id)
        if classe:
            q = q.where("classe", "==", classe)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]


class Administrateur(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone):
        super().__init__(uid, prenom, nom, email, "admin", telephone)

    @staticmethod
    def get_tous_professeurs():
        docs = _db().collection("users").where("role", "==", "professeur").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_travaux_professeur(prof_id):
        docs = _db().collection("travaux").where("prof_id", "==", prof_id).stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]


class SuperAdmin(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone):
        super().__init__(uid, prenom, nom, email, "super_admin", telephone)

    @staticmethod
    def get_tous_utilisateurs():
        docs = _db().collection("users").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def supprimer_utilisateur(uid):
        _db().collection("users").document(uid).delete()
