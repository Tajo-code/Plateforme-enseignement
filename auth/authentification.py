# auth/authentification.py — V4
import streamlit as st
import datetime
import secrets
import requests as req
from config import get_db, initialiser_firebase
from firebase_admin import auth
from models.journal import Journal

db = None
def _db():
    global db
    if db is None:
        db = get_db()
    return db

def _timestamp():
    return datetime.datetime.now().isoformat()

def est_connecte() -> bool:
    return "utilisateur" in st.session_state and st.session_state.utilisateur is not None

# ── Connexion ──────────────────────────────────────────────────────
def connecter_utilisateur(email: str, mot_de_passe: str) -> dict | None:
    initialiser_firebase()
    api_key = st.secrets["FIREBASE_API_KEY"]
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    try:
        reponse = req.post(url, json={"email": email, "password": mot_de_passe,
                                       "returnSecureToken": True}, timeout=10)
        data = reponse.json()
        if "error" in data:
            return None
        uid    = data["localId"]
        profil = _db().collection("users").document(uid).get().to_dict()
        if not profil:
            return None
        profil["uid"] = uid
        _db().collection("users").document(uid).update({
            "en_ligne": True, "derniere_connexion": _timestamp()
        })
        Journal.enregistrer(uid, f"{profil.get('nom','')} {profil.get('prenom','')}",
                            profil.get("role",""), "connexion")
        return profil
    except Exception:
        return None

def deconnecter() -> None:
    if est_connecte():
        u = st.session_state.utilisateur
        uid = u.get("uid")
        if uid:
            try:
                _db().collection("users").document(uid).update({"en_ligne": False})
                Journal.enregistrer(uid, f"{u.get('nom','')} {u.get('prenom','')}",
                                    u.get("role",""), "deconnexion")
            except Exception:
                pass
    st.session_state.clear()

# ── Vérifier mot de passe super admin ─────────────────────────────
def verifier_mot_de_passe(email: str, mot_de_passe: str) -> bool:
    """Vérifie le mot de passe avant une action critique."""
    initialiser_firebase()
    api_key = st.secrets["FIREBASE_API_KEY"]
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
    try:
        reponse = req.post(url, json={"email": email, "password": mot_de_passe,
                                       "returnSecureToken": True}, timeout=10)
        data = reponse.json()
        return "error" not in data
    except Exception:
        return False

# ── Inscription élève ──────────────────────────────────────────────
def inscrire_eleve(prenom, nom, email, mot_de_passe, telephone,
                   classe, code) -> tuple[bool, str]:
    initialiser_firebase()

    professeurs_ids    = []
    etablissements_ids = []

    # Chercher code professeur
    prof_docs = list(_db().collection("users")
                     .where("code_invitation","==",code.strip().upper())
                     .where("role","==","professeur").stream())
    if prof_docs:
        professeurs_ids.append(prof_docs[0].id)
        etab_ids = prof_docs[0].to_dict().get("etablissements_ids",[])
        if prof_docs[0].to_dict().get("etablissement_id"):
            etab_ids.append(prof_docs[0].to_dict()["etablissement_id"])
        etablissements_ids.extend(etab_ids)
    else:
        # Chercher code établissement
        from models.etablissement import Etablissement
        etab = Etablissement.get_par_code(code.strip().upper())
        if etab:
            etablissements_ids.append(etab["id"])
            # Trouver les profs de l'établissement
            profs = Etablissement.get_membres(etab["id"], "professeur")
            professeurs_ids = [p["id"] for p in profs]
        else:
            return False, "Code invalide."

    try:
        user = auth.create_user(email=email, password=mot_de_passe,
                                display_name=f"{nom} {prenom}")
        profil = {
            "uid":              user.uid,
            "prenom":           prenom.strip().capitalize(),
            "nom":              nom.strip().upper(),
            "email":            email.strip().lower(),
            "telephone":        telephone.strip(),
            "role":             "eleve",
            "classe":           classe,
            "professeurs_ids":  professeurs_ids,
            "etablissements_ids": etablissements_ids,
            "professeur_id":    professeurs_ids[0] if professeurs_ids else None,
            "etablissement_id": etablissements_ids[0] if etablissements_ids else None,
            "date_creation":    _timestamp(),
            "en_ligne":         False,
            "difficultes":      {},
            "abonnement_actif": True,
        }
        _db().collection("users").document(user.uid).set(profil)
        Journal.enregistrer(user.uid, f"{nom} {prenom}", "eleve", "creation_compte")
        return True, "Compte créé avec succès !"
    except Exception as e:
        return False, f"Erreur : {str(e)}"

