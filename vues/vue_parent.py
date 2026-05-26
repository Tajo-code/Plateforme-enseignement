# vues/vue_parent.py — Espace parent
import streamlit as st
from config import get_db
from models.message import Message
from models.utilisateur import Eleve
from utils.securite import exiger_role
from utils.jitsi import afficher_visio, get_sessions_actives


def afficher_vue_parent():
    exiger_role(["parent"])
    utilisateur = st.session_state.utilisateur
    etab_id = utilisateur.get("etablissement_id")

    # Nombre de messages non lus
    nb_non_lus = Message.nb_non_lus(utilisateur["uid"], etab_id)

    st.title(f"👨‍👩‍👧 Bonjour, {utilisateur['prenom']} !")
    if nb_non_lus > 0:
        st.info(f"📬 Vous avez **{nb_non_lus}** message(s) non lu(s).")

    onglet1, onglet2, onglet3, onglet4 = st.tabs([
        "👶 Mes enfants",
        f"💬 Messages ({nb_non_lus})",
        "📹 Réunions",
        "⚙️ Mon compte",
    ])

    with onglet1:
        _onglet_enfants(utilisateur)
    with onglet2:
        _onglet_messages(utilisateur, etab_id)
    with onglet3:
        _onglet_reunions(utilisateur, etab_id)
    with onglet4:
        _onglet_compte(utilisateur)


# ── ONGLET 1 : Mes enfants ────────────────────────────────────────
def _onglet_enfants(utilisateur: dict):
    st.subheader("👶 Résultats de mes enfants")

    enfants = utilisateur.get("enfants", [])  # liste d'IDs d'élèves

    if not enfants:
        st.info("Aucun enfant enregistré. Ajoutez les informations de vos enfants dans votre compte.")
        return

    for eleve_id in enfants:
        eleve_doc = get_db().collection("users").document(eleve_id).get()
        if not eleve_doc.exists:
            continue
        eleve = eleve_doc.to_dict()

        with st.expander(f"🎓 {eleve.get('nom')} {eleve.get('prenom')} — {eleve.get('classe','?')}"):
            # Travaux publiés
            travaux = Eleve.get_travaux_publies(eleve_id)

            if not travaux:
                st.info("Aucun résultat disponible pour le moment.")
                continue

            notes = [t["note"] for t in travaux if t.get("note") is not None]
            if notes:
                moy = sum(notes) / len(notes)
                couleur = "green" if moy >= 10 else "red"
                st.markdown(f"**Moyenne générale : :{couleur}[{moy:.1f}/20]**")

            st.divider()

            for t in sorted(travaux, key=lambda x: x.get("date_soumis",""), reverse=True):
                note = t.get("note")
                if note is not None:
                    couleur = "green" if note >= 10 else "red"
                    with st.expander(f"📝 {t['matiere']} — {t.get('discipline','')} | Note : :{couleur}[{note}/20]"):
                        st.markdown(f"**Date :** {t.get('date_soumis','')[:10]}")
                        if t.get("remarques"):
                            st.markdown(f"**Remarques du professeur :** {t['remarques']}")


