# vues/vue_superadmin.py — Espace Super Administrateur V3
import streamlit as st
import datetime
import secrets
from auth.authentification import creer_compte, supprimer_compte
from models.utilisateur import SuperAdmin
from models.etablissement import Etablissement, TAILLES
from models.abonnement import Abonnement, FORFAITS_DEFAUT
from utils.securite import exiger_role


def afficher_vue_superadmin():
    exiger_role(["super_admin"])
    utilisateur = st.session_state.utilisateur

    st.title("👑 Espace Super Administrateur")
    st.caption(f"Connecté : {utilisateur['prenom']} {utilisateur['nom']}")

    onglet1, onglet2, onglet3, onglet4, onglet5 = st.tabs([
        "🏫 Établissements",
        "👥 Utilisateurs",
        "💰 Forfaits & Abonnements",
        "➕ Créer un compte",
        "📊 Vue globale",
    ])

    with onglet1:
        _onglet_etablissements(utilisateur)
    with onglet2:
        _onglet_utilisateurs()
    with onglet3:
        _onglet_forfaits(utilisateur)
    with onglet4:
        _onglet_creation()
    with onglet5:
        _onglet_vue_globale()


# ── ONGLET 1 : Établissements ─────────────────────────────────────
def _onglet_etablissements(utilisateur: dict):
    st.subheader("🏫 Gestion des établissements")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**➕ Créer un établissement**")
        nom    = st.text_input("Nom de l'établissement")
        ville  = st.text_input("Ville")
        taille = st.selectbox("Taille", list(TAILLES.keys()),
                               format_func=lambda x: TAILLES[x]["label"])

        if st.button("✅ Créer l'établissement", type="primary"):
            if not nom or not ville:
                st.warning("⚠️ Remplissez tous les champs.")
            else:
                etab = Etablissement(nom, ville, taille, utilisateur["uid"])
                etab.sauvegarder()

                # Créer abonnement essai sans mettre à jour users
                from models.abonnement import Abonnement as Abo
                abo = Abo(etab.id, "etablissement", est_essai=True)
                abo.sauvegarder()
                st.success(f"✅ Établissement créé !")
                st.info(f"**ID :** `{etab.id}` | **Code invitation :** `{etab.code_invitation}`")
                st.rerun()

    with col2:
        st.markdown("**📋 Liste des établissements**")
        etablissements = Etablissement.get_tous()

        if not etablissements:
            st.info("Aucun établissement créé.")

        for etab in etablissements:
            statut = "✅ Actif" if etab.get("actif") else "⛔ Suspendu"
            with st.expander(f"🏫 {etab['nom']} — {etab.get('ville','?')} | {statut}"):
                st.markdown(f"**ID :** `{etab['id']}`")
                st.markdown(f"**Code invitation :** `{etab.get('code_invitation','—')}`")
                st.markdown(f"**Taille :** {etab.get('taille','?')}")
                st.markdown(f"**Créé le :** {etab.get('date_creation','')[:10]}")

                membres = Etablissement.get_membres(etab["id"])
                profs   = len([m for m in membres if m.get("role") == "professeur"])
                eleves  = len([m for m in membres if m.get("role") == "eleve"])
                parents = len([m for m in membres if m.get("role") == "parent"])
                st.markdown(f"**Membres :** {profs} profs | {eleves} élèves | {parents} parents")

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    if etab.get("actif"):
                        if st.button("⛔ Suspendre", key=f"susp_{etab['id']}"):
                            Etablissement.suspendre(etab["id"])
                            st.success("Établissement suspendu.")
                            st.rerun()
                    else:
                        if st.button("✅ Réactiver", key=f"react_{etab['id']}"):
                            Etablissement.reactiver(etab["id"])
                            st.success("Établissement réactivé.")
                            st.rerun()

                with col_b:
                    jours_prolonger = st.number_input("Prolonger (jours)",
                                                       min_value=1, max_value=365,
                                                       value=30, key=f"jours_{etab['id']}")
                with col_c:
                    if st.button("⏳ Prolonger", key=f"prol_{etab['id']}"):
                        Abonnement.prolonger(etab["id"], int(jours_prolonger), utilisateur["uid"])
                        st.success(f"Prolongé de {jours_prolonger} jours !")
                        st.rerun()


