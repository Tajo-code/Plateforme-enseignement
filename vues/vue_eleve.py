# vues/vue_eleve.py — V4 multi-établissements
import streamlit as st
import datetime
from config import get_db, get_bucket
from models.travail import Travail, ExerciceQCM
from models.utilisateur import Eleve, Professeur
from models.journal import Journal
from utils.securite import exiger_role, verifier_acces_eleve, bloquer_acces_non_autorise
from utils.jitsi import afficher_visio, get_sessions_actives


def afficher_vue_eleve():
    exiger_role(["eleve"])
    utilisateur = st.session_state.utilisateur

    if not verifier_acces_eleve(utilisateur["uid"]):
        bloquer_acces_non_autorise()

    # Récupérer tous les profs et établissements
    prof_ids  = utilisateur.get("professeurs_ids", [])
    if utilisateur.get("professeur_id") and utilisateur["professeur_id"] not in prof_ids:
        prof_ids.append(utilisateur["professeur_id"])
    prof_id = prof_ids[0] if prof_ids else ""

    etab_ids = utilisateur.get("etablissements_ids", [])
    if utilisateur.get("etablissement_id") and utilisateur["etablissement_id"] not in etab_ids:
        etab_ids.append(utilisateur["etablissement_id"])
    etab_id = etab_ids[0] if etab_ids else ""

    # Statut professeur
    en_ligne_prof = False
    for pid in prof_ids:
        doc = get_db().collection("users").document(pid).get()
        if doc.exists and doc.to_dict().get("en_ligne"):
            en_ligne_prof = True
            break

    statut_prof = "🟢 Professeur en ligne" if en_ligne_prof else "⚫ Professeur hors ligne"

    st.title(f"🎓 Bonjour, {utilisateur['prenom']} !")
    st.caption(f"Classe : {utilisateur['classe']}  •  {statut_prof}")
    
    # Cours en direct
    for pid in prof_ids:
        cours_actifs = get_sessions_actives(prof_id=pid)
        if cours_actifs:
            st.success(f"📹 **Cours en direct disponible !** Rejoignez maintenant.")
            break

    onglet1, onglet2, onglet3, onglet4, onglet5 = st.tabs([
        "📂 Exercices",
        "🎯 Mes difficultés",
        "📋 Mes travaux",
        "📊 Ma progression",
        "📹 Cours en ligne",
    ])

    with onglet1: _onglet_exercices(utilisateur, prof_ids, etab_ids)
    with onglet2: _onglet_difficultes(utilisateur, prof_id)
    with onglet3: _onglet_travaux(utilisateur)
    with onglet4: _onglet_progression(utilisateur)
    with onglet5: _onglet_visio(utilisateur, prof_ids)


# ── ONGLET 1 : Exercices ──────────────────────────────────────────
def _onglet_exercices(utilisateur: dict, prof_ids: list, etab_ids: list):
    st.subheader("📂 Exercices disponibles")
    st.caption("Exercices publiés par vos professeurs, du plus récent au plus ancien.")

    classe = utilisateur.get("classe")
    tous_exercices = []

    # Exercices de chaque prof
    for pid in prof_ids:
        exos = Professeur.get_exercices_publies(pid, classe=classe)
        for ex in exos:
            if not any(x["id"] == ex["id"] for x in tous_exercices):
                tous_exercices.append(ex)

    # Exercices des établissements
    for eid in etab_ids:
        exos = Professeur.get_exercices_etablissement(eid, classe=classe)
        for ex in exos:
            if not any(x["id"] == ex["id"] for x in tous_exercices):
                tous_exercices.append(ex)
    
    # chercher aussi les QCM publiés
    for pid in prof_ids:
        qcms = get_db().collection("exercices_qcm")\
            .where("prof_ids", "==",pid)\
            .where("classe", "==",classe)\
            .stream()
        for q in qcms:
            ex = {"id":q.id, **q.to_dict()}
            ex["titre"]     = ex.get("titre", "QCM")
            ex["format"]    = "QCM"
            ex["consignes"] = "repondez à toutes les questions"
            ex["contenu"]   = ""
            ex["est_qcm"]   = True
            if not any(x["id"] == ex["id"] for x in tous_exercices):
                tous_exercices.append(ex)


    if not tous_exercices:
        st.info("📭 Aucun exercice disponible pour le moment.")
        return

    # Trier par date
    tous_exercices = sorted(tous_exercices,
                            key=lambda x: x.get("date_creation",""), reverse=True)

    # Séparer nouveaux / anciens
    maintenant = datetime.datetime.now()
    nouveaux, anciens = [], []
    for ex in tous_exercices:
        try:
            date_ex = datetime.datetime.fromisoformat(ex.get("date_creation",""))
            if (maintenant - date_ex).days <= 7:
                nouveaux.append(ex)
            else:
                anciens.append(ex)
        except Exception:
            anciens.append(ex)

    if nouveaux:
        st.markdown("### 🆕 Nouveaux exercices (7 derniers jours)")
        _afficher_liste_exercices(nouveaux, utilisateur)

    if anciens:
        st.markdown("### 📁 Anciens exercices")
        _afficher_liste_exercices(anciens, utilisateur)


