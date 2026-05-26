# vues/vue_professeur.py — V3 avec visio + messages + établissement
import streamlit as st
import datetime
import uuid
from config import get_db, get_bucket
from models.travail import Travail, ExerciceQCM
from models.utilisateur import Professeur
from models.message import Message
from utils.securite import exiger_role, verifier_acces_professeur, bloquer_acces_non_autorise
from utils.jitsi import afficher_visio, creer_session_visio, get_sessions_actives


def afficher_vue_professeur():
    exiger_role(["professeur", "professeur_individuel", "admin", "super_admin"])
    utilisateur = st.session_state.utilisateur
    prof_id     = utilisateur["uid"]
    etab_id     = utilisateur.get("etablissement_id")

    if not verifier_acces_professeur(prof_id):
        bloquer_acces_non_autorise()

    # Statistiques
    nb_eleves  = Professeur.get_nb_eleves(prof_id)
    travaux    = Professeur.get_travaux_a_corriger(prof_id)
    a_corriger = len([t for t in travaux if t.get("statut") == "soumis"])
    nb_msg     = Message.nb_non_lus(prof_id, etab_id)

    st.title(f"👨‍🏫 Bonjour, {utilisateur['prenom']} !")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Élèves",      nb_eleves)
    col2.metric("📥 À corriger",   a_corriger)
    col3.metric("💬 Messages",     nb_msg)
    col4.metric("✅ Publiés",      len([t for t in travaux if t.get("statut") == "publié"]))

    code = utilisateur.get("code_invitation", "—")
    st.info(f"🔑 Code d'invitation : **{code}**")

    st.divider()

    onglets = ["📂 Exercices", "📥 Réception", "✏️ Corriger",
               "✅ Publier", "📹 Cours en ligne", f"💬 Messages ({nb_msg})", "👥 Élèves"]

    onglet1, onglet2, onglet3, onglet4, onglet5, onglet6, onglet7 = st.tabs(onglets)

    with onglet1:
        _onglet_exercices(utilisateur)
    with onglet2:
        _onglet_reception(utilisateur)
    with onglet3:
        _onglet_correction(utilisateur)
    with onglet4:
        _onglet_publication(utilisateur)
    with onglet5:
        _onglet_visio(utilisateur, etab_id)
    with onglet6:
        _onglet_messages(utilisateur, etab_id)
    with onglet7:
        _onglet_eleves(utilisateur)


# ── ONGLET 1 : Exercices ──────────────────────────────────────────
def _onglet_exercices(utilisateur: dict):
    st.subheader("📂 Publier un exercice")
    prof_id  = utilisateur["uid"]
    matieres = utilisateur.get("matieres", [])
    classes  = ["6e", "5e", "4e", "1ère", "Tle"]

    col1, col2 = st.columns(2)
    with col1:
        classe = st.selectbox("🎓 Classe", classes)
    with col2:
        matiere = st.selectbox("📚 Matière", matieres) if matieres else st.text_input("📚 Matière")

    titre      = st.text_input("📌 Titre", placeholder="Ex: Analyse de texte")
    consignes  = st.text_area("📋 Consignes et explications", height=150,
                               placeholder="Expliquez ce que vous attendez, les critères d'évaluation...")
    format_ex  = st.selectbox("📝 Format", ["Devoir individuel", "Travail de groupe", "QCM", "Rédaction", "Exposé"])
    date_lim   = st.date_input("📅 Date limite", min_value=datetime.date.today())

    contenu = st.text_area("✏️ Rédigez l'exercice", height=200,
                            placeholder="Écrivez votre exercice ici...")

    if st.button("🚀 Publier", type="primary"):
        if not titre or not consignes:
            st.warning("⚠️ Le titre et les consignes sont obligatoires.")
            return
        exercice = {
            "id":            str(uuid.uuid4()),
            "prof_id":       prof_id,
            "classe":        classe,
            "matiere":       matiere,
            "titre":         titre,
            "consignes":     consignes,
            "format":        format_ex,
            "date_limite":   str(date_lim),
            "contenu":       contenu,
            "fichier_url":   "",
            "date_creation": datetime.datetime.now().isoformat(),
        }
        get_db().collection("exercices_publies").add(exercice)
        st.success(f"✅ Exercice publié pour les élèves de {classe} !")
        st.balloons()


