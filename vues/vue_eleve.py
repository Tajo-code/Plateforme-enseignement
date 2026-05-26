# vues/vue_eleve.py — V3 avec visio + exercices adaptés
import streamlit as st
from config import get_db
from models.travail import Travail, ExerciceQCM
from models.utilisateur import Eleve, Professeur
from utils.securite import exiger_role, verifier_acces_eleve, bloquer_acces_non_autorise
from utils.jitsi import afficher_visio, get_sessions_actives


def afficher_vue_eleve():
    exiger_role(["eleve"])
    utilisateur = st.session_state.utilisateur

    if not verifier_acces_eleve(utilisateur["uid"]):
        bloquer_acces_non_autorise()

    prof_id = utilisateur.get("professeur_id", "")
    etab_id = utilisateur.get("etablissement_id", "")

    # Statut professeur
    en_ligne_prof = False
    if prof_id:
        doc = get_db().collection("users").document(prof_id).get()
        if doc.exists:
            en_ligne_prof = doc.to_dict().get("en_ligne", False)

    statut_prof = "🟢 Professeur en ligne" if en_ligne_prof else "⚫ Professeur hors ligne"

    st.title(f"🎓 Bonjour, {utilisateur['prenom']} !")
    st.caption(f"Classe : {utilisateur['classe']}  •  {statut_prof}")

    # Cours en ligne actifs
    cours_actifs = get_sessions_actives(prof_id=prof_id)
    if cours_actifs:
        st.success(f"📹 **Cours en direct disponible !** Votre professeur a lancé un cours.")

    onglet1, onglet2, onglet3, onglet4, onglet5 = st.tabs([
        "📂 Exercices",
        "🎯 Mes difficultés",
        "📋 Mes travaux",
        "📊 Ma progression",
        "📹 Cours en ligne",
    ])

    with onglet1:
        _onglet_exercices(utilisateur)
    with onglet2:
        _onglet_difficultes(utilisateur)
    with onglet3:
        _onglet_travaux(utilisateur)
    with onglet4:
        _onglet_progression(utilisateur)
    with onglet5:
        _onglet_visio(utilisateur, prof_id)


# ── ONGLET 1 : Exercices ──────────────────────────────────────────
def _onglet_exercices(utilisateur: dict):
    st.subheader("📂 Exercices disponibles")
    st.caption("Exercices publiés par votre professeur, du plus récent au plus ancien.")

    prof_id = utilisateur.get("professeur_id")
    classe  = utilisateur.get("classe")

    exercices = Professeur.get_exercices_publies(prof_id, classe=classe)

    if not exercices:
        st.info("📭 Aucun exercice disponible pour le moment.")
        return

    # Trier par date — nouveaux en premier
    exercices = sorted(exercices, key=lambda x: x.get("date_creation",""), reverse=True)

    # Séparer nouveaux (7 derniers jours) et anciens
    import datetime
    maintenant = datetime.datetime.now()
    nouveaux   = []
    anciens    = []

    for ex in exercices:
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
        _afficher_exercices(nouveaux, utilisateur, prof_id, classe)

    if anciens:
        st.markdown("### 📁 Anciens exercices")
        _afficher_exercices(anciens, utilisateur, prof_id, classe)


def _afficher_exercices(exercices, utilisateur, prof_id, classe):
    for ex in exercices:
        date_str = ex.get("date_creation","")[:10]
        with st.expander(f"📌 {ex.get('titre','Sans titre')} — {ex.get('matiere','?')} | {ex.get('format','?')} | {date_str}"):
            st.info(f"**📋 Consignes :** {ex.get('consignes','Pas de consignes.')}")

            if ex.get("contenu"):
                st.markdown("**📝 Exercice :**")
                st.markdown(ex["contenu"])

            st.markdown(f"**📅 Date limite :** {ex.get('date_limite','—')}")
            st.divider()
            st.markdown("**✏️ Soumettre votre réponse :**")

            mode = st.radio("Mode", ["Écrire ici", "Uploader un fichier"],
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
                            prof_id=prof_id,
                            classe=classe,
                            matiere=ex.get("matiere",""),
                            discipline=ex.get("titre",""),
                            format_travail=ex.get("format","Devoir individuel"),
                        )
                        travail.soumettre_texte(contenu)
                        st.success("✅ Travail soumis !")
            else:
                fichier = st.file_uploader("Fichier", type=["pdf","docx","txt","png","jpg"],
                                            key=f"file_{ex['id']}")
                if fichier and st.button("📤 Soumettre", type="primary", key=f"fsub_{ex['id']}"):
                    travail = Travail(
                        eleve_id=utilisateur["uid"],
                        eleve_nom=f"{utilisateur['nom']} {utilisateur['prenom']}",
                        prof_id=prof_id,
                        classe=classe,
                        matiere=ex.get("matiere",""),
                        discipline=ex.get("titre",""),
                        format_travail=ex.get("format","Devoir individuel"),
                    )
                    try:
                        travail.soumettre_fichier(fichier.read(), fichier.name)
                        st.success("✅ Fichier soumis !")
                    except Exception:
                        st.error("❌ Erreur upload. Essayez d'écrire votre réponse directement.")


