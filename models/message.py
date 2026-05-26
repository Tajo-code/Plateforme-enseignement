# models/message.py — Messagerie interne
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

class Message:
    """Message interne entre utilisateurs."""

    def __init__(self, expediteur_id: str, expediteur_nom: str,
                 destinataire_id: str, sujet: str, contenu: str,
                 etablissement_id: str = None, est_collectif: bool = False):
        self.id               = str(uuid.uuid4())
        self.expediteur_id    = expediteur_id
        self.expediteur_nom   = expediteur_nom
        self.destinataire_id  = destinataire_id  # "tous" si collectif
        self.sujet            = sujet
        self.contenu          = contenu
        self.etablissement_id = etablissement_id
        self.est_collectif    = est_collectif
        self.date_envoi       = _timestamp()
        self.lu               = False

    def envoyer(self) -> None:
        _db().collection("messages").document(self.id).set(self.to_dict())

    @staticmethod
    def get_recus(utilisateur_id: str, etablissement_id: str = None) -> list[dict]:
        """Récupère les messages reçus par un utilisateur."""
        # Messages directs
        docs_directs = list(
            _db().collection("messages")
            .where("destinataire_id", "==", utilisateur_id)
            .stream()
        )
        # Messages collectifs de l'établissement
        docs_collectifs = []
        if etablissement_id:
            docs_collectifs = list(
                _db().collection("messages")
                .where("etablissement_id", "==", etablissement_id)
                .where("est_collectif", "==", True)
                .stream()
            )
        tous = [{"id": d.id, **d.to_dict()} for d in docs_directs + docs_collectifs]
        return sorted(tous, key=lambda x: x.get("date_envoi", ""), reverse=True)

    @staticmethod
    def get_envoyes(expediteur_id: str) -> list[dict]:
        docs = (
            _db().collection("messages")
            .where("expediteur_id", "==", expediteur_id)
            .stream()
        )
        return sorted(
            [{"id": d.id, **d.to_dict()} for d in docs],
            key=lambda x: x.get("date_envoi", ""), reverse=True
        )

    @staticmethod
    def marquer_lu(message_id: str) -> None:
        _db().collection("messages").document(message_id).update({"lu": True})

    @staticmethod
    def nb_non_lus(utilisateur_id: str, etablissement_id: str = None) -> int:
        messages = Message.get_recus(utilisateur_id, etablissement_id)
        return len([m for m in messages if not m.get("lu", False)])

    def to_dict(self) -> dict:
        return {
            "id":               self.id,
            "expediteur_id":    self.expediteur_id,
            "expediteur_nom":   self.expediteur_nom,
            "destinataire_id":  self.destinataire_id,
            "sujet":            self.sujet,
            "contenu":          self.contenu,
            "etablissement_id": self.etablissement_id,
            "est_collectif":    self.est_collectif,
            "date_envoi":       self.date_envoi,
            "lu":               self.lu,
        }
