# models/utilisateur.py — V4 multi-établissements
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
    CLASSES_VALIDES = {"1":"6e","2":"5e","3":"4e","4":"1ère","5":"Tle"}

    def __init__(self, uid, prenom, nom, email, telephone, classe,
                 professeurs_ids: list, etablissements_ids: list):
        super().__init__(uid, prenom, nom, email, "eleve", telephone)
        self.classe             = classe
        # Listes pour multi-appartenance
        self.professeurs_ids    = professeurs_ids    # [prof_id1, prof_id2, ...]
        self.etablissements_ids = etablissements_ids # [etab_id1, etab_id2, ...]
        # Compatibilité ancien code
        self.professeur_id      = professeurs_ids[0] if professeurs_ids else None
        self.etablissement_id   = etablissements_ids[0] if etablissements_ids else None
        self.difficultes        = {}

    def to_dict(self):
        d = super().to_dict()
        d.update({
            "classe":             self.classe,
            "professeurs_ids":    self.professeurs_ids,
            "etablissements_ids": self.etablissements_ids,
            "professeur_id":      self.professeur_id,
            "etablissement_id":   self.etablissement_id,
            "difficultes":        self.difficultes,
        })
        return d

    @staticmethod
    def get_travaux(eleve_id):
        docs = _db().collection("travaux").where("eleve_id","==",eleve_id).stream()
        return [{"id":d.id,**d.to_dict()} for d in docs]

    @staticmethod
    def get_travaux_publies(eleve_id):
        docs = (_db().collection("travaux")
                .where("eleve_id","==",eleve_id)
                .where("statut","==","publié")
                .stream())
        return [{"id":d.id,**d.to_dict()} for d in docs]

    @staticmethod
    def get_difficultes(eleve_id):
        doc = _db().collection("users").document(eleve_id).get()
        return doc.to_dict().get("difficultes",{}) if doc.exists else {}

    @staticmethod
    def get_exercices_adaptes(eleve_id, prof_id, classe):
        difficultes = Eleve.get_difficultes(eleve_id)
        exercices   = []
        for matiere in difficultes.keys():
            docs = (_db().collection("exercices_qcm")
                    .where("prof_id","==",prof_id)
                    .where("classe","==",classe)
                    .where("matiere","==",matiere)
                    .stream())
            for doc in docs:
                exercices.append({"id":doc.id,**doc.to_dict()})
        return exercices