# ── ONGLET 2 : Mes difficultés ────────────────────────────────────
def _onglet_difficultes(utilisateur: dict):
    st.subheader("🎯 Mes difficultés et exercices adaptés")

    eleve_id = utilisateur["uid"]
    prof_id  = utilisateur.get("professeur_id")
    classe   = utilisateur.get("classe")

    difficultes = Eleve.get_difficultes(eleve_id)

    if not difficultes:
        st.success("✅ Aucune difficulté détectée ! Continuez à travailler.")
    else:
        st.warning("⚠️ Difficultés détectées :")
        for matiere, dl in difficultes.items():
            if dl:
                st.markdown(f"**{matiere} :** {', '.join(dl)}")

    st.divider()
    st.markdown("### 📚 Exercices recommandés pour vous")

    exercices_adaptes = Eleve.get_exercices_adaptes(eleve_id, prof_id, classe)

    if not exercices_adaptes:
        st.info("Aucun exercice adapté disponible pour le moment. Votre professeur en ajoutera bientôt.")
        return

    for ex in exercices_adaptes:
        with st.expander(f"📌 {ex.get('titre','Exercice')} — {ex.get('matiere','?')}"):
            questions = ex.get("questions", [])
            reponses  = {}

            for i, q in enumerate(questions):
                st.markdown(f"**{i+1}. {q['question']}**")
                choix = q.get("choix", [])
                rep   = st.radio("", choix, key=f"qcm_{ex['id']}_{i}", index=None)
                if rep:
                    reponses[q.get("id", str(i))] = rep

            if st.button("✅ Valider", key=f"val_{ex['id']}", type="primary"):
                if len(reponses) < len(questions):
                    st.warning("⚠️ Répondez à toutes les questions.")
                else:
                    resultat = ExerciceQCM.corriger_automatiquement(ex["id"], eleve_id, reponses)
                    note = resultat["note"]
                    couleur = "green" if note >= 10 else "red"
                    st.markdown(f"### Note : :{couleur}[{note}/20]")
                    st.markdown(f"**{resultat['correctes']}/{resultat['total']}** réponses correctes")
                    if resultat["difficultes"]:
                        st.warning(f"À retravailler : {', '.join(resultat['difficultes'])}")
                    else:
                        st.success("🎉 Excellent ! Aucune difficulté détectée.")


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

            if statut == "publié":
                st.markdown("### 📝 Correction")
                note = t.get("note")
                if note is not None:
                    couleur = "green" if note >= 10 else "red"
                    st.markdown(f"**Note : :{couleur}[{note}/20]**")
                st.markdown(f"**Remarques :** {t.get('remarques','—')}")
            else:
                st.info("🔒 Correction disponible après publication par votre professeur.")


# ── ONGLET 4 : Progression ────────────────────────────────────────
def _onglet_progression(utilisateur: dict):
    st.subheader("📊 Ma progression")
    eleve_id = utilisateur["uid"]

    travaux = Eleve.get_travaux(eleve_id)
    publies = [t for t in travaux if t.get("statut") == "publié" and t.get("note") is not None]

    col1, col2, col3 = st.columns(3)
    col1.metric("📤 Soumis",   len(travaux))
    col2.metric("✅ Corrigés", len(publies))
    col3.metric("⏳ En attente", len(travaux) - len(publies))

    if publies:
        notes = [t["note"] for t in publies]
        moy   = sum(notes) / len(notes)
        couleur = "green" if moy >= 10 else "red"
        st.markdown(f"### Moyenne : :{couleur}[{moy:.1f} / 20]")

        st.divider()
        st.markdown("**📚 Par matière :**")
        matieres = {}
        for t in publies:
            matieres.setdefault(t["matiere"], []).append(t["note"])

        for mat, ns in matieres.items():
            m = sum(ns) / len(ns)
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
def _onglet_visio(utilisateur: dict, prof_id: str):
    st.subheader("📹 Cours en ligne")

    sessions = get_sessions_actives(prof_id=prof_id)
    cours    = [s for s in sessions if s.get("type_session") == "cours"]

    if not cours:
        st.info("📭 Aucun cours en ligne pour le moment. Votre professeur lancera un cours depuis son espace.")
        return

    for c in cours:
        with st.expander(f"📹 {c.get('titre','Cours')} — En direct"):
            st.markdown(f"**Lien direct :** [Rejoindre]({c.get('lien','')})")
            if st.button("📹 Rejoindre le cours", key=f"join_{c['id']}", type="primary"):
                st.session_state["cours_eleve"] = c

    if st.session_state.get("cours_eleve"):
        cours_actif = st.session_state["cours_eleve"]
        st.divider()
        st.markdown(f"### 📹 {cours_actif['titre']}")
        nom = f"{utilisateur['prenom']} {utilisateur['nom']}"
        afficher_visio(
            nom_salle=cours_actif["nom_salle"],
            nom_utilisateur=nom,
            est_moderateur=False,
            hauteur=550
        )
