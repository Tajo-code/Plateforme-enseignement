# vues/vue_professeur.py — V4
import streamlit as st
import datetime
import uuid
from config import get_db, get_bucket
from models.travail import Travail, ExerciceQCM
from models.utilisateur import Professeur
from models.message import Message
from models.journal import Journal
from utils.securite import exiger_role, verifier_acces_professeur, bloquer_acces_non_autorise
from utils.jitsi import afficher_visio, creer_session_visio, get_sessions_actives


def afficher_vue_professeur():
    exiger_role(["professeur", "admin", "super_admin"])
    utilisateur = st.session_state.utilisateur
    prof_id     = utilisateur["uid"]
    etab_ids    = utilisateur.get("etablissements_ids", [])
    if utilisateur.get("etablissement_id") and utilisateur["etablissement_id"] not in etab_ids:
        etab_ids.append(utilisateur["etablissement_id"])
    etab_id = etab_ids[0] if etab_ids else None

    nb_eleves  = Professeur.get_nb_eleves(prof_id)
    travaux    = Professeur.get_travaux_a_corriger(prof_id)
    a_corriger = len([t for t in travaux if t.get("statut") == "soumis"])
    nb_msg     = Message.nb_non_lus(prof_id, etab_id)

    st.title(f"👨‍🏫 Bonjour, {utilisateur['prenom']} !")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("👥 Élèves",     nb_eleves)
    col2.metric("📥 À corriger", a_corriger)
    col3.metric("💬 Messages",   nb_msg)
    col4.metric("✅ Publiés",    len([t for t in travaux if t.get("statut") == "publié"]))

    code = utilisateur.get("code_invitation","—")
    st.info(f"🔑 Code d'invitation : **{code}**")

    # Afficher les établissements
    if etab_ids:
        noms_etabs = []
        for eid in etab_ids:
            from models.etablissement import Etablissement
            e = Etablissement.get(eid)
            if e:
                noms_etabs.append(e.get("nom","?"))
        if noms_etabs:
            st.caption(f"🏫 Établissement(s) : {', '.join(noms_etabs)}")
    if utilisateur.get("est_individuel", True):
        st.caption("👤 Également professeur individuel")

    st.divider()

    onglets = ["📂 Exercices", "🎯 Créer QCM", "📥 Réception", "✏️ Corriger",
           "✅ Publier", "📹 Cours en ligne",
           "🤝 Réunions parents", f"💬 Messages ({nb_msg})", "👥 Élèves"]

    tabs = st.tabs(onglets)
    with tabs[0]: _onglet_exercices(utilisateur, etab_id)
    with tabs[1]: _onglet_qcm(utilisateur)  # nouveau
    with tabs[2]: _onglet_reception(utilisateur)
    with tabs[3]: _onglet_correction(utilisateur)
    with tabs[4]: _onglet_publication(utilisateur)
    with tabs[5]: _onglet_visio_cours(utilisateur, etab_id)
    with tabs[6]: _onglet_visio_parents(utilisateur, etab_id)
    with tabs[7]: _onglet_messages(utilisateur, etab_id)
    with tabs[8]: _onglet_eleves(utilisateur)


