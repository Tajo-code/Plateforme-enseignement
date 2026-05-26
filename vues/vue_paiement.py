# vues/vue_paiement.py — Espace paiement MTN MoMo + Orange Money
import streamlit as st
from models.abonnement import Abonnement, FORFAITS_DEFAUT
from models.paiement import Paiement
from config import get_db


def afficher_vue_paiement():
    utilisateur = st.session_state.utilisateur
    role = utilisateur.get("role")

    st.title("💳 Abonnement & Paiement")

    # Statut abonnement actuel
    _afficher_statut_abonnement(utilisateur)

    st.divider()

    onglet1, onglet2 = st.tabs(["📦 Choisir un forfait", "📋 Historique"])

    with onglet1:
        _onglet_forfaits(utilisateur, role)
    with onglet2:
        _onglet_historique(utilisateur)


# ── Statut abonnement ─────────────────────────────────────────────
def _afficher_statut_abonnement(utilisateur: dict):
    import datetime
    abonnement_fin  = utilisateur.get("abonnement_fin")
    abonnement_actif = utilisateur.get("abonnement_actif", True)

    if not abonnement_fin:
        st.info("🎁 Vous bénéficiez d'un mois d'essai gratuit.")
        return

    try:
        date_fin = datetime.datetime.fromisoformat(abonnement_fin)
        jours    = (date_fin - datetime.datetime.now()).days

        if not abonnement_actif:
            st.error("⛔ Votre abonnement est suspendu. Renouvelez pour réactiver votre compte.")
        elif jours <= 0:
            st.error("⛔ Votre abonnement a expiré.")
        elif jours <= 7:
            st.warning(f"⚠️ Abonnement expire dans **{jours} jour(s)**.")
        else:
            st.success(f"✅ Abonnement actif — expire le **{date_fin.strftime('%d/%m/%Y')}** ({jours} jours restants)")
    except Exception:
        st.info("Abonnement en cours.")


# ── ONGLET 1 : Choisir un forfait ────────────────────────────────
def _onglet_forfaits(utilisateur: dict, role: str):
    st.subheader("📦 Choisir votre forfait")

    forfaits = Abonnement.get_forfaits()

    # Filtrer selon le rôle
    if role in ["professeur", "professeur_individuel"]:
        forfaits_affiches = {k: v for k, v in forfaits.items() if v.get("cible") == "professeur"}
    elif role in ["admin_etablissement"]:
        forfaits_affiches = {k: v for k, v in forfaits.items() if v.get("cible") == "etablissement"}
    else:
        forfaits_affiches = forfaits

    if not forfaits_affiches:
        st.info("Aucun forfait disponible.")
        return

    # Afficher les forfaits en colonnes
    cols = st.columns(min(3, len(forfaits_affiches)))
    forfait_choisi = None

    for i, (fid, f) in enumerate(forfaits_affiches.items()):
        with cols[i % 3]:
            st.markdown(f"""
            <div style="
                border: 2px solid #1a1a2e;
                border-radius: 12px;
                padding: 20px;
                text-align: center;
                margin-bottom: 10px;
            ">
                <h3>{f.get('label','?')}</h3>
                <h2 style="color:#1a1a2e;">{f.get('prix_fcfa',0):,} FCFA</h2>
                <p>{f.get('duree_jours',30)} jours</p>
            </div>
            """, unsafe_allow_html=True)
            if st.button(f"Choisir", key=f"choisir_{fid}", use_container_width=True):
                st.session_state["forfait_choisi"] = fid

    st.divider()

    # Formulaire de paiement
    if st.session_state.get("forfait_choisi"):
        fid     = st.session_state["forfait_choisi"]
        forfait = forfaits.get(fid, {})

        st.markdown(f"### Payer : **{forfait.get('label','?')}** — {forfait.get('prix_fcfa',0):,} FCFA")

        col1, col2 = st.columns(2)
        with col1:
            operateur = st.selectbox("Opérateur",
                                      ["mtn", "orange"],
                                      format_func=lambda x: "MTN Mobile Money" if x == "mtn" else "Orange Money")
        with col2:
            telephone = st.text_input("Numéro de téléphone",
                                       value=utilisateur.get("telephone", ""),
                                       placeholder="+237600000000")

        st.info(f"💡 Vous allez recevoir une demande de confirmation sur le **{operateur.upper()}** au numéro **{telephone}**")

        if st.button("💳 Payer maintenant", type="primary", use_container_width=True):
            if not telephone:
                st.warning("⚠️ Entrez votre numéro de téléphone.")
            else:
                with st.spinner("Traitement du paiement..."):
                    paiement = Paiement(
                        utilisateur_id=utilisateur["uid"],
                        forfait_id=fid,
                        montant_fcfa=forfait.get("prix_fcfa", 0),
                        operateur=operateur,
                        telephone=telephone,
                    )
                    resultat = paiement.initier()

                if resultat.get("succes"):
                    if resultat.get("simulation"):
                        st.success(f"✅ {resultat['message']}")
                        st.info("En production, vous recevrez une notification sur votre téléphone.")
                    elif resultat.get("url"):
                        st.success("✅ Redirection vers le paiement...")
                        st.markdown(f"[👉 Cliquez ici pour payer]({resultat['url']})")
                    st.session_state.pop("forfait_choisi", None)
                else:
                    st.error(f"❌ {resultat.get('message', 'Erreur de paiement.')}")


# ── ONGLET 2 : Historique ─────────────────────────────────────────
def _onglet_historique(utilisateur: dict):
    st.subheader("📋 Historique des paiements")

    paiements = Paiement.get_historique(utilisateur["uid"])

    if not paiements:
        st.info("Aucun paiement enregistré.")
        return

    for p in sorted(paiements, key=lambda x: x.get("date_creation",""), reverse=True):
        statut = p.get("statut","?")
        icone  = {"confirme": "✅", "en_attente": "🕐", "echoue": "❌"}.get(statut, "?")
        with st.expander(f"{icone} {p.get('forfait_id','?')} — {p.get('montant_fcfa',0):,} FCFA | {p.get('date_creation','')[:10]}"):
            st.markdown(f"**Opérateur :** {p.get('operateur','?').upper()}")
            st.markdown(f"**Statut :** {statut}")
            st.markdown(f"**Transaction :** {p.get('transaction_id','—')}")