def _afficher_liste_exercices(exercices: list, utilisateur: dict):
    for ex in exercices:
        date_str = ex.get("date_creation","")[:10]
        with st.expander(f"📌 {ex.get('titre','?')} — {ex.get('matiere','?')} | {ex.get('format','?')} | {date_str}"):
            st.info(f"**📋 Consignes :** {ex.get('consignes','Pas de consignes.')}")

            if ex.get("contenu"):
                st.markdown("**📝 Exercice :**")
                st.markdown(ex["contenu"])

            if ex.get("fichier_url"):
                st.markdown(f"[📥 Télécharger le fichier]({ex['fichier_url']})")

            st.markdown(f"**📅 Date limite :** {ex.get('date_limite','—')}")
            st.divider()
       # si c'est un QCM, afficher les questions directement
            if ex.get("est_qcm"):
                questions = ex.get("questions", [])
                reponses = {}
                for i, q in enumerate(questions):
                    st.markdown(f"**{i+1}. {q['question']}**")
                    rep = st.radio("", q.get("choix", []), 
                                   key=f"qcm_ex_{ex['id']}_{i}", index=None)
                    if rep:
                        reponses[q.get("id", str(i))] = rep
                if st.button("Valider le QCM", key=f"val_qcm_{ex['id']}", type="primary"):
                    if len(reponses) < len(questions):
                        st.warning("Répondez à toutes les questions.")
                    else:
                        from models.travail import ExerciceQCM
                        resultat = ExerciceQCM.corriger_automatiquement(ex["id"], utilisateur["uid"], reponses)
                        note = resultat["note"]
                        c = "green" if note >= 10 else "red"
                        st.markdown(f"### : {c}[{note}/20]")
                        st.markdown(f"**{resultat['correctes']}/{resultat['total']}** correctes")
                        if resultat["difficultes"]:
                            st.warning(f"A retravailler : {','.join(resultat['difficultes'])}")
                        else:
                            st.success("Parfait")
                return # Ne pas afficher le formulaire de soumission pour un QCM
            st.markdown("**✏️ Soumettre votre réponse :**")

            prof_id = ex.get("prof_id") or utilisateur.get("professeur_id","")
            classe  = utilisateur.get("classe","")
            mode    = st.radio("Mode", ["Écrire ici","Uploader un fichier"],
                               horizontal=True, key=f"mode_{ex['id']}")

            if mode == "Écrire ici":
                contenu = st.text_area("Votre réponse", height=250,
                                        key=f"rep_{ex['id']}",
                                        placeholder="Rédigez votre réponse ici...")

                if st.button("📤 Soumettre", type="primary", key=f"sub_{ex['id']}"):
                    if not contenu.strip():
                        st.warning("⚠️ Écrivez votre réponse.")
                    else:
                        travail = Travail(
                            eleve_id=utilisateur["uid"],
                            eleve_nom=f"{utilisateur['nom']} {utilisateur['prenom']}",
                            prof_id=prof_id, classe=classe,
                            matiere=ex.get("matiere",""),
                            discipline=ex.get("titre",""),
                            format_travail=ex.get("format","Devoir individuel"),
                        )
                        travail.soumettre_texte(contenu)
                        Journal.enregistrer(utilisateur["uid"],
                                            f"{utilisateur['nom']} {utilisateur['prenom']}",
                                            "eleve", "devoir_soumis",
                                            f"{ex.get('titre','')} — {classe}")
                        st.success("✅ Travail soumis !")
            else:
                fichier = st.file_uploader("Fichier",
                            type=["pdf","docx","txt","png","jpg"],
                            key=f"file_{ex['id']}")

                if fichier is not None:
                    st.session_state[f"fichier_eleve_{ex['id']}"] = {
                        "bytes": fichier.getvalue(),
                        "nom":   fichier.name,
                    }

                if st.session_state.get(f"fichier_eleve_{ex['id']}"):
                    f_data = st.session_state[f"fichier_eleve_{ex['id']}"]
                    st.info(f"📎 Fichier prêt : {f_data['nom']}")
    
                    if st.button("📤 Soumettre", type="primary", key=f"fsub_{ex['id']}"):
                        travail = Travail(
                            eleve_id=utilisateur["uid"],
                            eleve_nom=f"{utilisateur['nom']} {utilisateur['prenom']}",
                            prof_id=prof_id, classe=classe,
                            matiere=ex.get("matiere",""),
                            discipline=ex.get("titre",""),
                            format_travail=ex.get("format","Devoir individuel"),
                        )
                        try:
                            travail.soumettre_fichier(f_data["bytes"], f_data["nom"])
                            st.session_state.pop(f"fichier_eleve_{ex['id']}", None)
                            Journal.enregistrer(utilisateur["uid"],
                                        f"{utilisateur['nom']} {utilisateur['prenom']}",
                                        "eleve", "devoir_soumis",
                                        f"Fichier: {f_data['nom']}")
                            st.success("✅ Fichier soumis !")
                            st.rerun()
                        except Exception:
                            st.error("❌ Erreur upload.")