# ── ONGLET 2 : Utilisateurs ───────────────────────────────────────
def _onglet_utilisateurs():
    st.subheader("👥 Tous les utilisateurs")
    tous = SuperAdmin.get_tous_utilisateurs()

    filtre = st.selectbox("Filtrer", ["Tous", "super_admin", "admin_etablissement",
                                       "professeur", "professeur_individuel",
                                       "eleve", "parent"])
    if filtre != "Tous":
        tous = [u for u in tous if u.get("role") == filtre]

    st.markdown(f"**{len(tous)} utilisateur(s)**")

    for u in sorted(tous, key=lambda x: x.get("role", "")):
        icones = {
            "super_admin":          "👑",
            "admin_etablissement":  "🏫",
            "professeur":           "👨‍🏫",
            "professeur_individuel":"👨‍🏫",
            "eleve":                "🎓",
            "parent":               "👨‍👩‍👧",
        }
        icone    = icones.get(u.get("role"), "👤")
        en_ligne = "🟢" if u.get("en_ligne") else "⚫"

        with st.expander(f"{icone} {en_ligne} {u.get('nom','?')} {u.get('prenom','?')} — {u.get('role','?')}"):
            col1, col2 = st.columns(2)
            col1.markdown(f"**Email :** {u.get('email','—')}")
            col2.markdown(f"**Tél :** {u.get('telephone','—')}")
            col1.markdown(f"**Inscrit le :** {u.get('date_creation','—')[:10]}")

            if u.get("etablissement_id"):
                etab = Etablissement.get(u["etablissement_id"])
                col2.markdown(f"**Établissement :** {etab.get('nom','?') if etab else '—'}")

            # Abonnement
            abo_fin = u.get("abonnement_fin")
            if abo_fin:
                try:
                    date_fin = datetime.datetime.fromisoformat(abo_fin)
                    jours    = (date_fin - datetime.datetime.now()).days
                    statut_abo = f"{'✅' if jours > 0 else '⛔'} {jours} jours restants"
                    st.markdown(f"**Abonnement :** {statut_abo}")

                    col_j, col_b = st.columns(2)
                    with col_j:
                        jours_p = st.number_input("Prolonger (jours)", min_value=1,
                                                   max_value=365, value=30,
                                                   key=f"jp_{u['id']}")
                    with col_b:
                        if st.button("⏳ Prolonger", key=f"p_{u['id']}"):
                            from auth.authentification import est_connecte
                            super_uid = st.session_state.utilisateur["uid"]
                            Abonnement.prolonger(u["id"], int(jours_p), super_uid)
                            st.success("Prolongé !")
                            st.rerun()
                except Exception:
                    pass

            uid_actuel = st.session_state.utilisateur["uid"]
            if u["id"] != uid_actuel and u.get("role") != "super_admin":
                if st.button(f"🗑️ Supprimer", key=f"del_{u['id']}"):
                    ok, msg = supprimer_compte(u["id"])
                    if ok:
                        st.success(msg)
                        st.rerun()
                    else:
                        st.error(msg)