# ── ONGLET 1 : Exercices ──────────────────────────────────────────
def _onglet_exercices(utilisateur: dict, etab_id: str):
    st.subheader("📂 Publier un exercice")
    prof_id  = utilisateur["uid"]
    matieres = utilisateur.get("matieres", [])
    classes  = ["6e", "5e", "4e", "1ère", "Tle"]

    col1, col2 = st.columns(2)
    with col1:
        classe  = st.selectbox("🎓 Classe", classes)
    with col2:
        matiere = st.selectbox("📚 Matière", matieres) if matieres else st.text_input("📚 Matière")

    titre     = st.text_input("📌 Titre", placeholder="Ex: Analyse de texte")
    consignes = st.text_area("📋 Consignes et explications", height=120,
                              placeholder="Expliquez ce que vous attendez...")
    format_ex = st.selectbox("📝 Format", ["Devoir individuel","Travail de groupe",
                                            "QCM","Rédaction","Exposé"])
    date_lim  = st.date_input("📅 Date limite", min_value=datetime.date.today())

    # Type de contenu
    type_contenu = st.radio("Contenu de l'exercice",
                             ["Rédiger ici", "Uploader un fichier", "Les deux"],
                             horizontal=True)

    contenu     = ""
    fichier_url = ""

    if type_contenu in ["Rédiger ici", "Les deux"]:
        contenu = st.text_area("✏️ Rédigez l'exercice", height=200,
                                placeholder="Écrivez votre exercice ici...")

    if type_contenu in ["Uploader un fichier", "Les deux"]:
        fichier = st.file_uploader(
            "📎 Fichier exercice",
            type=["pdf","docx","doc","txt","png","jpg"],
            key=f"upload_ex_{prof_id}",
            accept_multiple_files=False
        )
    
        # Lire et stocker IMMÉDIATEMENT dans session_state
        if fichier is not None:
            st.session_state["fichier_prof_bytes"] = fichier.getvalue()
            st.session_state["fichier_prof_nom"]   = fichier.name
            st.session_state["fichier_prof_pret"]  = True
    
        # Afficher confirmation si fichier en attente
        if st.session_state.get("fichier_prof_nom"):
            st.success(f"📎 En attente : **{st.session_state['fichier_prof_nom']}**")
        if fichier:
            try:
                from utils.cloudinary_upload import uploader_fichier
                dossier     = f"exercices/{prof_id}/{classe}/{matiere}"
                fichier_url = uploader_fichier(fichier.getvalue(), fichier.name, dossier)
                st.success(f"✅ Fichier prêt : {fichier.name}")
            except Exception as e:
                st.warning(f"⚠️ Erreur upload : {e}")
                

    if st.button("🚀 Publier l'exercice", type="primary"):
        if not titre or not consignes:
            st.warning("⚠️ Titre et consignes obligatoires.")
            return

        fichier_url = ""
        if (st.session_state.get("fichier_prof_bytes") and
                type_contenu in ["Uploader un fichier", "Les deux"]):
            try:
                from utils.cloudinary_upload import uploader_fichier
                fichier_url = uploader_fichier(
                    st.session_state["fichier_prof_bytes"],
                    st.session_state["fichier_prof_nom"],
                    f"exercices/{prof_id}/{classe}/{matiere}"
                )
            except Exception as e:
                st.warning(f"⚠️ Erreur upload : {e}")

        exercice = {
            "id":             str(uuid.uuid4()),
            "prof_id":        prof_id,
            "etablissement_id": etab_id,
            "classe":         classe,
            "matiere":        matiere,
            "titre":          titre,
            "consignes":      consignes,
            "format":         format_ex,
            "date_limite":    str(date_lim),
            "contenu":        contenu,
            "fichier_url":    fichier_url,
            "date_creation":  datetime.datetime.now().isoformat(),
        }
        get_db().collection("exercices_publies").add(exercice)

        # Nettoyer session
        for k in ["fichier_prof_bytes","fichier_prof_nom"]:
            st.session_state.pop(k, None)

        st.success("✅ Exercice publié !")
        st.balloons()
        st.rerun()
        exercices = Professeur.get_exercices_publies(prof_id)
        exercices = sorted(exercices, key=lambda x: x.get("date_creation",""), reverse=True)

        if not exercices:
            st.info("Aucun exercice publié.")
        else:
            for ex in exercices:
                col1, col2 = st.columns([4, 1])
                with col1:
                    st.markdown(f"📌 **{ex.get('titre','?')}** — {ex.get('classe','?')} | {ex.get('matiere','?')} | {ex.get('date_creation','')[:10]}")
                with col2:
                    if st.button("🗑️", key=f"del_ex_{ex['id']}",
                         help="Supprimer cet exercice"):
                        get_db().collection("exercices_publies").document(ex["id"]).delete()
                        st.success("Exercice supprimé.")
                        st.rerun()
        st.balloons()




