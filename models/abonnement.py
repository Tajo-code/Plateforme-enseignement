# models/abonnement.py
import datetime
import uuid
from config import get_db

db = None
def _db():
    global db
    if db is None:
        db = get_db()
    return db

def _timestamp():
    return datetime.datetime.now().isoformat()

# ── Forfaits configurables par le super admin ──────────────────────
FORFAITS_DEFAUT = {
    # Professeurs individuels
    "prof_mensuel":      {"label": "Professeur — Mensuel",     "duree_jours": 30,  "prix_fcfa": 5000,  "cible": "professeur"},
    "prof_trimestriel":  {"label": "Professeur — Trimestriel", "duree_jours": 90,  "prix_fcfa": 13000, "cible": "professeur"},
    "prof_annuel":       {"label": "Professeur — Annuel",      "duree_jours": 365, "prix_fcfa": 45000, "cible": "professeur"},
    # Établissements
    "etab_petit":        {"label": "Établissement Petit",      "duree_jours": 365, "prix_fcfa": 100000, "cible": "etablissement"},
    "etab_moyen":        {"label": "Établissement Moyen",      "duree_jours": 365, "prix_fcfa": 200000, "cible": "etablissement"},
    "etab_grand":        {"label": "Établissement Grand",      "duree_jours": 365, "prix_fcfa": 350000, "cible": "etablissement"},
}

class Abonnement:
    """Gère les abonnements avec période d'essai gratuite."""

    JOURS_ESSAI = 30  # 1 mois gratuit

    def __init__(self, utilisateur_id: str, type_utilisateur: str,
                 forfait_id: str = None, est_essai: bool = True):
        self.id               = str(uuid.uuid4())
        self.utilisateur_id   = utilisateur_id
        self.type_utilisateur = type_utilisateur
        self.forfait_id       = forfait_id
        self.est_essai        = est_essai
        self.date_debut       = datetime.datetime.now()
        self.date_fin         = self.date_debut + datetime.timedelta(
            days=self.JOURS_ESSAI if est_essai else
            self._duree_forfait(forfait_id)
        )
        self.actif            = True
        self.prolonge_par     = None  # uid du super_admin qui a prolongé

    def _duree_forfait(self, forfait_id: str) -> int:
        forfaits = self._get_forfaits()
        return forfaits.get(forfait_id, {}).get("duree_jours", 30)

    def _get_forfaits(self) -> dict:
        doc = _db().collection("config").document("forfaits").get()
        if doc.exists:
            return doc.to_dict()
        return FORFAITS_DEFAUT

    def est_valide(self) -> bool:
        return self.actif and datetime.datetime.now() < self.date_fin

    def jours_restants(self) -> int:
        delta = self.date_fin - datetime.datetime.now()
        return max(0, delta.days)

    def sauvegarder(self) -> None:
        _db().collection("abonnements").document(self.id).set(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "utilisateur_id":   self.utilisateur_id,
            "type_utilisateur": self.type_utilisateur,
            "forfait_id":       self.forfait_id,
            "est_essai":        self.est_essai,
            "date_debut":       self.date_debut.isoformat(),
            "date_fin":         self.date_fin.isoformat(),
            "actif":            self.actif,
            "prolonge_par":     self.prolonge_par,
        }

    @staticmethod
    def creer_essai(utilisateur_id: str, type_utilisateur: str) -> "Abonnement":
        """Crée un abonnement d'essai gratuit de 30 jours."""
        abo = Abonnement(utilisateur_id, type_utilisateur, est_essai=True)
        abo.sauvegarder()
        doc = _db().collection("users").document(utilisateur_id).get()
        if doc.exists:
            _db().collection("users").document(utilisateur_id).update({
                "abonnement_id":    abo.id,
                "abonnement_actif": True,
                "abonnement_fin":   abo.date_fin.isoformat(),
            })
        else:
            _db().collection("etablissements").document(utilisateur_id).update({
                "abonnement_id":    abo.id,
                "abonnement_actif": True,
                "abonnement_fin":   abo.date_fin.isoformat(),
    })
        
        return abo

    @staticmethod
    def get_actif(utilisateur_id: str) -> dict | None:
        docs = list(
            _db().collection("abonnements")
            .where("utilisateur_id", "==", utilisateur_id)
            .where("actif", "==", True)
            .stream()
        )
        return {"id": docs[0].id, **docs[0].to_dict()} if docs else None

    @staticmethod
    def verifier_et_suspendre(utilisateur_id: str) -> bool:
        """Vérifie si l'abonnement est expiré et suspend immédiatement."""
        abo = Abonnement.get_actif(utilisateur_id)
        if not abo:
            return False
        date_fin = datetime.datetime.fromisoformat(abo["date_fin"])
        if datetime.datetime.now() > date_fin:
            _db().collection("abonnements").document(abo["id"]).update({"actif": False})
            _db().collection("users").document(utilisateur_id).update({
                "abonnement_actif": False
            })
            return False
        return True

    @staticmethod
    def prolonger(utilisateur_id: str, jours: int, super_admin_id: str) -> None:
        """Super admin prolonge un abonnement."""
        abo = Abonnement.get_actif(utilisateur_id)
        if abo:
            date_fin_actuelle = datetime.datetime.fromisoformat(abo["date_fin"])
            nouvelle_fin = date_fin_actuelle + datetime.timedelta(days=jours)
            _db().collection("abonnements").document(abo["id"]).update({
                "date_fin":     nouvelle_fin.isoformat(),
                "actif":        True,
                "prolonge_par": super_admin_id,
            })
            _db().collection("users").document(utilisateur_id).update({
                "abonnement_actif": True,
                "abonnement_fin":   nouvelle_fin.isoformat(),
            })

    @staticmethod
    def get_forfaits() -> dict:
        doc = _db().collection("config").document("forfaits").get()
        if doc.exists:
            return doc.to_dict()
        return FORFAITS_DEFAUT

    @staticmethod
    def sauvegarder_forfaits(forfaits: dict) -> None:
        """Super admin modifie les forfaits."""
        _db().collection("config").document("forfaits").set(forfaits)
