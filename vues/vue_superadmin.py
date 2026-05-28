# vues/vue_superadmin.py — V4
import streamlit as st
import datetime
from auth.authentification import creer_compte, supprimer_compte, verifier_mot_de_passe
from models.utilisateur import SuperAdmin
from models.etablissement import Etablissement, TAILLES
from models.abonnement import Abonnement, FORFAITS_DEFAUT
from models.journal import Journal
from utils.securite import exiger_role


def afficher_vue_superadmin():
    exiger_role(["super_admin"])
    utilisateur = st.session_state.utilisateur

    st.title("👑 Espace Super Administrateur")
    st.caption(f"Connecté : {utilisateur['prenom']} {utilisateur['nom']}")

    onglet1, onglet2, onglet3, onglet4, onglet5, onglet6 = st.tabs([
        "🏫 Établissements",
        "👥 Utilisateurs",
        "💰 Forfaits",
        "➕ Créer un compte",
        "📋 Journal",
        "📊 Vue globale",
    ])

    with onglet1:
        _onglet_etablissements(utilisateur)
    with onglet2:
        _onglet_utilisateurs(utilisateur)
    with onglet3:
        _onglet_forfaits()
    with onglet4:
        _onglet_creation()
    with onglet5:
        _onglet_journal()
    with onglet6:
        _onglet_vue_globale()


# ── ONGLET 1 : Établissements ─────────────────────────────────────
def _onglet_etablissements(utilisateur: dict):
    st.subheader("🏫 Gestion des établissements")
    col1, col2 = st.columns(2)

    with col1:
        st.markdown("**➕ Créer un établissement**")
        nom    = st.text_input("Nom",   key="etab_nom")
        ville  = st.text_input("Ville", key="etab_ville")
        taille = st.selectbox("Taille", list(TAILLES.keys()),
                               format_func=lambda x: TAILLES[x]["label"])
        if st.button("✅ Créer", type="primary"):
            if not nom or not ville:
                st.warning("⚠️ Remplissez tous les champs.")
            else:
                etab = Etablissement(nom, ville, taille, utilisateur["uid"])
                etab.sauvegarder()
                try:
                    abo = Abonnement(etab.id, "etablissement", est_essai=True)
                    abo.sauvegarder()
                except Exception:
                    pass
                Journal.enregistrer(utilisateur["uid"],
                                    f"{utilisateur['nom']} {utilisateur['prenom']}",
                                    "super_admin", "creation_etab", f"{nom} — {ville}")
                st.success(f"✅ Établissement créé !")
                st.info(f"**ID :** `{etab.id}` | **Code :** `{etab.code_invitation}`")
                st.rerun()

    with col2:
        st.markdown("**📋 Liste**")
        etablissements = Etablissement.get_tous()
        if not etablissements:
            st.info("Aucun établissement.")

        for etab in etablissements:
            statut = "✅ Actif" if etab.get("actif") else "⛔ Suspendu"
            with st.expander(f"🏫 {etab['nom']} — {statut}"):
                st.markdown(f"**ID :** `{etab['id']}`")
                st.markdown(f"**Code :** `{etab.get('code_invitation','—')}`")
                membres = Etablissement.get_membres(etab["id"])
                profs   = len([m for m in membres if m.get("role")=="professeur"])
                eleves  = len([m for m in membres if m.get("role")=="eleve"])
                parents = len([m for m in membres if m.get("role")=="parent"])
                st.markdown(f"**Membres :** {profs} profs | {eleves} élèves | {parents} parents")

                col_a, col_b = st.columns(2)
                with col_a:
                    if etab.get("actif"):
                        if st.button("⛔ Suspendre", key=f"susp_{etab['id']}"):
                            _confirmer_action(
                                utilisateur,
                                lambda: _suspendre_etab(etab["id"], utilisateur),
                                f"susp_confirm_{etab['id']}"
                            )
                    else:
                        if st.button("✅ Réactiver", key=f"react_{etab['id']}"):
                            Etablissement.reactiver(etab["id"])
                            Journal.enregistrer(utilisateur["uid"],
                                                f"{utilisateur['nom']} {utilisateur['prenom']}",
                                                "super_admin", "reactivation",
                                                f"Établissement: {etab['nom']}")
                            st.success("Réactivé !")
                            st.rerun()

                with col_b:
                    jours = st.number_input("Prolonger (jours)", 1, 365, 30,
                                             key=f"jp_{etab['id']}")
                    if st.button("⏳ Prolonger", key=f"prol_{etab['id']}"):
                        try:
                            # Mettre à jour l'établissement directement
                            import datetime as dt
                            nouvelle_fin = dt.datetime.now() + dt.timedelta(days=int(jours))
                            _db_update_etab(etab["id"], nouvelle_fin)
                            Journal.enregistrer(utilisateur["uid"],
                                                f"{utilisateur['nom']} {utilisateur['prenom']}",
                                                "super_admin", "prolongement",
                                                f"Établissement {etab['nom']}: +{jours} jours")
                            st.success(f"Prolongé de {jours} jours !")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Erreur : {e}")