# ── ONGLET 2 : Boîte de réception ────────────────────────────────
def _onglet_reception(utilisateur: dict):
    st.subheader("📥 Boîte de réception")
    prof_id = utilisateur["uid"]
    classes = ["Toutes"] + ["6e", "5e", "4e", "1ère", "Tle"]

    col1, col2 = st.columns(2)
    with col1:
        filtre_classe = st.selectbox("Classe", classes, key="rec_classe")
    with col2:
        filtre_statut = st.selectbox("Statut", ["Tous", "soumis", "corrigé", "publié"], key="rec_statut")

    classe_param = None if filtre_classe == "Toutes" else filtre_classe
    travaux = Professeur.get_travaux_a_corriger(prof_id, classe=classe_param)
    if filtre_statut != "Tous":
        travaux = [t for t in travaux if t.get("statut") == filtre_statut]
    travaux = sorted(travaux, key=lambda t: t.get("date_soumis",""), reverse=True)

    if not travaux:
        st.info("📭 Aucun travail reçu.")
        return

    st.markdown(f"**{len(travaux)} travail(aux)**")
    for t in travaux:
        statut = t.get("statut","soumis")
        icone  = {"soumis":"🆕","corrigé":"🔒","publié":"✅"}.get(statut,"🕐")
        with st.expander(f"{icone} {t['eleve_nom']} | {t.get('classe','?')} | {t['matiere']} | {t.get('date_soumis','')[:10]}"):
            if t.get("contenu_texte"):
                st.text_area("Réponse", value=t["contenu_texte"], height=150, disabled=True, key=f"r_{t['id']}")
            if t.get("fichier_url"):
                st.markdown(f"[📎 Voir fichier]({t['fichier_url']})")


# ── ONGLET 3 : Corriger ───────────────────────────────────────────
def _onglet_correction(utilisateur: dict):
    st.subheader("✏️ Corriger les travaux")
    prof_id = utilisateur["uid"]
    travaux = Professeur.get_travaux_a_corriger(prof_id, statut="soumis")

    if not travaux:
        st.info("✅ Aucun travail à corriger.")
        return

    for t in sorted(travaux, key=lambda x: x.get("date_soumis",""), reverse=True):
        with st.expander(f"🆕 {t['eleve_nom']} | {t.get('classe','?')} | {t['matiere']} | {t.get('date_soumis','')[:10]}"):
            st.markdown("**📄 Travail soumis :**")
            if t.get("contenu_texte"):
                # Permettre au prof de modifier la réponse de l'élève
                reponse_modifiee = st.text_area(
                    "Réponse de l'élève (modifiable)",
                    value=t["contenu_texte"],
                    height=200,
                    key=f"rep_{t['id']}",
                    help="Vous pouvez modifier ou annoter directement la réponse de l'élève."
                )
            if t.get("fichier_url"):
                st.markdown(f"[📎 Voir fichier]({t['fichier_url']})")

            st.divider()
            st.markdown("**✏️ Votre correction :**")

            note = st.number_input("Note /20", 0.0, 20.0, 0.0, 0.5, key=f"note_{t['id']}")
            remarques = st.text_area("Remarques détaillées",
                                      placeholder="Commentaires, points forts, points à améliorer...",
                                      height=120, key=f"rem_{t['id']}")

            if st.button("💾 Enregistrer", type="primary", key=f"save_{t['id']}"):
                if not remarques.strip():
                    st.warning("⚠️ Ajoutez des remarques.")
                else:
                    # Sauvegarder la réponse modifiée si changée
                    updates = {
                        "note":        note,
                        "remarques":   remarques,
                        "statut":      "corrigé",
                        "date_corrige": datetime.datetime.now().isoformat(),
                    }
                    if t.get("contenu_texte") and reponse_modifiee != t["contenu_texte"]:
                        updates["contenu_texte_original"] = t["contenu_texte"]
                        updates["contenu_texte_modifie"]  = reponse_modifiee
                    get_db().collection("travaux").document(t["id"]).update(updates)
                    st.success("✅ Correction enregistrée !")
                    st.rerun()


# ── ONGLET 4 : Publier corrections ───────────────────────────────
def _onglet_publication(utilisateur: dict):
    st.subheader("✅ Publier les corrections")
    prof_id = utilisateur["uid"]
    corriges = Professeur.get_travaux_a_corriger(prof_id, statut="corrigé")

    if not corriges:
        st.info("📭 Aucune correction en attente de publication.")
        return

    st.warning(f"⚠️ **{len(corriges)} correction(s)** prête(s).")

    with st.expander("Aperçu"):
        for t in corriges:
            n = t.get("note", "?")
            couleur = "green" if isinstance(n, (int,float)) and n >= 10 else "red"
            st.markdown(f"- **{t['eleve_nom']}** | {t.get('classe','?')} | {t['matiere']} | :{couleur}[{n}/20]")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("🚀 Publier TOUTES", type="primary"):
            nb = Professeur.publier_corrections(prof_id)
            st.success(f"✅ {nb} correction(s) publiée(s) !")
            st.balloons()
            st.rerun()
    with col2:
        st.info("💡 Les élèves ne verront leurs résultats qu'après publication.")