# ── ONGLET 2 : Boîte de réception ────────────────────────────────
def _onglet_reception(utilisateur: dict):
    st.subheader("📥 Boîte de réception")
    prof_id = utilisateur["uid"]
    classes = ["Toutes"] + ["6e","5e","4e","1ère","Tle"]

    col1, col2 = st.columns(2)
    with col1:
        filtre_classe = st.selectbox("Classe", classes, key="rec_classe")
    with col2:
        filtre_statut = st.selectbox("Statut", ["Tous","soumis","corrigé","publié"],
                                      key="rec_statut")

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
            col1, col2, col3 = st.columns(3)
            col1.markdown(f"**Élève :** {t['eleve_nom']}")
            col2.markdown(f"**Classe :** {t.get('classe','?')}")
            col3.markdown(f"**Format :** {t.get('format_travail','?')}")
            if t.get("contenu_texte"):
                st.text_area("Réponse", value=t["contenu_texte"],
                             height=120, disabled=True, key=f"r_{t['id']}")
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
            reponse_modifiee = t.get("contenu_texte","")
            if t.get("contenu_texte"):
                reponse_modifiee = st.text_area(
                    "Réponse de l'élève (modifiable — annotez directement)",
                    value=t["contenu_texte"], height=200, key=f"rep_{t['id']}",
                    help="Vous pouvez annoter ou corriger directement la réponse."
                )
            if t.get("fichier_url"):
                st.markdown(f"[📎 Voir fichier]({t['fichier_url']})")

            st.divider()
            note = st.number_input("Note /20", 0.0, 20.0, 0.0, 0.5, key=f"note_{t['id']}")
            remarques = st.text_area("Remarques détaillées",
                                      placeholder="Commentaires, points forts, à améliorer...",
                                      height=100, key=f"rem_{t['id']}")

            if st.button("💾 Enregistrer", type="primary", key=f"save_{t['id']}"):
                if not remarques.strip():
                    st.warning("⚠️ Ajoutez des remarques.")
                else:
                    updates = {
                        "note": note, "remarques": remarques,
                        "statut": "corrigé",
                        "date_corrige": datetime.datetime.now().isoformat(),
                    }
                    if t.get("contenu_texte") and reponse_modifiee != t["contenu_texte"]:
                        updates["contenu_texte_original"] = t["contenu_texte"]
                        updates["contenu_texte_modifie"]  = reponse_modifiee
                    get_db().collection("travaux").document(t["id"]).update(updates)
                    Journal.enregistrer(prof_id, f"{utilisateur['nom']} {utilisateur['prenom']}",
                                        "professeur", "correction",
                                        f"{t['eleve_nom']} — {note}/20")
                    st.success("✅ Correction enregistrée !")
                    st.rerun()


# ── ONGLET 4 : Publier ────────────────────────────────────────────
def _onglet_publication(utilisateur: dict):
    st.subheader("✅ Publier les corrections")
    prof_id  = utilisateur["uid"]
    corriges = Professeur.get_travaux_a_corriger(prof_id, statut="corrigé")

    if not corriges:
        st.info("📭 Aucune correction en attente.")
        return

    st.warning(f"⚠️ **{len(corriges)} correction(s)** prête(s).")
    with st.expander("Aperçu"):
        for t in corriges:
            n = t.get("note","?")
            c = "green" if isinstance(n,(int,float)) and n >= 10 else "red"
            st.markdown(f"- **{t['eleve_nom']}** | {t.get('classe','?')} | {t['matiere']} | :{c}[{n}/20]")

    if st.button("🚀 Publier TOUTES", type="primary"):
        nb = Professeur.publier_corrections(prof_id)
        Journal.enregistrer(prof_id, f"{utilisateur['nom']} {utilisateur['prenom']}",
                            "professeur", "publication", f"{nb} corrections publiées")
        st.success(f"✅ {nb} correction(s) publiée(s) !")
        st.balloons()
        st.rerun()