class Professeur(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone, matieres,
                 etablissements_ids: list = None, est_individuel: bool = True):
        super().__init__(uid, prenom, nom, email, "professeur", telephone)
        self.matieres           = matieres
        self.etablissements_ids = etablissements_ids or []
        self.est_individuel     = est_individuel
        # Compatibilité
        self.etablissement_id   = etablissements_ids[0] if etablissements_ids else None

    def to_dict(self):
        d = super().to_dict()
        d.update({
            "matieres":           self.matieres,
            "etablissements_ids": self.etablissements_ids,
            "etablissement_id":   self.etablissement_id,
            "est_individuel":     self.est_individuel,
        })
        return d

    @staticmethod
    def get_eleves(prof_id: str, classe: str = None) -> list[dict]:
        """
        Récupère les élèves liés à ce professeur :
        - par professeur_id direct
        - par professeurs_ids (liste)
        - par établissement commun
        """
        try:
            prof_doc = _db().collection("users").document(prof_id).get()
            etab_ids = []
            if prof_doc.exists:
                data = prof_doc.to_dict()
                etab_ids = data.get("etablissements_ids", [])
                if data.get("etablissement_id"):
                    etab_ids.append(data["etablissement_id"])
                etab_ids = list(set(etab_ids))

            # Récupérer tous les élèves
            docs   = list(_db().collection("users").where("role","==","eleve").stream())
            eleves = []
            for d in docs:
                data = d.to_dict()
                # Lié directement au prof
                if data.get("professeur_id") == prof_id:
                    eleves.append({"id":d.id,**data})
                    continue
                # Dans la liste des profs de l'élève
                if prof_id in data.get("professeurs_ids",[]):
                    eleves.append({"id":d.id,**data})
                    continue
                # Dans le même établissement
                eleve_etabs = data.get("etablissements_ids",[])
                if data.get("etablissement_id"):
                    eleve_etabs.append(data["etablissement_id"])
                if any(e in etab_ids for e in eleve_etabs):
                    eleves.append({"id":d.id,**data})

            if classe:
                eleves = [e for e in eleves if e.get("classe") == classe]
            # Dédupliquer
            seen = set()
            result = []
            for e in eleves:
                if e["id"] not in seen:
                    seen.add(e["id"])
                    result.append(e)
            return result
        except Exception:
            return []

    @staticmethod
    def get_nb_eleves(prof_id: str) -> int:
        return len(Professeur.get_eleves(prof_id))

    @staticmethod
    def get_travaux_a_corriger(prof_id: str, classe: str = None,
                                eleve_id: str = None, statut: str = None) -> list[dict]:
        """
        Récupère les travaux des élèves liés à ce professeur.
        Inclut les travaux soumis via établissement commun.
        """
        try:
            # IDs des élèves de ce prof
            eleves    = Professeur.get_eleves(prof_id)
            eleve_ids = [e["id"] for e in eleves]

            if eleve_id:
                eleve_ids = [eleve_id] if eleve_id in eleve_ids else []

            all_travaux = []
            # Travaux directs au prof
            q = _db().collection("travaux").where("prof_id","==",prof_id)
            if classe:
                q = q.where("classe","==",classe)
            if statut:
                q = q.where("statut","==",statut)
            all_travaux += [{"id":d.id,**d.to_dict()} for d in q.stream()]

            # Travaux des élèves liés (même établissement)
            for eid in eleve_ids:
                q2 = _db().collection("travaux").where("eleve_id","==",eid)
                if statut:
                    q2 = q2.where("statut","==",statut)
                for d in q2.stream():
                    t = {"id":d.id,**d.to_dict()}
                    # Éviter doublons
                    if not any(x["id"] == t["id"] for x in all_travaux):
                        all_travaux.append(t)

            if classe:
                all_travaux = [t for t in all_travaux if t.get("classe") == classe]
            return all_travaux
        except Exception:
            return []

    @staticmethod
    def get_exercices_publies(prof_id: str, classe: str = None) -> list[dict]:
        """Récupère les exercices publiés par ce prof."""
        q = _db().collection("exercices_publies").where("prof_id","==",prof_id)
        if classe:
            q = q.where("classe","==",classe)
        return [{"id":d.id,**d.to_dict()} for d in q.stream()]

    @staticmethod
    def get_exercices_etablissement(etab_id: str, classe: str = None) -> list[dict]:
        """Récupère tous les exercices publiés dans un établissement."""
        # Trouver tous les profs de l'établissement
        profs = list(_db().collection("users")
                     .where("role","==","professeur")
                     .stream())
        exercices = []
        for p in profs:
            data = p.to_dict()
            etabs = data.get("etablissements_ids",[])
            if data.get("etablissement_id"):
                etabs.append(data["etablissement_id"])
            if etab_id in etabs:
                q = _db().collection("exercices_publies").where("prof_id","==",p.id)
                if classe:
                    q = q.where("classe","==",classe)
                for d in q.stream():
                    exercices.append({"id":d.id,**d.to_dict()})
        return exercices

    @staticmethod
    def publier_corrections(prof_id: str) -> int:
        corriges = (_db().collection("travaux")
                    .where("prof_id","==",prof_id)
                    .where("statut","==","corrigé")
                    .stream())
        count = 0
        for doc in corriges:
            _db().collection("travaux").document(doc.id).update({
                "statut":      "publié",
                "date_publie": _timestamp(),
            })
            count += 1
        return count


class Administrateur(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone):
        super().__init__(uid, prenom, nom, email, "admin", telephone)

    @staticmethod
    def get_tous_professeurs():
        docs = _db().collection("users").where("role","==","professeur").stream()
        return [{"id":d.id,**d.to_dict()} for d in docs]

    @staticmethod
    def get_travaux_professeur(prof_id):
        docs = _db().collection("travaux").where("prof_id","==",prof_id).stream()
        return [{"id":d.id,**d.to_dict()} for d in docs]


class SuperAdmin(Utilisateur):
    def __init__(self, uid, prenom, nom, email, telephone):
        super().__init__(uid, prenom, nom, email, "super_admin", telephone)

    @staticmethod
    def get_tous_utilisateurs():
        docs = _db().collection("users").stream()
        return [{"id":d.id,**d.to_dict()} for d in docs]

    @staticmethod
    def supprimer_utilisateur(uid):
        _db().collection("users").document(uid).delete()
