# utils/cloudinary_upload.py
import cloudinary
import cloudinary.uploader
import streamlit as st
import hashlib
import hmac
import time


def uploader_fichier(fichier_bytes: bytes, nom_fichier: str,
                     dossier: str = "plateforme") -> str:
    """Upload un fichier sur Cloudinary et retourne l'URL publique."""

    cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"]
    api_key    = st.secrets["CLOUDINARY_API_KEY"]
    api_secret = st.secrets["CLOUDINARY_API_SECRET"]

    cloudinary.config(
        cloud_name = cloud_name,
        api_key    = api_key,
        api_secret = api_secret,
        secure     = True
    )

    # Nettoyer le nom du fichier
    import unicodedata
    nom_propre = unicodedata.normalize('NFKD', nom_fichier)
    nom_propre = nom_propre.encode('ascii', 'ignore').decode('ascii')
    public_id  = nom_propre.replace(" ", "_").replace(".", "_")
    ext       = nom_fichier.split(".")[-1].lower()
    resource_type = "raw" if ext in ["pdf","docx","doc","txt"] else "image"

    resultat = cloudinary.uploader.upload(
        fichier_bytes,
        folder        = dossier,
        public_id     = public_id,
        resource_type = resource_type,
        overwrite     = True,
    )
    return resultat.get("secure_url", "")