# ── ONGLET 5 : Cours en ligne ─────────────────────────────────────
def _onglet_visio_cours(utilisateur: dict, etab_id: str):
    st.subheader("📹 Cours en ligne")
    col1, col2 = st.columns(2)

    with col1:
        titre = st.text_input("Titre du cours", placeholder="Ex: Cours de Français — 6e")
        if st.button("📹 Lancer le cours", type="primary"):
            if not titre:
                st.warning("⚠️ Donnez un titre.")
            else:
                session = creer_session_visio(utilisateur["uid"], titre, "cours", etab_id)
                st.success(f"✅ Cours lancé !")
                st.code(session["lien"])
                st.session_state["cours_actif"] = session
                Journal.enregistrer(utilisateur["uid"],
                                    f"{utilisateur['nom']} {utilisateur['prenom']}",
                                    "professeur", "visio_lancee", titre)

    with col2:
        sessions = get_sessions_actives(prof_id=utilisateur["uid"])
        cours    = [s for s in sessions if s.get("type_session") == "cours"]
        if not cours:
            st.info("Aucun cours en cours.")
        for c in cours:
            st.markdown(f"- **{c.get('titre','?')}** — [Lien]({c.get('lien','')})")
            if st.button("Rejoindre", key=f"join_c_{c['id']}"):
                st.session_state["cours_actif"] = c

    if st.session_state.get("cours_actif"):
        cours = st.session_state["cours_actif"]
        st.divider()
        st.markdown(f"### 📹 {cours['titre']}")
        afficher_visio(cours["nom_salle"],
                       f"Prof. {utilisateur['prenom']} {utilisateur['nom']}",
                       est_moderateur=True, hauteur=550)


# ── ONGLET 6 : Réunions parents ───────────────────────────────────
def _onglet_visio_parents(utilisateur: dict, etab_id: str):
    st.subheader("🤝 Réunions parents-administration")
    st.caption("Les professeurs peuvent assister aux réunions organisées par l'administration.")

    if not etab_id:
        st.info("Vous n'êtes rattaché à aucun établissement.")
        return

    sessions = get_sessions_actives(etablissement_id=etab_id)
    reunions = [s for s in sessions if s.get("type_session") == "reunion_parents"]

    if not reunions:
        st.info("Aucune réunion en cours.")
        return

    for r in reunions:
        with st.expander(f"📹 {r.get('titre','Réunion')} — En cours"):
            st.markdown(f"**Lien direct :** [Rejoindre]({r.get('lien','')})")
            if st.button("📹 Rejoindre", key=f"join_r_{r['id']}", type="primary"):
                st.session_state["reunion_prof"] = r

    if st.session_state.get("reunion_prof"):
        r = st.session_state["reunion_prof"]
        st.divider()
        st.markdown(f"### 📹 {r['titre']}")
        afficher_visio(r["nom_salle"],
                       f"Prof. {utilisateur['prenom']} {utilisateur['nom']}",
                       est_moderateur=False, hauteur=550)


# ── ONGLET 7 : Messages ───────────────────────────────────────────
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
                if st.button("🗑️ Supprimer", key=f"del_msg_p_{m['id']}"):
                    Message.supprimer(m["id"])
                    st.rerun()

    with col2:
        st.markdown("**📤 Envoyer à l'administration**")
        sujet   = st.text_input("Sujet", key="msg_s_prof")
        contenu = st.text_area("Message", height=100, key="msg_c_prof")
        if st.button("📤 Envoyer", type="primary", key="btn_msg_prof"):
            if not sujet or not contenu:
                st.warning("⚠️ Remplissez sujet et message.")
            elif etab_id:
                admins = list(get_db().collection("users")
                              .where("etablissement_id","==",etab_id)
                              .where("role","==","admin_etablissement").stream())
                if admins:
                    msg = Message(
                        expediteur_id=utilisateur["uid"],
                        expediteur_nom=f"Prof. {utilisateur['prenom']} {utilisateur['nom']}",
                        destinataire_id=admins[0].id,
                        sujet=sujet, contenu=contenu, etablissement_id=etab_id,
                    )
                    msg.envoyer()
                    Journal.enregistrer(utilisateur["uid"],
                                        f"{utilisateur['nom']} {utilisateur['prenom']}",
                                        "professeur", "message_envoye", sujet)
                    st.success("✅ Message envoyé !")
            else:
                st.warning("Pas d'établissement rattaché.")