def _db_update_etab(etab_id: str, nouvelle_fin) -> None:
    from config import get_db
    get_db().collection("etablissements").document(etab_id).update({
        "abonnement_actif": True,
        "abonnement_fin":   nouvelle_fin.isoformat(),
    })


def _suspendre_etab(etab_id: str, utilisateur: dict) -> None:
    Etablissement.suspendre(etab_id)
    etab = Etablissement.get(etab_id)
    Journal.enregistrer(utilisateur["uid"],
                        f"{utilisateur['nom']} {utilisateur['prenom']}",
                        "super_admin", "suspension_etab",
                        f"Établissement: {etab.get('nom','?') if etab else etab_id}")


def _confirmer_action(utilisateur: dict, action_fn, key: str) -> None:
    """Demande le mot de passe avant une action critique."""
    if f"confirm_{key}" not in st.session_state:
        st.session_state[f"confirm_{key}"] = False

    if not st.session_state[f"confirm_{key}"]:
        mdp = st.text_input("🔐 Confirmez votre mot de passe", type="password", key=f"mdp_{key}")
        if st.button("Confirmer", key=f"btn_{key}"):
            if verifier_mot_de_passe(utilisateur["email"], mdp):
                st.session_state[f"confirm_{key}"] = True
                action_fn()
                st.rerun()
            else:
                st.error("❌ Mot de passe incorrect.")


# ── ONGLET 2 : Utilisateurs ───────────────────────────────────────
def _onglet_utilisateurs(utilisateur: dict):
    st.subheader("👥 Tous les utilisateurs")
    tous = SuperAdmin.get_tous_utilisateurs()

    filtre = st.selectbox("Filtrer", ["Tous", "super_admin", "admin_etablissement",
                                       "professeur", "eleve", "parent", "admin"])
    if filtre != "Tous":
        tous = [u for u in tous if u.get("role") == filtre]

    st.markdown(f"**{len(tous)} utilisateur(s)**")

    for u in sorted(tous, key=lambda x: x.get("role","")):
        icones = {"super_admin":"👑","admin_etablissement":"🏫","admin":"🛡️",
                  "professeur":"👨‍🏫","eleve":"🎓","parent":"👨‍👩‍👧"}
        icone    = icones.get(u.get("role"),"👤")
        en_ligne = "🟢" if u.get("en_ligne") else "⚫"

        with st.expander(f"{icone} {en_ligne} {u.get('nom','?')} {u.get('prenom','?')} — {u.get('role','?')}"):
            col1, col2 = st.columns(2)
            col1.markdown(f"**Email :** {u.get('email','—')}")
            col2.markdown(f"**Tél :** {u.get('telephone','—')}")
            col1.markdown(f"**Inscrit le :** {u.get('date_creation','—')[:10]}")

            # Établissements
            etab_ids = u.get("etablissements_ids",[])
            if u.get("etablissement_id") and u["etablissement_id"] not in etab_ids:
                etab_ids.append(u["etablissement_id"])
            if etab_ids:
                noms_etabs = []
                for eid in etab_ids:
                    e = Etablissement.get(eid)
                    if e:
                        noms_etabs.append(e.get("nom","?"))
                col2.markdown(f"**Établissement(s) :** {', '.join(noms_etabs)}")

            # Abonnement
            abo_fin = u.get("abonnement_fin")
            if abo_fin:
                try:
                    date_fin = datetime.datetime.fromisoformat(abo_fin)
                    jours    = (date_fin - datetime.datetime.now()).days
                    st.markdown(f"**Abonnement :** {'✅' if jours>0 else '⛔'} {jours} jours restants")
                    col_j, col_p = st.columns(2)
                    with col_j:
                        jp = st.number_input("Prolonger (j)", 1, 365, 30, key=f"jp_{u['id']}")
                    with col_p:
                        if st.button("⏳ Prolonger", key=f"p_{u['id']}"):
                            Abonnement.prolonger(u["id"], int(jp), utilisateur["uid"])
                            Journal.enregistrer(utilisateur["uid"],
                                                f"{utilisateur['nom']} {utilisateur['prenom']}",
                                                "super_admin", "prolongement",
                                                f"{u.get('nom','')} {u.get('prenom','')}: +{jp}j")
                            st.success("Prolongé !")
                            st.rerun()
                except Exception:
                    pass

            # Actions critiques avec confirmation mot de passe
            uid_actuel = utilisateur["uid"]
            if u["id"] != uid_actuel and u.get("role") != "super_admin":
                st.divider()
                col_s, col_d = st.columns(2)

                with col_s:
                    if u.get("abonnement_actif", True):
                        if st.button(f"⛔ Suspendre", key=f"susp_u_{u['id']}"):
                            st.session_state[f"action_u_{u['id']}"] = "suspendre"

                with col_d:
                    if st.button(f"🗑️ Supprimer", key=f"del_{u['id']}"):
                        st.session_state[f"action_u_{u['id']}"] = "supprimer"

                # Confirmation
                if st.session_state.get(f"action_u_{u['id']}"):
                    action = st.session_state[f"action_u_{u['id']}"]
                    st.warning(f"⚠️ Confirmez votre mot de passe pour **{action}** ce compte.")
                    mdp_conf = st.text_input("Mot de passe", type="password",
                                              key=f"mdp_conf_{u['id']}")
                    col_ok, col_ann = st.columns(2)
                    with col_ok:
                        if st.button("✅ Confirmer", key=f"ok_{u['id']}"):
                            if verifier_mot_de_passe(utilisateur["email"], mdp_conf):
                                if action == "supprimer":
                                    ok, msg = supprimer_compte(u["id"])
                                    Journal.enregistrer(utilisateur["uid"],
                                                        f"{utilisateur['nom']} {utilisateur['prenom']}",
                                                        "super_admin", "suppression_compte",
                                                        f"{u.get('nom','')} {u.get('prenom','')} ({u.get('role','')})")
                                elif action == "suspendre":
                                    from config import get_db
                                    get_db().collection("users").document(u["id"]).update({
                                        "abonnement_actif": False
                                    })
                                    Journal.enregistrer(utilisateur["uid"],
                                                        f"{utilisateur['nom']} {utilisateur['prenom']}",
                                                        "super_admin", "suspension",
                                                        f"{u.get('nom','')} {u.get('prenom','')}")
                                    ok, msg = True, "Compte suspendu."
                                if ok:
                                    st.success(msg)
                                    del st.session_state[f"action_u_{u['id']}"]
                                    st.rerun()
                            else:
                                st.error("❌ Mot de passe incorrect.")
                    with col_ann:
                        if st.button("Annuler", key=f"ann_{u['id']}"):
                            del st.session_state[f"action_u_{u['id']}"]
                            st.rerun()