# ── ONGLET 2 : Messages ───────────────────────────────────────────
def _onglet_messages(utilisateur: dict, etab_id: str):
    st.subheader("💬 Messages avec l'administration")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📥 Messages reçus**")
        messages = Message.get_recus(utilisateur["uid"], etab_id)

        if not messages:
            st.info("Aucun message reçu.")
        else:
            for m in messages:
                lu = "✅" if m.get("lu") else "🆕"
                with st.expander(f"{lu} {m.get('sujet','Sans sujet')} — {m.get('date_envoi','')[:10]}"):
                    st.markdown(f"**De :** {m.get('expediteur_nom','?')}")
                    st.markdown(f"**Message :** {m.get('contenu','')}")
                    if not m.get("lu"):
                        Message.marquer_lu(m["id"])

    with col2:
        st.markdown("**📤 Envoyer un message à l'administration**")
        sujet   = st.text_input("Sujet", placeholder="Ex: Absence de mon enfant")
        contenu = st.text_area("Message", height=150)

        if st.button("📤 Envoyer", type="primary"):
            if not sujet or not contenu:
                st.warning("⚠️ Remplissez le sujet et le message.")
            else:
                # Trouver l'admin de l'établissement
                if etab_id:
                    admins = get_db().collection("users")\
                        .where("etablissement_id", "==", etab_id)\
                        .where("role", "==", "admin_etablissement")\
                        .stream()
                    admins_list = list(admins)
                    if admins_list:
                        admin_id = admins_list[0].id
                        msg = Message(
                            expediteur_id=utilisateur["uid"],
                            expediteur_nom=f"{utilisateur['nom']} {utilisateur['prenom']}",
                            destinataire_id=admin_id,
                            sujet=sujet,
                            contenu=contenu,
                            etablissement_id=etab_id,
                        )
                        msg.envoyer()
                        st.success("✅ Message envoyé à l'administration !")
                    else:
                        st.error("Impossible de trouver l'administrateur.")


# ── ONGLET 3 : Réunions vidéo ─────────────────────────────────────
def _onglet_reunions(utilisateur: dict, etab_id: str):
    st.subheader("📹 Réunions parents-administration")

    sessions = get_sessions_actives(etablissement_id=etab_id)
    reunions = [s for s in sessions if s.get("type_session") == "reunion_parents"]

    if not reunions:
        st.info("Aucune réunion en cours. L'administration vous convoquera via la messagerie.")
        return

    for reunion in reunions:
        with st.expander(f"📹 {reunion.get('titre','Réunion')} — En cours"):
            st.markdown(f"**Organisée par :** Administration")
            st.markdown(f"**Lien direct :** [Rejoindre]({reunion.get('lien','')})")

            if st.button("📹 Rejoindre la réunion", key=f"join_{reunion['id']}", type="primary"):
                nom_utilisateur = f"{utilisateur['prenom']} {utilisateur['nom']} (Parent)"
                afficher_visio(
                    nom_salle=reunion["nom_salle"],
                    nom_utilisateur=nom_utilisateur,
                    est_moderateur=False
                )


# ── ONGLET 4 : Mon compte ─────────────────────────────────────────
def _onglet_compte(utilisateur: dict):
    st.subheader("⚙️ Mon compte")

    st.markdown(f"**Nom :** {utilisateur.get('nom')} {utilisateur.get('prenom')}")
    st.markdown(f"**Email :** {utilisateur.get('email')}")
    st.markdown(f"**Téléphone :** {utilisateur.get('telephone','—')}")

    st.divider()
    st.markdown("**👶 Mes enfants enregistrés :**")

    enfants = utilisateur.get("enfants", [])
    for eleve_id in enfants:
        doc = get_db().collection("users").document(eleve_id).get()
        if doc.exists:
            e = doc.to_dict()
            st.markdown(f"- {e.get('nom')} {e.get('prenom')} — {e.get('classe','?')}")

    st.divider()
    st.markdown("**➕ Ajouter un enfant**")
    st.caption("Entrez l'email avec lequel votre enfant est inscrit sur la plateforme.")
    email_enfant = st.text_input("Email de l'enfant")

    if st.button("Ajouter", type="primary"):
        if not email_enfant:
            st.warning("⚠️ Entrez l'email de votre enfant.")
        else:
            docs = list(
                get_db().collection("users")
                .where("email", "==", email_enfant.strip().lower())
                .where("role", "==", "eleve")
                .stream()
            )
            if not docs:
                st.error("❌ Aucun élève trouvé avec cet email.")
            else:
                eleve_id = docs[0].id
                if eleve_id not in enfants:
                    enfants.append(eleve_id)
                    get_db().collection("users").document(utilisateur["uid"]).update({
                        "enfants": enfants
                    })
                    st.success("✅ Enfant ajouté avec succès !")
                    st.rerun()
                else:
                    st.info("Cet enfant est déjà dans votre liste.")
