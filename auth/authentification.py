# auth/authentification.py — V3 complète
import streamlit as st
import datetime
import secrets
import requests as req
from config import get_db, initialiser_firebase
from firebase_admin import auth

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
    payload = {"email": email, "password": mot_de_passe, "returnSecureToken": True}
    try:
        reponse = req.post(url, json=payload, timeout=10)
        data    = reponse.json()
        if "error" in data:
            return None
        uid    = data["localId"]
        profil = _db().collection("users").document(uid).get().to_dict()
        if not profil:
            return None

        # Vérifier si le compte est suspendu
        if not profil.get("abonnement_actif", True):
            from models.abonnement import Abonnement
            valide = Abonnement.verifier_et_suspendre(uid)
            if not valide:
                profil["abonnement_actif"] = False

        profil["uid"] = uid
        _db().collection("users").document(uid).update({
            "en_ligne":          True,
            "derniere_connexion": _timestamp(),
        })
        return profil
    except Exception:
        return None

def deconnecter() -> None:
    if est_connecte():
        uid = st.session_state.utilisateur.get("uid")
        if uid:
            try:
                _db().collection("users").document(uid).update({"en_ligne": False})
            except Exception:
                pass
    st.session_state.clear()

# ── Inscription élève ──────────────────────────────────────────────
def inscrire_eleve(prenom, nom, email, mot_de_passe, telephone,
                   classe, code_professeur) -> tuple[bool, str]:
    initialiser_firebase()

    # Vérifier code professeur OU code établissement
    prof_docs = list(
        _db().collection("users")
        .where("code_invitation", "==", code_professeur.strip().upper())
        .where("role", "==", "professeur")
        .stream()
    )
    etab_doc = None
    prof_id  = None
    etab_id  = None

    if prof_docs:
        prof_id = prof_docs[0].id
        etab_id = prof_docs[0].to_dict().get("etablissement_id")
    else:
        # Chercher dans les établissements
        from models.etablissement import Etablissement
        etab = Etablissement.get_par_code(code_professeur.strip().upper())
        if etab:
            etab_id = etab["id"]
            # Chercher un prof par défaut dans l'établissement
            profs = Etablissement.get_membres(etab_id, "professeur")
            prof_id = profs[0]["id"] if profs else None
        else:
            return False, "Code invalide. Vérifiez le code de votre professeur ou établissement."

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
            "professeur_id":    prof_id,
            "etablissement_id": etab_id,
            "date_creation":    _timestamp(),
            "en_ligne":         False,
            "difficultes":      {},
            "abonnement_actif": True,
        }
        _db().collection("users").document(user.uid).set(profil)
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
        return False, "Code établissement invalide. Contactez l'administration."

    if not etab.get("actif", True):
        return False, "Cet établissement est actuellement suspendu."

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
            "enfants":          [],
            "date_creation":    _timestamp(),
            "en_ligne":         False,
            "abonnement_actif": True,
        }
        _db().collection("users").document(user.uid).set(profil)
        return True, f"Compte créé ! Vous êtes rattaché à **{etab['nom']}**."
    except Exception as e:
        return False, f"Erreur : {str(e)}"

# ── Création compte admin/prof (par super_admin) ───────────────────
def creer_compte(prenom, nom, email, mot_de_passe, telephone, role,
                 matieres=None, etablissement_id=None) -> tuple[bool, str]:
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
            "etablissement_id": etablissement_id,
        }
        if role in ["professeur", "professeur_individuel"]:
            profil["matieres"]        = matieres or []
            profil["code_invitation"] = secrets.token_hex(4).upper()

        _db().collection("users").document(user.uid).set(profil)

        # Créer abonnement essai
        from models.abonnement import Abonnement
        Abonnement.creer_essai(user.uid, role)

        return True, "Compte créé avec succès !"
    except Exception as e:
        return False, f"Erreur : {str(e)}"

# ── Réinitialisation mot de passe ──────────────────────────────────
def envoyer_reset_email(email: str) -> tuple[bool, str]:
    initialiser_firebase()
    api_key = st.secrets["FIREBASE_API_KEY"]
    url = f"https://identitytoolkit.googleapis.com/v1/accounts:sendOobCode?key={api_key}"
    payload = {"requestType": "PASSWORD_RESET", "email": email}
    try:
        reponse = req.post(url, json=payload, timeout=10)
        data    = reponse.json()
        if "error" in data:
            return False, "Email introuvable."
        return True, "Email de réinitialisation envoyé ! Vérifiez votre boîte mail."
    except Exception as e:
        return False, f"Erreur : {str(e)}"

def changer_mot_de_passe(uid: str, nouveau_mdp: str) -> tuple[bool, str]:
    initialiser_firebase()
    try:
        auth.update_user(uid, password=nouveau_mdp)
        return True, "Mot de passe modifié avec succès !"
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