# ── ONGLET 8 : Élèves ─────────────────────────────────────────────
def _onglet_eleves(utilisateur: dict):
    st.subheader("👥 Mes élèves")
    prof_id = utilisateur["uid"]
    classes = ["Toutes"] + ["6e","5e","4e","1ère","Tle"]
    filtre  = st.selectbox("Classe", classes, key="el_cl")

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
            publies = [t for t in travaux if t.get("statut")=="publié" and t.get("note") is not None]
            notes   = [t["note"] for t in publies]
            moy     = f"{sum(notes)/len(notes):.1f}/20" if notes else "—"
            col1, col2, col3 = st.columns(3)
            col1.metric("Travaux", len(travaux))
            col2.metric("Corrigés", len(publies))
            col3.metric("Moyenne", moy)
            diffi = e.get("difficultes",{})
            if diffi:
                st.markdown("**⚠️ Difficultés :**")
                for mat, dl in diffi.items():
                    if dl:
                        st.markdown(f"- **{mat}** : {', '.join(dl[:3])}")


def _onglet_qcm(utilisateur: dict):
    st.subheader("🎯 Créer un exercice QCM adaptatif")
    st.caption("Ces exercices seront proposés automatiquement aux élèves selon leurs difficultés.")

    prof_id  = utilisateur["uid"]
    matieres = utilisateur.get("matieres", [])
    classes  = ["6e","5e","4e","1ère","Tle"]

    col1, col2 = st.columns(2)
    with col1:
        classe  = st.selectbox("Classe", classes, key="qcm_classe")
    with col2:
        matiere = st.selectbox("Matière", matieres, key="qcm_matiere") if matieres else st.text_input("Matière", key="qcm_matiere_txt")

    titre = st.text_input("Titre du QCM", key="qcm_titre",
                           placeholder="Ex: QCM Orthographe 6e")

    st.divider()
    st.markdown("**Questions du QCM**")
    st.caption("Ajoutez les questions une par une.")

    if "qcm_questions" not in st.session_state:
        st.session_state.qcm_questions = []

    # Ajouter une question
    with st.expander("➕ Ajouter une question"):
        question_txt  = st.text_input("Question", key="q_txt")
        difficulte    = st.text_input("Difficulté associée",
                                       placeholder="Ex: Accord du participe passé",
                                       key="q_diff")
        nb_choix = st.number_input("Nombre de choix", 2, 4, 3, key="q_nb")
        choix = []
        for i in range(int(nb_choix)):
            c = st.text_input(f"Choix {i+1}", key=f"q_c{i}")
            choix.append(c)
        bonne_reponse = st.selectbox("Bonne réponse", choix if choix else [""], key="q_br")

        if st.button("➕ Ajouter cette question", key="btn_add_q"):
            if question_txt and bonne_reponse:
                st.session_state.qcm_questions.append({
                    "id":            str(uuid.uuid4()),
                    "question":      question_txt,
                    "choix":         [c for c in choix if c],
                    "bonne_reponse": bonne_reponse,
                    "difficulte":    difficulte,
                })
                st.success(f"✅ Question ajoutée ! ({len(st.session_state.qcm_questions)} au total)")
                st.rerun()

    # Afficher les questions ajoutées
    if st.session_state.qcm_questions:
        st.markdown(f"**{len(st.session_state.qcm_questions)} question(s) :**")
        for i, q in enumerate(st.session_state.qcm_questions):
            st.markdown(f"**{i+1}.** {q['question']} — ✅ {q['bonne_reponse']}")

        if st.button("🚀 Publier le QCM", type="primary", key="btn_pub_qcm"):
            if not titre:
                st.warning("⚠️ Donnez un titre au QCM.")
            else:
                from models.travail import ExerciceQCM
                qcm = ExerciceQCM(
                    titre=titre,
                    matiere=matiere,
                    classe=classe,
                    prof_id=prof_id,
                    questions=st.session_state.qcm_questions,
                )
                qcm.sauvegarder()
                st.session_state.qcm_questions = []
                Journal.enregistrer(prof_id,
                                    f"{utilisateur['nom']} {utilisateur['prenom']}",
                                    "professeur", "exercice_publie",
                                    f"QCM: {titre} — {classe} — {matiere}")
                st.success(f"✅ QCM publié ! Il sera proposé automatiquement aux élèves en difficulté.")
                st.balloons()
                st.rerun()

        if st.button("🗑️ Effacer toutes les questions", key="btn_clear_q"):
            st.session_state.qcm_questions = []
            st.rerun()