# ── ONGLET 3 : Forfaits & Abonnements ────────────────────────────
def _onglet_forfaits(utilisateur: dict):
    st.subheader("💰 Gestion des forfaits")
    st.caption("Définissez librement les montants et durées.")

    forfaits = Abonnement.get_forfaits()
    forfaits_modifies = {}

    st.markdown("**Forfaits Professeurs individuels**")
    profs_forfaits = {k: v for k, v in forfaits.items() if v.get("cible") == "professeur"}

    for fid, f in profs_forfaits.items():
        with st.expander(f"📦 {f.get('label','?')}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                label = st.text_input("Libellé", value=f.get("label",""), key=f"l_{fid}")
            with col2:
                prix = st.number_input("Prix (FCFA)", min_value=0,
                                        value=f.get("prix_fcfa", 0), step=500, key=f"p_{fid}")
            with col3:
                duree = st.number_input("Durée (jours)", min_value=1,
                                         value=f.get("duree_jours", 30), key=f"d_{fid}")
            forfaits_modifies[fid] = {**f, "label": label, "prix_fcfa": prix, "duree_jours": duree}

    st.divider()
    st.markdown("**Forfaits Établissements**")
    etab_forfaits = {k: v for k, v in forfaits.items() if v.get("cible") == "etablissement"}

    for fid, f in etab_forfaits.items():
        with st.expander(f"🏫 {f.get('label','?')}"):
            col1, col2, col3 = st.columns(3)
            with col1:
                label = st.text_input("Libellé", value=f.get("label",""), key=f"l_{fid}")
            with col2:
                prix = st.number_input("Prix (FCFA)", min_value=0,
                                        value=f.get("prix_fcfa", 0), step=5000, key=f"p_{fid}")
            with col3:
                duree = st.number_input("Durée (jours)", min_value=1,
                                         value=f.get("duree_jours", 365), key=f"d_{fid}")
            forfaits_modifies[fid] = {**f, "label": label, "prix_fcfa": prix, "duree_jours": duree}

    if st.button("💾 Sauvegarder tous les forfaits", type="primary"):
        Abonnement.sauvegarder_forfaits(forfaits_modifies)
        st.success("✅ Forfaits mis à jour !")


# ── ONGLET 4 : Créer un compte ────────────────────────────────────
def _onglet_creation():
    st.subheader("➕ Créer un nouveau compte")

    role = st.selectbox("Rôle", ["professeur_individuel", "admin_etablissement", "admin"])

    col1, col2 = st.columns(2)
    with col1:
        prenom = st.text_input("Prénom")
        email  = st.text_input("Email")
    with col2:
        nom       = st.text_input("Nom")
        telephone = st.text_input("Téléphone", placeholder="+237600000000")

    mdp = st.text_input("Mot de passe temporaire", type="password")

    matieres      = []
    etablissement_id = None

    if role == "professeur_individuel":
        matieres_input = st.text_input("Matières (séparées par virgules)")
        matieres = [m.strip() for m in matieres_input.split(",") if m.strip()]

    if role == "admin_etablissement":
        etablissements = Etablissement.get_tous()
        if etablissements:
            noms_etab = {f"{e['nom']} ({e['ville']})": e["id"] for e in etablissements}
            choix_etab = st.selectbox("Établissement", list(noms_etab.keys()))
            etablissement_id = noms_etab.get(choix_etab)
        else:
            st.warning("Aucun établissement créé. Créez d'abord un établissement.")

    if st.button("✅ Créer le compte", type="primary"):
        if not all([prenom, nom, email, mdp]):
            st.warning("⚠️ Remplissez tous les champs.")
            return
        ok, msg = creer_compte(prenom, nom, email, mdp, telephone, role,
                                matieres=matieres,
                                etablissement_id=etablissement_id)
        if ok:
            st.success(f"✅ Compte {role} créé pour {nom} {prenom}.")
        else:
            st.error(msg)


# ── ONGLET 5 : Vue globale ────────────────────────────────────────
def _onglet_vue_globale():
    st.subheader("📊 Statistiques globales")

    tous         = SuperAdmin.get_tous_utilisateurs()
    etablissements = Etablissement.get_tous()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("🏫 Établissements", len(etablissements))
    col2.metric("👨‍🏫 Professeurs",   len([u for u in tous if "professeur" in u.get("role","")]))
    col3.metric("🎓 Élèves",         len([u for u in tous if u.get("role") == "eleve"]))
    col4.metric("👨‍👩‍👧 Parents",       len([u for u in tous if u.get("role") == "parent"]))

    st.divider()

    # Abonnements expirés
    import datetime
    expires = []
    for u in tous:
        abo_fin = u.get("abonnement_fin")
        if abo_fin:
            try:
                if datetime.datetime.fromisoformat(abo_fin) < datetime.datetime.now():
                    expires.append(u)
            except Exception:
                pass

    if expires:
        st.warning(f"⚠️ **{len(expires)} compte(s)** avec abonnement expiré :")
        for u in expires:
            st.markdown(f"- {u.get('nom')} {u.get('prenom')} ({u.get('role','?')})")
