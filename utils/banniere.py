# utils/banniere.py — Bannière permanente d'abonnement
import streamlit as st
import datetime
from models.abonnement import Abonnement


def afficher_banniere_abonnement(utilisateur: dict) -> bool:
    """
    Affiche une bannière permanente en haut de l'écran
    si l'abonnement expire bientôt ou est expiré.
    Retourne True si l'abonnement est valide, False sinon.
    """
    uid = utilisateur.get("uid")
    role = utilisateur.get("role")

    # Les élèves, parents et admins établissements ne paient pas directement
    if role in ["eleve", "parent", "admin_etablissement", "super_admin"]:
        return True

    # Vérifier l'abonnement
    abonnement_fin = utilisateur.get("abonnement_fin")
    abonnement_actif = utilisateur.get("abonnement_actif", True)

    if not abonnement_fin:
        return True

    try:
        date_fin = datetime.datetime.fromisoformat(abonnement_fin)
        maintenant = datetime.datetime.now()
        jours_restants = (date_fin - maintenant).days

        if not abonnement_actif or maintenant > date_fin:
            # Compte suspendu
            st.markdown("""
            <div style="
                background-color: #ff4444;
                color: white;
                padding: 12px 20px;
                text-align: center;
                font-weight: bold;
                font-size: 15px;
                position: sticky;
                top: 0;
                z-index: 9999;
                border-radius: 0 0 8px 8px;
            ">
                ⛔ Votre abonnement a expiré. Renouvelez pour continuer à utiliser la plateforme.
                Contactez le support si vous pensez que c'est une erreur.
            </div>
            """, unsafe_allow_html=True)
            return False

        elif jours_restants <= 7:
            # Expiration imminente — bannière orange
            couleur = "#ff8800" if jours_restants > 3 else "#ff4444"
            st.markdown(f"""
            <div style="
                background-color: {couleur};
                color: white;
                padding: 10px 20px;
                text-align: center;
                font-weight: bold;
                font-size: 14px;
                border-radius: 0 0 8px 8px;
            ">
                ⚠️ Votre abonnement expire dans <b>{jours_restants} jour(s)</b>.
                Renouvelez maintenant pour éviter la suspension de votre compte.
                &nbsp;&nbsp;
                <a href="?page=paiement" style="color:white;text-decoration:underline;">
                    → Renouveler
                </a>
            </div>
            """, unsafe_allow_html=True)
            return True

        elif jours_restants <= 30 and utilisateur.get("abonnement_essai"):
            # Période d'essai — bannière bleue informative
            st.markdown(f"""
            <div style="
                background-color: #1a1a2e;
                color: white;
                padding: 8px 20px;
                text-align: center;
                font-size: 13px;
                border-radius: 0 0 8px 8px;
            ">
                🎁 Période d'essai gratuite — <b>{jours_restants} jour(s) restant(s)</b>.
                Abonnez-vous pour continuer après l'essai.
                &nbsp;&nbsp;
                <a href="?page=paiement" style="color:#4fc3f7;text-decoration:underline;">
                    → Voir les forfaits
                </a>
            </div>
            """, unsafe_allow_html=True)
            return True

    except Exception:
        pass

    return True