# ── Inscription parent ─────────────────────────────────────────────
def inscrire_parent(prenom, nom, email, mot_de_passe,
                    telephone, code_etablissement) -> tuple[bool, str]:
    initialiser_firebase()
    from models.etablissement import Etablissement
    etab = Etablissement.get_par_code(code_etablissement.strip().upper())
    if not etab:
        return False, "Code établissement invalide."
    if not etab.get("actif", True):
        return False, "Cet établissement est suspendu."
    try:
        user = auth.create_user(email=email, password=mot_de_passe,
                                display_name=f"{nom} {prenom}")
        profil = {
            "uid":              user.uid,
            "prenom":           prenom.strip().capitalize(),
            "nom":              nom.strip().upper(),
            "email":            email.strip().lower(),
            "telephone":        telephone.strip(),
            "role":             "parent",
            "etablissement_id": etab["id"],
            "etablissements_ids": [etab["id"]],
            "enfants":          [],
            "date_creation":    _timestamp(),
            "en_ligne":         False,
            "abonnement_actif": True,
        }
        _db().collection("users").document(user.uid).set(profil)
        Journal.enregistrer(user.uid, f"{nom} {prenom}", "parent", "creation_compte",
                            f"Établissement: {etab['nom']}")
        return True, f"Compte créé ! Rattaché à **{etab['nom']}**."
    except Exception as e:
        return False, f"Erreur : {str(e)}"

# ── Création compte (super admin) ─────────────────────────────────
def creer_compte(prenom, nom, email, mot_de_passe, telephone, role,
                 matieres=None, etablissements_ids=None,
                 est_individuel=True) -> tuple[bool, str]:
    initialiser_firebase()
    try:
        user = auth.create_user(email=email, password=mot_de_passe,
                                display_name=f"{nom} {prenom}")
        profil = {
            "uid":              user.uid,
            "prenom":           prenom.strip().capitalize(),
            "nom":              nom.strip().upper(),
            "email":            email.strip().lower(),
            "telephone":        telephone.strip() if telephone else "",
            "role":             role,
            "date_creation":    _timestamp(),
            "en_ligne":         False,
            "abonnement_actif": True,
        }
        if role == "professeur":
            etab_ids = etablissements_ids or []
            profil["matieres"]           = matieres or []
            profil["code_invitation"]    = secrets.token_hex(4).upper()
            profil["etablissements_ids"] = etab_ids
            profil["etablissement_id"]   = etab_ids[0] if etab_ids else None
            profil["est_individuel"]     = est_individuel
        if role == "admin_etablissement":
            etab_ids = etablissements_ids or []
            profil["etablissements_ids"] = etab_ids
            profil["etablissement_id"]   = etab_ids[0] if etab_ids else None

        _db().collection("users").document(user.uid).set(profil)

        # Abonnement essai
        from models.abonnement import Abonnement
        Abonnement.creer_essai(user.uid, role)

        # Journal
        super_uid = st.session_state.utilisateur["uid"] if est_connecte() else "system"
        super_nom = f"{st.session_state.utilisateur.get('nom','')} {st.session_state.utilisateur.get('prenom','')}" if est_connecte() else "system"
        Journal.enregistrer(super_uid, super_nom, "super_admin", "creation_compte",
                            f"Nouveau {role}: {nom} {prenom} ({email})")
        return True, "Compte créé avec succès !"
    except Exception as e:
        return False, f"Erreur : {str(e)}"

# ── Réinitialisation mot de passe ──────────────────────────────────
def envoyer_reset_email(email: str) -> tuple[bool, str]:
    initialiser_firebase()
    api_key = st.secrets["FIREBASE_API_KEY"]
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    try:
        reponse = req.post(url, json={"requestType":"PASSWORD_RESET","email":email}, timeout=10)
        data = reponse.json()
        if "error" in data:
            return False, "Email introuvable."
        return True, "Email de réinitialisation envoyé !"
    except Exception as e:
        return False, f"Erreur : {str(e)}"

def changer_mot_de_passe(uid: str, nouveau_mdp: str) -> tuple[bool, str]:
    initialiser_firebase()
    try:
        auth.update_user(uid, password=nouveau_mdp)
        return True, "Mot de passe modifié !"
    except Exception as e:
        return False, f"Erreur : {str(e)}"

def supprimer_compte(uid: str) -> tuple[bool, str]:
    initialiser_firebase()
    try:
        auth.delete_user(uid)
        _db().collection("users").document(uid).delete()
        return True, "Compte supprimé."
    except Exception as e:
        return False, f"Erreur : {str(e)}"
