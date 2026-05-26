# utils/securite.py — Contrôle d'accès strict par rôle
import streamlit as st

def est_connecte() -> bool:
    return "utilisateur" in st.session_state and st.session_state.utilisateur is not None

def role_actuel() -> str | None:
    if est_connecte():
        return st.session_state.utilisateur.get("role")
    return None

def est_super_admin() -> bool:
    return role_actuel() == "super_admin"

def est_admin() -> bool:
    return role_actuel() in ["admin", "super_admin"]

def est_professeur() -> bool:
    return role_actuel() in ["professeur", "admin", "super_admin"]

def est_eleve() -> bool:
    return role_actuel() == "eleve"

def exiger_role(roles_autorises: list[str]) -> None:
    if not est_connecte():
        st.error("🔒 Vous devez être connecté pour accéder à cette page.")
        st.stop()
    if role_actuel() not in roles_autorises:
        st.error("⛔ Accès refusé.")
        st.stop()

def verifier_acces_eleve(eleve_id_demande: str) -> bool:
    utilisateur = st.session_state.get("utilisateur", {})
    role = utilisateur.get("role")
    if role in ["super_admin", "admin", "professeur"]:
        return True
    if role == "eleve":
        return utilisateur.get("uid") == eleve_id_demande
    return False

def verifier_acces_professeur(prof_id_demande: str) -> bool:
    utilisateur = st.session_state.get("utilisateur", {})
    role = utilisateur.get("role")
    if role in ["super_admin", "admin"]:
        return True
    if role == "professeur":
        return utilisateur.get("uid") == prof_id_demande
    return False

def bloquer_acces_non_autorise() -> None:
    st.error("⛔ Accès refusé.")
    st.stop()
