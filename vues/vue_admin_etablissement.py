# vues/vue_admin_etablissement.py — Espace admin établissement
import streamlit as st
from config import get_db
from models.message import Message
from models.etablissement import Etablissement
from utils.securite import exiger_role
from utils.jitsi import afficher_visio, creer_session_visio, get_sessions_actives
import secrets


def afficher_vue_admin_etablissement():
    exiger_role(["admin_etablissement", "super_admin"])
    utilisateur = st.session_state.utilisateur
    etab_id = utilisateur.get("etablissement_id")

    # Charger l'établissement
    etab = Etablissement.get(etab_id) if etab_id else None
    nom_etab = etab.get("nom", "Établissement") if etab else "Établissement"

    nb_non_lus = Message.nb_non_lus(utilisateur["uid"], etab_id)

    st.title(f"🏫 {nom_etab}")
    st.caption(f"Administrateur : {utilisateur['prenom']} {utilisateur['nom']}")

    # Statistiques rapides
    membres = Etablissement.get_membres(etab_id) if etab_id else []
    profs   = [m for m in membres if m.get("role") == "professeur"]
    eleves  = [m for m in membres if m.get("role") == "eleve"]
    parents = [m for m in membres if m.get("role") == "parent"]

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👨‍🏫 Professeurs", len(profs))
    col2.metric("🎓 Élèves",       len(eleves))
    col3.metric("👨‍👩‍👧 Parents",     len(parents))
    col4.metric("💬 Non lus",      nb_non_lus)

    if etab:
        st.info(f"🔑 Code d'invitation de l'établissement : **{etab.get('code_invitation','—')}** — Partagez ce code aux professeurs, élèves et parents.")

    st.divider()

    onglet1, onglet2, onglet3, onglet4, onglet5 = st.tabs([
        "👥 Membres",
        f"💬 Messages ({nb_non_lus})",
        "📹 Visioconférence",
        "📊 Rapports",
        "⚙️ Paramètres",
    ])

    with onglet1:
        _onglet_membres(utilisateur, etab_id, profs, eleves, parents)
    with onglet2:
        _onglet_messages(utilisateur, etab_id)
    with onglet3:
        _onglet_visio(utilisateur, etab_id)
    with onglet4:
        _onglet_rapports(utilisateur, etab_id)
    with onglet5:
        _onglet_parametres(utilisateur, etab_id, etab)


# ── ONGLET 1 : Membres ────────────────────────────────────────────
def _onglet_membres(utilisateur, etab_id, profs, eleves, parents):
    st.subheader("👥 Membres de l'établissement")

    tab_p, tab_e, tab_par = st.tabs(["👨‍🏫 Professeurs", "🎓 Élèves", "👨‍👩‍👧 Parents"])

    with tab_p:
        if not profs:
            st.info("Aucun professeur inscrit.")
        for p in profs:
            en_ligne = "🟢" if p.get("en_ligne") else "⚫"
            with st.expander(f"{en_ligne} {p['nom']} {p['prenom']} — {', '.join(p.get('matieres',[]))}"):
                st.markdown(f"**Email :** {p.get('email','—')}")
                st.markdown(f"**Tél :** {p.get('telephone','—')}")

    with tab_e:
        classes = ["Toutes"] + ["6e", "5e", "4e", "1ère", "Tle"]
        filtre  = st.selectbox("Classe", classes, key="filtre_eleves_admin")
        eleves_filtres = eleves if filtre == "Toutes" else [e for e in eleves if e.get("classe") == filtre]

        st.markdown(f"**{len(eleves_filtres)} élève(s)**")
        for e in eleves_filtres:
            with st.expander(f"🎓 {e['nom']} {e['prenom']} — {e.get('classe','?')}"):
                st.markdown(f"**Email :** {e.get('email','—')}")

    with tab_par:
        if not parents:
            st.info("Aucun parent inscrit.")
        for p in parents:
            with st.expander(f"👨‍👩‍👧 {p['nom']} {p['prenom']}"):
                st.markdown(f"**Email :** {p.get('email','—')}")
                st.markdown(f"**Tél :** {p.get('telephone','—')}")
                enfants = p.get("enfants", [])
                st.markdown(f"**Enfants :** {len(enfants)} enregistré(s)")


# ── ONGLET 2 : Messages ───────────────────────────────────────────
def _onglet_messages(utilisateur: dict, etab_id: str):
    st.subheader("💬 Messagerie")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📥 Messages reçus**")
        messages = Message.get_recus(utilisateur["uid"], etab_id)

        if not messages:
            st.info("Aucun message.")
        for m in messages:
            lu = "✅" if m.get("lu") else "🆕"
            with st.expander(f"{lu} {m.get('sujet','?')} — {m.get('expediteur_nom','?')} | {m.get('date_envoi','')[:10]}"):
                st.markdown(f"**Message :** {m.get('contenu','')}")
                if not m.get("lu"):
                    Message.marquer_lu(m["id"])

    with col2:
        st.markdown("**📤 Envoyer un message**")
        type_envoi = st.radio("Type", ["Message individuel", "Message collectif (tous les parents)"], horizontal=True)

        if type_envoi == "Message individuel":
            membres = Etablissement.get_membres(etab_id)
            noms    = {f"{m['nom']} {m['prenom']} ({m.get('role','?')})": m["id"] for m in membres if m["id"] != utilisateur["uid"]}
            dest_nom = st.selectbox("Destinataire", list(noms.keys()))
            dest_id  = noms.get(dest_nom)
            est_collectif = False
        else:
            dest_id = "tous"
            est_collectif = True
            st.info("📢 Ce message sera envoyé à tous les parents de l'établissement.")

        sujet   = st.text_input("Sujet")
        contenu = st.text_area("Message", height=120)

        if st.button("📤 Envoyer", type="primary", key="btn_envoyer_admin"):
            if not sujet or not contenu:
                st.warning("⚠️ Remplissez sujet et message.")
            else:
                msg = Message(
                    expediteur_id=utilisateur["uid"],
                    expediteur_nom=f"Administration — {utilisateur['prenom']} {utilisateur['nom']}",
                    destinataire_id=dest_id,
                    sujet=sujet,
                    contenu=contenu,
                    etablissement_id=etab_id,
                    est_collectif=est_collectif,
                )
                msg.envoyer()
                st.success("✅ Message envoyé !")


