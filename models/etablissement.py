# models/etablissement.py
import datetime
import secrets
from config import get_db

db = None
def _db():
    global db
    if db is None:
        db = get_db()
    return db

def _timestamp():
    return datetime.datetime.now().isoformat()

TAILLES = {
    "petit":  {"label": "Petit (< 200 élèves)",   "max_eleves": 200},
    "moyen":  {"label": "Moyen (200-500 élèves)",  "max_eleves": 500},
    "grand":  {"label": "Grand (> 500 élèves)",    "max_eleves": 9999},
}

class Etablissement:
    """Représente un établissement scolaire."""

    def __init__(self, nom: str, ville: str, taille: str, super_admin_id: str):
        self.id               = secrets.token_hex(4).upper()  # ID unique ex: A3F7B2C1
        self.nom              = nom.strip()
        self.ville            = ville.strip()
        self.taille           = taille
        self.super_admin_id   = super_admin_id
        self.date_creation    = _timestamp()
        self.actif            = True
        self.code_invitation  = secrets.token_hex(6).upper()  # code pour rejoindre
        self.abonnement_id    = None

    def sauvegarder(self) -> None:
        _db().collection("etablissements").document(self.id).set(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id":              self.id,
            "nom":             self.nom,
            "ville":           self.ville,
            "taille":          self.taille,
            "super_admin_id":  self.super_admin_id,
            "date_creation":   self.date_creation,
            "actif":           self.actif,
            "code_invitation": self.code_invitation,
            "abonnement_id":   self.abonnement_id,
        }

    @staticmethod
    def get(etab_id: str) -> dict | None:
        doc = _db().collection("etablissements").document(etab_id).get()
        return {"id": doc.id, **doc.to_dict()} if doc.exists else None

    @staticmethod
    def get_tous() -> list[dict]:
        docs = _db().collection("etablissements").stream()
        return [{"id": d.id, **d.to_dict()} for d in docs]

    @staticmethod
    def get_par_code(code: str) -> dict | None:
        docs = list(
            _db().collection("etablissements")
            .where("code_invitation", "==", code.strip().upper())
            .stream()
        )
        if docs:
            return {"id": docs[0].id, **docs[0].to_dict()}
        return None

    @staticmethod
    def suspendre(etab_id: str) -> None:
        _db().collection("etablissements").document(etab_id).update({"actif": False})

    @staticmethod
    def reactiver(etab_id: str) -> None:
        _db().collection("etablissements").document(etab_id).update({"actif": True})

    @staticmethod
    def get_membres(etab_id: str, role: str = None) -> list[dict]:
        q = _db().collection("users").where("etablissement_id", "==", etab_id)
        if role:
            q = q.where("role", "==", role)
        return [{"id": d.id, **d.to_dict()} for d in q.stream()]