# ── ONGLET 2 : Difficultés ────────────────────────────────────────
def _onglet_difficultes(utilisateur: dict, prof_id: str):
    st.subheader("🎯 Mes difficultés et exercices adaptés")

    eleve_id = utilisateur["uid"]
    classe   = utilisateur.get("classe")
    diffi    = Eleve.get_difficultes(eleve_id)

    if not diffi:
        st.success("✅ Aucune difficulté détectée !")
    else:
        st.warning("⚠️ Difficultés détectées :")
        for matiere, dl in diffi.items():
            if dl:
                st.markdown(f"**{matiere} :** {', '.join(dl)}")

    st.divider()
    st.markdown("### 📚 Exercices recommandés pour vous")

    exercices_adaptes = Eleve.get_exercices_adaptes(eleve_id, prof_id, classe)

    if not exercices_adaptes:
        st.info("Aucun exercice adapté disponible pour le moment.")
        return

    for ex in exercices_adaptes:
        with st.expander(f"📌 {ex.get('titre','Exercice')} — {ex.get('matiere','?')}"):
            questions = ex.get("questions",[])
            reponses  = {}
            for i, q in enumerate(questions):
                st.markdown(f"**{i+1}. {q['question']}**")
                rep = st.radio("", q.get("choix",[]),
                               key=f"qcm_{ex['id']}_{i}", index=None)
                if rep:
                    reponses[q.get("id",str(i))] = rep

            if st.button("✅ Valider", key=f"val_{ex['id']}", type="primary"):
                if len(reponses) < len(questions):
                    st.warning("⚠️ Répondez à toutes les questions.")
                else:
                    resultat = ExerciceQCM.corriger_automatiquement(
                        ex["id"], eleve_id, reponses)
                    note = resultat["note"]
                    c = "green" if note >= 10 else "red"
                    st.markdown(f"### Note : :{c}[{note}/20]")
                    st.markdown(f"**{resultat['correctes']}/{resultat['total']}** correctes")
                    if resultat["difficultes"]:
                        st.warning(f"À retravailler : {', '.join(resultat['difficultes'])}")
                    else:
                        st.success("🎉 Excellent !")