# ── ONGLET 3 : Visioconférence ────────────────────────────────────
def _onglet_visio(utilisateur: dict, etab_id: str):
    st.subheader("📹 Visioconférence — Réunions parents")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**➕ Lancer une nouvelle réunion**")
        titre = st.text_input("Titre de la réunion", placeholder="Ex: Réunion de rentrée")

        if st.button("🚀 Lancer la réunion", type="primary"):
            if not titre:
                st.warning("⚠️ Donnez un titre à la réunion.")
            else:
                session = creer_session_visio(
                    organisateur_id=utilisateur["uid"],
                    titre=titre,
                    type_session="reunion_parents",
                    etablissement_id=etab_id,
                )
                # Notifier les parents par message
                msg = Message(
                    expediteur_id=utilisateur["uid"],
                    expediteur_nom=f"Administration",
                    destinataire_id="tous",
                    sujet=f"📹 Réunion en cours : {titre}",
                    contenu=f"Une réunion a été lancée. Rejoignez-la ici : {session['lien']}",
                    etablissement_id=etab_id,
                    est_collectif=True,
                )
                msg.envoyer()
                st.success(f"✅ Réunion lancée ! Les parents ont été notifiés.")
                st.session_state["session_visio_active"] = session

    with col2:
        st.markdown("**📋 Réunions en cours**")
        sessions = get_sessions_actives(etablissement_id=etab_id)
        reunions = [s for s in sessions if s.get("type_session") == "reunion_parents"]

        if not reunions:
            st.info("Aucune réunion en cours.")
        for r in reunions:
            st.markdown(f"- **{r.get('titre','?')}** — [Lien]({r.get('lien','')})")

    # Afficher la visio si active
    if st.session_state.get("session_visio_active"):
        session = st.session_state["session_visio_active"]
        st.divider()
        st.markdown(f"### 📹 {session['titre']}")
        nom_utilisateur = f"Admin — {utilisateur['prenom']} {utilisateur['nom']}"
        afficher_visio(
            nom_salle=session["nom_salle"],
            nom_utilisateur=nom_utilisateur,
            est_moderateur=True
        )


# ── ONGLET 4 : Rapports ───────────────────────────────────────────
def _onglet_rapports(utilisateur: dict, etab_id: str):
    st.subheader("📊 Rapports de l'établissement")

    membres = Etablissement.get_membres(etab_id)
    eleves  = [m for m in membres if m.get("role") == "eleve"]

    st.markdown(f"**Total membres :** {len(membres)}")

    # Répartition par classe
    st.markdown("**Répartition par classe :**")
    classes = {}
    for e in eleves:
        c = e.get("classe", "—")
        classes[c] = classes.get(c, 0) + 1
    for classe, nb in sorted(classes.items()):
        st.markdown(f"- **{classe}** : {nb} élève(s)")

    st.divider()

    # Moyennes par classe
    st.markdown("**Moyennes par classe :**")
    for classe in sorted(classes.keys()):
        eleves_classe = [e for e in eleves if e.get("classe") == classe]
        toutes_notes = []
        for e in eleves_classe:
            travaux = get_db().collection("travaux")\
                .where("eleve_id", "==", e["id"])\
                .where("statut", "==", "publié")\
                .stream()
            notes = [t.to_dict().get("note") for t in travaux if t.to_dict().get("note") is not None]
            toutes_notes.extend(notes)

        if toutes_notes:
            moy = sum(toutes_notes) / len(toutes_notes)
            couleur = "green" if moy >= 10 else "red"
            st.markdown(f"- **{classe}** : :{couleur}[{moy:.1f}/20]")


# ── ONGLET 5 : Paramètres ─────────────────────────────────────────
def _onglet_parametres(utilisateur: dict, etab_id: str, etab: dict):
    st.subheader("⚙️ Paramètres de l'établissement")

    if etab:
        st.markdown(f"**Nom :** {etab.get('nom','—')}")
        st.markdown(f"**Ville :** {etab.get('ville','—')}")
        st.markdown(f"**Taille :** {etab.get('taille','—')}")
        st.markdown(f"**ID établissement :** `{etab.get('id','—')}`")
        st.markdown(f"**Code invitation :** `{etab.get('code_invitation','—')}`")
        st.markdown(f"**Statut :** {'✅ Actif' if etab.get('actif') else '⛔ Suspendu'}")