# ── ONGLET 5 : Cours en ligne (Visio) ────────────────────────────
def _onglet_visio(utilisateur: dict, etab_id: str):
    st.subheader("📹 Cours en ligne — Visioconférence")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**🚀 Lancer un cours**")
        titre_cours = st.text_input("Titre du cours", placeholder="Ex: Cours de Français — 6e")

        if st.button("📹 Lancer le cours", type="primary"):
            if not titre_cours:
                st.warning("⚠️ Donnez un titre au cours.")
            else:
                session = creer_session_visio(
                    organisateur_id=utilisateur["uid"],
                    titre=titre_cours,
                    type_session="cours",
                    etablissement_id=etab_id,
                )
                st.success(f"✅ Cours lancé ! Partagez ce lien à vos élèves :")
                st.code(session["lien"])
                st.session_state["cours_actif"] = session

    with col2:
        st.markdown("**📋 Cours en cours**")
        sessions = get_sessions_actives(prof_id=utilisateur["uid"])
        cours    = [s for s in sessions if s.get("type_session") == "cours"]

        if not cours:
            st.info("Aucun cours en cours.")
        for c in cours:
            st.markdown(f"- **{c.get('titre','?')}** — [Lien]({c.get('lien','')})")
            if st.button("Rejoindre", key=f"join_{c['id']}"):
                st.session_state["cours_actif"] = c

    # Afficher la visio
    if st.session_state.get("cours_actif"):
        cours = st.session_state["cours_actif"]
        st.divider()
        st.markdown(f"### 📹 {cours['titre']}")
        nom_utilisateur = f"Prof. {utilisateur['prenom']} {utilisateur['nom']}"
        afficher_visio(
            nom_salle=cours["nom_salle"],
            nom_utilisateur=nom_utilisateur,
            est_moderateur=True,
            hauteur=550
        )


# ── ONGLET 6 : Messages ───────────────────────────────────────────
def _onglet_messages(utilisateur: dict, etab_id: str):
    st.subheader("💬 Messages")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**📥 Reçus**")
        messages = Message.get_recus(utilisateur["uid"], etab_id)
        if not messages:
            st.info("Aucun message.")
        for m in messages:
            lu = "✅" if m.get("lu") else "🆕"
            with st.expander(f"{lu} {m.get('sujet','?')} | {m.get('expediteur_nom','?')}"):
                st.markdown(m.get("contenu",""))
                if not m.get("lu"):
                    Message.marquer_lu(m["id"])

    with col2:
        st.markdown("**📤 Envoyer à l'administration**")
        sujet   = st.text_input("Sujet", key="msg_sujet_prof")
        contenu = st.text_area("Message", height=100, key="msg_contenu_prof")

        if st.button("📤 Envoyer", type="primary", key="btn_msg_prof"):
            if not sujet or not contenu:
                st.warning("⚠️ Remplissez sujet et message.")
            elif etab_id:
                admins = list(get_db().collection("users")
                              .where("etablissement_id", "==", etab_id)
                              .where("role", "==", "admin_etablissement")
                              .stream())
                if admins:
                    msg = Message(
                        expediteur_id=utilisateur["uid"],
                        expediteur_nom=f"Prof. {utilisateur['prenom']} {utilisateur['nom']}",
                        destinataire_id=admins[0].id,
                        sujet=sujet,
                        contenu=contenu,
                        etablissement_id=etab_id,
                    )
                    msg.envoyer()
                    st.success("✅ Message envoyé !")
            else:
                st.warning("Vous n'êtes rattaché à aucun établissement.")


# ── ONGLET 7 : Élèves ─────────────────────────────────────────────
def _onglet_eleves(utilisateur: dict):
    st.subheader("👥 Mes élèves")
    prof_id = utilisateur["uid"]
    classes = ["Toutes"] + ["6e", "5e", "4e", "1ère", "Tle"]
    filtre  = st.selectbox("Classe", classes, key="el_classe")

    classe_param = None if filtre == "Toutes" else filtre
    eleves = Professeur.get_eleves(prof_id, classe=classe_param)

    if not eleves:
        st.info("Aucun élève inscrit.")
        return

    st.markdown(f"**{len(eleves)} élève(s)**")

    for e in sorted(eleves, key=lambda x: x.get("classe","")):
        en_ligne = "🟢" if e.get("en_ligne") else "⚫"
        with st.expander(f"🎓 {en_ligne} {e['nom']} {e['prenom']} — {e.get('classe','?')}"):
            travaux = Professeur.get_travaux_a_corriger(prof_id, eleve_id=e["id"])
            publies = [t for t in travaux if t.get("statut") == "publié" and t.get("note") is not None]
            notes   = [t["note"] for t in publies]
            moy     = f"{sum(notes)/len(notes):.1f}/20" if notes else "—"

            col1, col2, col3 = st.columns(3)
            col1.metric("Travaux", len(travaux))
            col2.metric("Corrigés", len(publies))
            col3.metric("Moyenne", moy)

            diffi = e.get("difficultes", {})
            if diffi:
                st.markdown("**⚠️ Difficultés :**")
                for mat, dl in diffi.items():
                    if dl:
                        st.markdown(f"- **{mat}** : {', '.join(dl[:3])}")