# ── ONGLET 3 : Mes travaux ────────────────────────────────────────
def _onglet_travaux(utilisateur: dict):
    st.subheader("📋 Mes travaux soumis")
    eleve_id = utilisateur["uid"]

    if not verifier_acces_eleve(eleve_id):
        bloquer_acces_non_autorise()

    travaux = Eleve.get_travaux(eleve_id)
    if not travaux:
        st.info("📭 Vous n'avez encore soumis aucun travail.")
        return

    for t in sorted(travaux, key=lambda x: x.get("date_soumis",""), reverse=True):
        statut = t.get("statut","soumis")
        icone  = {"soumis":"🕐","corrigé":"🔒","publié":"✅"}.get(statut,"🕐")
        with st.expander(f"{icone} {t['matiere']} — {t.get('discipline','')} | {t.get('date_soumis','')[:10]} | {statut}"):
            if t.get("contenu_texte_modifie"):
                st.markdown("**Votre réponse (annotée par le professeur) :**")
                st.text(t["contenu_texte_modifie"])
            elif t.get("contenu_texte"):
                st.markdown("**Votre réponse :**")
                st.text(t["contenu_texte"])
            if t.get("fichier_url"):
                st.markdown(f"[📎 Voir le fichier]({t['fichier_url']})")
            st.divider()
            # Suppression uniquement si pas encore corrigé
            if statut == "soumis":
                if st.button("🗑️ Retirer ce travail", key=f"del_t_{t['id']}"):
                    get_db().collection("travaux").document(t["id"]).delete()
                    st.success("Travail retiré.")
                    st.rerun()
            if statut == "publié":
                st.markdown("### 📝 Correction")
                note = t.get("note")
                if note is not None:
                    c = "green" if note >= 10 else "red"
                    st.markdown(f"**Note : :{c}[{note}/20]**")
                st.markdown(f"**Remarques :** {t.get('remarques','—')}")
            else:
                st.info("🔒 Correction disponible après publication.")


# ── ONGLET 4 : Progression ────────────────────────────────────────
def _onglet_progression(utilisateur: dict):
    st.subheader("📊 Ma progression")
    eleve_id = utilisateur["uid"]

    travaux = Eleve.get_travaux(eleve_id)
    publies = [t for t in travaux if t.get("statut")=="publié" and t.get("note") is not None]

    col1, col2, col3 = st.columns(3)
    col1.metric("📤 Soumis",    len(travaux))
    col2.metric("✅ Corrigés",  len(publies))
    col3.metric("⏳ En attente", len(travaux)-len(publies))

    if publies:
        notes = [t["note"] for t in publies]
        moy   = sum(notes)/len(notes)
        c = "green" if moy >= 10 else "red"
        st.markdown(f"### Moyenne : :{c}[{moy:.1f} / 20]")
        st.divider()
        st.markdown("**📚 Par matière :**")
        matieres = {}
        for t in publies:
            matieres.setdefault(t["matiere"],[]).append(t["note"])
        for mat, ns in matieres.items():
            m = sum(ns)/len(ns)
            c = "green" if m >= 10 else "red"
            st.markdown(f"- **{mat}** : :{c}[{m:.1f}/20] ({len(ns)} devoir(s))")

    diffi = Eleve.get_difficultes(eleve_id)
    if diffi:
        st.divider()
        st.markdown("**⚠️ Points à améliorer :**")
        for mat, dl in diffi.items():
            if dl:
                st.markdown(f"- **{mat}** : {', '.join(dl)}")


# ── ONGLET 5 : Cours en ligne ─────────────────────────────────────
def _onglet_visio(utilisateur: dict, prof_ids: list):
    st.subheader("📹 Cours en ligne")

    tous_cours = []
    for pid in prof_ids:
        sessions = get_sessions_actives(prof_id=pid)
        cours    = [s for s in sessions if s.get("type_session") == "cours"]
        tous_cours.extend(cours)

    if not tous_cours:
        st.info("📭 Aucun cours en direct. Votre professeur lancera un cours depuis son espace.")
        return

    for c in tous_cours:
        with st.expander(f"📹 {c.get('titre','Cours')} — En direct"):
            st.markdown(f"**Lien direct :** [Rejoindre]({c.get('lien','')})")
            if st.button("📹 Rejoindre", key=f"join_{c['id']}", type="primary"):
                st.session_state["cours_eleve"] = c

    if st.session_state.get("cours_eleve"):
        c = st.session_state["cours_eleve"]
        st.divider()
        st.markdown(f"### 📹 {c['titre']}")
        afficher_visio(c["nom_salle"],
                       f"{utilisateur['prenom']} {utilisateur['nom']}",
                       est_moderateur=False, hauteur=550)