# ── ONGLET 3 : Forfaits ───────────────────────────────────────────
def _onglet_forfaits():
    st.subheader("💰 Gestion des forfaits")
    forfaits = Abonnement.get_forfaits()
    forfaits_modifies = {}

    for fid, f in forfaits.items():
        with st.expander(f"📦 {f.get('label','?')} — {f.get('prix_fcfa',0):,} FCFA"):
            col1, col2, col3 = st.columns(3)
            label = col1.text_input("Libellé", value=f.get("label",""), key=f"l_{fid}")
            prix  = col2.number_input("Prix (FCFA)", 0, value=f.get("prix_fcfa",0),
                                       step=500, key=f"p_{fid}")
            duree = col3.number_input("Durée (jours)", 1, value=f.get("duree_jours",30),
                                       key=f"d_{fid}")
            forfaits_modifies[fid] = {**f, "label":label, "prix_fcfa":prix, "duree_jours":duree}

    if st.button("💾 Sauvegarder", type="primary"):
        Abonnement.sauvegarder_forfaits(forfaits_modifies)
        Journal.enregistrer(
            st.session_state.utilisateur["uid"],
            f"{st.session_state.utilisateur['nom']} {st.session_state.utilisateur['prenom']}",
            "super_admin", "modification_forfait"
        )
        st.success("✅ Forfaits mis à jour !")


