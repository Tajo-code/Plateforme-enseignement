# app.py — V4 complet
import streamlit as st
from auth.authentification import (connecter_utilisateur, deconnecter,
                                    inscrire_eleve, inscrire_parent,
                                    envoyer_reset_email, changer_mot_de_passe,
                                    est_connecte)
from utils.securite import role_actuel
from utils.banniere import afficher_banniere_abonnement
from models.journal import Journal
import time

st.set_page_config(
    page_title="Plateforme Éducative",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #1a1a2e; }
    [data-testid="stSidebar"] * { color: #e0e0e0 !important; }
    .stButton > button[kind="primary"] {
        background-color: #1a1a2e; color: white;
        border-radius: 8px; width: 100%;
    }
    div[data-testid="metric-container"] {
        background: #f8f9fa; border-radius: 10px;
        padding: 1rem; border: 1px solid #e0e0e0;
    }
</style>
""", unsafe_allow_html=True)

# ── Session state ──────────────────────────────────────────────────
for key in ["utilisateur","page_auth","cours_actif","cours_eleve",
            "session_visio_active","forfait_choisi","page_paiement",
            "reunion_prof"]:
    if key not in st.session_state:
        st.session_state[key] = None if key == "utilisateur" else (
            "connexion" if key == "page_auth" else False if key == "page_paiement" else None
        )


# ── Sidebar ────────────────────────────────────────────────────────
def afficher_sidebar():
    with st.sidebar:
        st.markdown("## 🎓 Plateforme\nÉducative")
        st.divider()

        if est_connecte():
            u = st.session_state.utilisateur
            icones = {
                "super_admin":          "👑",
                "admin_etablissement":  "🏫",
                "admin":                "🛡️",
                "professeur":           "👨‍🏫",
                "eleve":                "🎓",
                "parent":               "👨‍👩‍👧",
            }
            icone = icones.get(u.get("role",""), "👤")
            st.markdown(f"**{icone} {u.get('prenom','')} {u.get('nom','')}**")
            st.caption(f"Rôle : {u.get('role','—')}")
            st.divider()

            if u.get("role") in ["professeur","admin_etablissement"]:
                if st.button("💳 Abonnement & Paiement", use_container_width=True):
                    st.session_state.page_paiement = True
                    st.rerun()

            with st.expander("🔑 Changer mon mot de passe"):
                nouveau   = st.text_input("Nouveau", type="password", key="new_mdp")
                confirmer = st.text_input("Confirmer", type="password", key="conf_mdp")
                if st.button("Changer", key="btn_mdp"):
                    if not nouveau or not confirmer:
                        st.warning("Remplissez les deux champs.")
                    elif nouveau != confirmer:
                        st.error("Mots de passe différents.")
                    elif len(nouveau) < 6:
                        st.error("Minimum 6 caractères.")
                    else:
                        ok, msg = changer_mot_de_passe(u["uid"], nouveau)
                        st.success(msg) if ok else st.error(msg)

            st.divider()
            if st.button("🚪 Se déconnecter", use_container_width=True):
                deconnecter()
                st.rerun()
        else:
            st.caption("Connectez-vous pour accéder à la plateforme.")

    # Rafraichissement automatiquement toutes les 30 secondes
    if est_connecte():
        if "last_refresh" not in st.session_state:
            st.session_state.last_refresh = time.time()
        if time.time() - st.session_state.last_refresh > 30:
            st.session_state.last_refresh = time.time()
            st.rerun()



# ── Page connexion ─────────────────────────────────────────────────
def page_connexion():
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown("## 🎓 Bienvenue sur la plateforme éducative")
        st.divider()
        email = st.text_input("📧 Email", placeholder="votre@email.com")
        mdp   = st.text_input("🔒 Mot de passe", type="password")

        if st.button("Se connecter", type="primary", use_container_width=True):
            if not email or not mdp:
                st.warning("⚠️ Remplissez tous les champs.")
            else:
                with st.spinner("Connexion..."):
                    profil = connecter_utilisateur(email, mdp)
                if profil:
                    st.session_state.utilisateur = profil
                    st.rerun()
                else:
                    st.error("❌ Email ou mot de passe incorrect.")

        st.divider()
        col1, col2, col3 = st.columns(3)
        with col1:
            if st.button("🎓 Compte élève", use_container_width=True):
                st.session_state.page_auth = "inscription_eleve"
                st.rerun()
        with col2:
            if st.button("👨‍👩‍👧 Compte parent", use_container_width=True):
                st.session_state.page_auth = "inscription_parent"
                st.rerun()
        with col3:
            if st.button("🔑 Mot de passe oublié", use_container_width=True):
                st.session_state.page_auth = "reset"
                st.rerun()


# ── Inscription élève ──────────────────────────────────────────────
def page_inscription_eleve():
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown("## 🎓 Créer un compte élève")
        st.caption("Vous avez besoin du code de votre professeur ou établissement.")
        st.divider()

        CLASSES = ["6e","5e","4e","1ère","Tle"]
        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom")
            email  = st.text_input("Email")
            classe = st.selectbox("Classe", CLASSES)
        with col2:
            nom       = st.text_input("Nom")
            telephone = st.text_input("Téléphone", placeholder="+237600000000")
            code      = st.text_input("🔑 Code (professeur ou établissement)")

        mdp       = st.text_input("Mot de passe", type="password")
        confirmer = st.text_input("Confirmer", type="password")

        if st.button("✅ Créer mon compte", type="primary", use_container_width=True):
            if not all([prenom, nom, email, mdp, code]):
                st.warning("⚠️ Remplissez tous les champs.")
            elif mdp != confirmer:
                st.error("❌ Mots de passe différents.")
            elif len(mdp) < 6:
                st.error("❌ Minimum 6 caractères.")
            else:
                with st.spinner("Création..."):
                    ok, msg = inscrire_eleve(prenom, nom, email, mdp,
                                             telephone, classe, code)
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state.page_auth = "connexion"
                    st.rerun()
                else:
                    st.error(msg)

        if st.button("← Retour", use_container_width=True):
            st.session_state.page_auth = "connexion"
            st.rerun()


# ── Inscription parent ─────────────────────────────────────────────
def page_inscription_parent():
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown("## 👨‍👩‍👧 Créer un compte parent")
        st.caption("Vous avez besoin du code de l'établissement de votre enfant.")
        st.divider()

        col1, col2 = st.columns(2)
        with col1:
            prenom = st.text_input("Prénom")
            email  = st.text_input("Email")
        with col2:
            nom       = st.text_input("Nom")
            telephone = st.text_input("Téléphone", placeholder="+237600000000")

        code      = st.text_input("🔑 Code de l'établissement")
        mdp       = st.text_input("Mot de passe", type="password")
        confirmer = st.text_input("Confirmer", type="password")

        if st.button("✅ Créer mon compte", type="primary", use_container_width=True):
            if not all([prenom, nom, email, mdp, code]):
                st.warning("⚠️ Remplissez tous les champs.")
            elif mdp != confirmer:
                st.error("❌ Mots de passe différents.")
            elif len(mdp) < 6:
                st.error("❌ Minimum 6 caractères.")
            else:
                with st.spinner("Création..."):
                    ok, msg = inscrire_parent(prenom, nom, email, mdp,
                                              telephone, code)
                if ok:
                    st.success(f"✅ {msg}")
                    st.session_state.page_auth = "connexion"
                    st.rerun()
                else:
                    st.error(msg)

        if st.button("← Retour", use_container_width=True):
            st.session_state.page_auth = "connexion"
            st.rerun()


# ── Reset mot de passe ─────────────────────────────────────────────
def page_reset():
    _, col_c, _ = st.columns([1, 2, 1])
    with col_c:
        st.markdown("## 🔑 Mot de passe oublié")
        email = st.text_input("📧 Votre email")
        if st.button("📧 Envoyer le lien", type="primary", use_container_width=True):
            if not email:
                st.warning("⚠️ Entrez votre email.")
            else:
                ok, msg = envoyer_reset_email(email)
                st.success(msg) if ok else st.error(msg)
        if st.button("← Retour", use_container_width=True):
            st.session_state.page_auth = "connexion"
            st.rerun()


# ── Routeur principal ──────────────────────────────────────────────
def main():
    afficher_sidebar()

    if not est_connecte():
        page = st.session_state.page_auth
        if page == "inscription_eleve":
            page_inscription_eleve()
        elif page == "inscription_parent":
            page_inscription_parent()
        elif page == "reset":
            page_reset()
        else:
            page_connexion()
        return

    utilisateur = st.session_state.utilisateur

    # Bannière abonnement
    abonnement_valide = afficher_banniere_abonnement(utilisateur)

    # Page paiement
    if st.session_state.get("page_paiement"):
        from vues.vue_paiement import afficher_vue_paiement
        if st.button("← Retour"):
            st.session_state.page_paiement = False
            st.rerun()
        afficher_vue_paiement()
        return

    # Compte suspendu
    if not abonnement_valide:
        st.warning("⚠️ Votre compte est suspendu. Renouvelez votre abonnement.")
        from vues.vue_paiement import afficher_vue_paiement
        afficher_vue_paiement()
        return

    role = role_actuel()

    if role == "super_admin":
        from vues.vue_superadmin import afficher_vue_superadmin
        afficher_vue_superadmin()
    elif role == "admin_etablissement":
        from vues.vue_admin_etablissement import afficher_vue_admin_etablissement
        afficher_vue_admin_etablissement()
    elif role == "admin":
        from vues.vue_admin import afficher_vue_admin
        afficher_vue_admin()
    elif role == "professeur":
        from vues.vue_professeur import afficher_vue_professeur
        afficher_vue_professeur()
    elif role == "eleve":
        from vues.vue_eleve import afficher_vue_eleve
        afficher_vue_eleve()
    elif role == "parent":
        from vues.vue_parent import afficher_vue_parent
        afficher_vue_parent()
    else:
        st.error("Rôle inconnu.")
        if st.button("Se déconnecter"):
            deconnecter()
            st.rerun()


if __name__ == "__main__":
    main()
