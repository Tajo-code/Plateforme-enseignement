# vues/vue_admin.py — Espace administrateur (lecture seule)
import streamlit as st
from models.utilisateur import Administrateur
from utils.securite import exiger_role


def afficher_vue_admin():
    exiger_role(["admin", "super_admin"])
    utilisateur = st.session_state.utilisateur

    st.title(f"🛡️ Espace Administrateur — {utilisateur['prenom']} {utilisateur['nom']}")
    st.info("👁️ Accès en **lecture seule**. Vous pouvez consulter mais pas modifier.")

    onglet1, onglet2 = st.tabs(["👨‍🏫 Professeurs", "📋 Travaux"])

    with onglet1:
        _onglet_professeurs()
    with onglet2:
        _onglet_travaux()


def _onglet_professeurs():
    st.subheader("👨‍🏫 Liste des professeurs")
    professeurs = Administrateur.get_tous_professeurs()

    if not professeurs:
        st.info("Aucun professeur enregistré.")
        return

    st.markdown(f"**{len(professeurs)} professeur(s)**")

    for p in professeurs:
        en_ligne = "🟢 En ligne" if p.get("en_ligne") else "⚫ Hors ligne"
        with st.expander(f"👤 {p['nom']} {p['prenom']} — {', '.join(p.get('matieres', []))} | {en_ligne}"):
            col1, col2 = st.columns(2)
            col1.markdown(f"**Email :** {p.get('email','—')}")
            col2.markdown(f"**Tél :** {p.get('telephone','—')}")
            col1.markdown(f"**Inscrit le :** {p.get('date_creation','—')[:10]}")

            travaux = Administrateur.get_travaux_professeur(p["id"])
            soumis  = len([t for t in travaux if t.get("statut") == "soumis"])
            corriges= len([t for t in travaux if t.get("statut") == "corrigé"])
            publies = len([t for t in travaux if t.get("statut") == "publié"])

            c1, c2, c3 = st.columns(3)
            c1.metric("En attente", soumis)
            c2.metric("Corrigés",   corriges)
            c3.metric("Publiés",    publies)


def _onglet_travaux():
    st.subheader("📋 Consultation des travaux")
    professeurs = Administrateur.get_tous_professeurs()

    if not professeurs:
        st.info("Aucun professeur enregistré.")
        return

    noms_profs = {f"{p['nom']} {p['prenom']}": p["id"] for p in professeurs}
    choix_prof = st.selectbox("Choisir un professeur", list(noms_profs.keys()))
    prof_id    = noms_profs[choix_prof]

    travaux = Administrateur.get_travaux_professeur(prof_id)
    filtre  = st.selectbox("Statut", ["Tous", "soumis", "corrigé", "publié"])
    if filtre != "Tous":
        travaux = [t for t in travaux if t.get("statut") == filtre]

    if not travaux:
        st.info("Aucun travail trouvé.")
        return

    st.markdown(f"**{len(travaux)} travail(aux)**")

    for t in sorted(travaux, key=lambda x: x.get("date_soumis",""), reverse=True):
        statut = t.get("statut","soumis")
        icone  = {"soumis":"🕐","corrigé":"🔒","publié":"✅"}.get(statut,"🕐")
        with st.expander(f"{icone} {t['eleve_nom']} | {t.get('classe','?')} | {t['matiere']}"):
            st.markdown(f"**Statut :** {statut}")
            st.markdown(f"**Date :** {t.get('date_soumis','')[:10]}")
            if t.get("note") is not None:
                st.markdown(f"**Note :** {t['note']}/20")
            if t.get("remarques"):
                st.markdown(f"**Remarques :** {t['remarques']}")