# ── ONGLET 4 : Créer un compte ────────────────────────────────────
def _onglet_creation():
    st.subheader("➕ Créer un compte")

    role = st.selectbox("Rôle", [
        "professeur",
        "admin_etablissement",
        "admin",
    ], format_func=lambda x: {
        "professeur":          "👨‍🏫 Professeur (individuel et/ou établissement)",
        "admin_etablissement": "🏫 Admin établissement",
        "admin":               "🛡️ Administrateur",
    }.get(x, x))

    col1, col2 = st.columns(2)
    with col1:
        prenom = st.text_input("Prénom",    key="create_prenom")
        email  = st.text_input("Email",     key="create_email")
    with col2:
        nom       = st.text_input("Nom",       key="create_nom")
        telephone = st.text_input("Téléphone", key="create_tel", placeholder="+237600000000")

    mdp = st.text_input("Mot de passe temporaire", type="password", key="create_mdp")

    matieres         = []
    etablissements_ids = []
    est_individuel   = True

    if role == "professeur":
        mat_input = st.text_input("Matières...", key="create_matieres")
        matieres  = [m.strip() for m in mat_input.split(",") if m.strip()]

        est_individuel = st.checkbox("Professeur individuel (hors établissement)", value=True)

        etablissements = Etablissement.get_tous()
        if etablissements:
            noms = {f"{e['nom']} ({e['ville']})": e["id"] for e in etablissements}
            choix = st.multiselect("Établissement(s) rattaché(s) (optionnel)", list(noms.keys()))
            etablissements_ids = [noms[c] for c in choix]

    elif role == "admin_etablissement":
        etablissements = Etablissement.get_tous()
        if etablissements:
            noms   = {f"{e['nom']} ({e['ville']})": e["id"] for e in etablissements}
            choix  = st.multiselect("Établissement(s)", list(noms.keys()))
            etablissements_ids = [noms[c] for c in choix]

    if st.button("✅ Créer le compte", type="primary"):
        if not all([prenom, nom, email, mdp]):
            st.warning("⚠️ Remplissez tous les champs.")
            return
        ok, msg = creer_compte(prenom, nom, email, mdp, telephone, role,
                                matieres=matieres,
                                etablissements_ids=etablissements_ids,
                                est_individuel=est_individuel)
        if ok:
            st.success(f"✅ Compte créé pour {nom} {prenom}.")
            if role == "professeur":
                st.info("Le code d'invitation est visible dans la liste des utilisateurs.")
        else:
            st.error(msg)


# ── ONGLET 5 : Journal ────────────────────────────────────────────
def _onglet_journal():
    st.subheader("📋 Journal des activités")
    st.caption("Toutes les actions effectuées sur la plateforme.")

    col1, col2, col3 = st.columns(3)
    with col1:
        filtre_role = st.selectbox("Rôle", ["Tous","super_admin","admin_etablissement",
                                             "professeur","eleve","parent"])
    with col2:
        filtre_action = st.selectbox("Action", ["Toutes"] + list(Journal.ACTIONS.keys()
                                                if hasattr(Journal, 'ACTIONS') else
                                                ["connexion","deconnexion","creation_compte",
                                                 "suppression_compte","suspension"]))
    with col3:
        limite = st.number_input("Nombre max", 50, 1000, 200, step=50)

    entrees = Journal.get_tout(int(limite))

    if filtre_role != "Tous":
        entrees = [e for e in entrees if e.get("role") == filtre_role]
    if filtre_action != "Toutes":
        entrees = [e for e in entrees if e.get("action") == filtre_action]

    st.markdown(f"**{len(entrees)} entrée(s)**")

    # Export Excel
    if entrees:
        excel = Journal.exporter_excel(entrees)
        st.download_button(
            label="📥 Exporter en Excel",
            data=excel,
            file_name=f"journal_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

    st.divider()

    for e in entrees[:100]:  # Afficher max 100 dans l'UI
        date   = e.get("date","")[:19].replace("T"," ")
        nom    = e.get("utilisateur_nom","?")
        role   = e.get("role","?")
        action = e.get("libelle","?")
        detail = e.get("details","")
        st.markdown(f"`{date}` — **{nom}** ({role}) — {action}" +
                    (f" — *{detail}*" if detail else ""))


# ── ONGLET 6 : Vue globale ────────────────────────────────────────
def _onglet_vue_globale():
    st.subheader("📊 Statistiques globales")

    tous           = SuperAdmin.get_tous_utilisateurs()
    etablissements = Etablissement.get_tous()

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("🏫 Établissements", len(etablissements))
    col2.metric("👨‍🏫 Professeurs",   len([u for u in tous if u.get("role")=="professeur"]))
    col3.metric("🎓 Élèves",         len([u for u in tous if u.get("role")=="eleve"]))
    col4.metric("👨‍👩‍👧 Parents",       len([u for u in tous if u.get("role")=="parent"]))
    col5.metric("🟢 En ligne",       len([u for u in tous if u.get("en_ligne")]))

    st.divider()
    # Abonnements expirés
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
        st.warning(f"⚠️ **{len(expires)}** compte(s) avec abonnement expiré :")
        for u in expires:
            st.markdown(f"- {u.get('nom')} {u.get('prenom')} ({u.get('role','?')})")
