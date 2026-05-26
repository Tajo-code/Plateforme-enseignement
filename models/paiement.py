# models/paiement.py — MTN Mobile Money + Orange Money (FCFA)
import datetime
import uuid
import requests
from config import get_db
import streamlit as st

db = None
def _db():
    global db
    if db is None:
        db = get_db()
    return db

def _timestamp():
    return datetime.datetime.now().isoformat()

class Paiement:
    """
    Gère les paiements via MTN MoMo et Orange Money au Cameroun.
    Intégration via CinetPay — agrégateur de paiement camerounais
    qui supporte MTN MoMo et Orange Money.
    """

    OPERATEURS = {
        "mtn":    "MTN Mobile Money",
        "orange": "Orange Money",
    }

    def __init__(self, utilisateur_id: str, forfait_id: str,
                 montant_fcfa: int, operateur: str, telephone: str):
        self.id             = str(uuid.uuid4())
        self.utilisateur_id = utilisateur_id
        self.forfait_id     = forfait_id
        self.montant_fcfa   = montant_fcfa
        self.operateur      = operateur
        self.telephone      = telephone
        self.statut         = "en_attente"  # en_attente | confirme | echoue
        self.date_creation  = _timestamp()
        self.transaction_id = None
        self.date_confirmation = None

    def initier(self) -> dict:
        """
        Initie un paiement via CinetPay.
        Retourne l'URL de paiement ou les instructions USSD.
        """
        try:
            api_key    = st.secrets.get("CINETPAY_API_KEY", "")
            site_id    = st.secrets.get("CINETPAY_SITE_ID", "")

            if not api_key or not site_id:
                # Mode simulation si pas de clés configurées
                return self._simulation()

            payload = {
                "apikey":          api_key,
                "site_id":         site_id,
                "transaction_id":  self.id,
                "amount":          self.montant_fcfa,
                "currency":        "XAF",  # FCFA
                "description":     f"Abonnement plateforme — {self.forfait_id}",
                "customer_phone_number": self.telephone,
                "channels":        "MOBILE_MONEY",
                "notify_url":      st.secrets.get("NOTIFY_URL", ""),
                "metadata":        f"user:{self.utilisateur_id}|forfait:{self.forfait_id}",
            }

            reponse = requests.post(
                "https://api-checkout.cinetpay.com/v2/payment",
                json=payload, timeout=30
            )
            data = reponse.json()

            if data.get("code") == "201":
                self.transaction_id = data["data"]["payment_token"]
                self.sauvegarder()
                return {
                    "succes":      True,
                    "url":         data["data"]["payment_url"],
                    "message":     "Redirection vers le paiement...",
                    "transaction": self.transaction_id,
                }
            else:
                return {"succes": False, "message": data.get("message", "Erreur de paiement.")}

        except Exception as e:
            return {"succes": False, "message": f"Erreur : {str(e)}"}

    def _simulation(self) -> dict:
        """Mode simulation pour les tests sans clés CinetPay."""
        self.transaction_id = f"SIM_{self.id[:8].upper()}"
        self.statut         = "confirme"
        self.date_confirmation = _timestamp()
        self.sauvegarder()
        return {
            "succes":      True,
            "simulation":  True,
            "message":     f"[SIMULATION] Paiement de {self.montant_fcfa} FCFA via {self.OPERATEURS[self.operateur]} simulé avec succès.",
            "transaction": self.transaction_id,
        }

    @staticmethod
    def confirmer(transaction_id: str) -> bool:
        """Confirme un paiement et active l'abonnement."""
        docs = list(
            _db().collection("paiements")
            .where("transaction_id", "==", transaction_id)
            .stream()
        )
        if not docs:
            return False

        paiement = {"id": docs[0].id, **docs[0].to_dict()}
        _db().collection("paiements").document(paiement["id"]).update({
            "statut":             "confirme",
            "date_confirmation":  _timestamp(),
        })

        # Activer l'abonnement
        from models.abonnement import Abonnement
        forfaits = Abonnement.get_forfaits()
        forfait  = forfaits.get(paiement["forfait_id"], {})
        duree    = forfait.get("duree_jours", 30)
        Abonnement.prolonger(
            paiement["utilisateur_id"], duree, "system"
        )
        return True

    def sauvegarder(self) -> None:
        _db().collection("paiements").document(self.id).set(self.to_dict())

    def to_dict(self) -> dict:
        return {
            "id":                  self.id,
            "utilisateur_id":      self.utilisateur_id,
            "forfait_id":          self.forfait_id,
            "montant_fcfa":        self.montant_fcfa,
            "operateur":           self.operateur,
            "telephone":           self.telephone,
            "statut":              self.statut,
            "date_creation":       self.date_creation,
            "transaction_id":      self.transaction_id,
            "date_confirmation":   self.date_confirmation,
        }

    @staticmethod
    def get_historique(utilisateur_id: str) -> list[dict]:
        docs = (
            _db().collection("paiements")
            .where("utilisateur_id", "==", utilisateur_id)
            .stream()
        )
        return [{"id": d.id, **d.to_dict()} for d in docs]
