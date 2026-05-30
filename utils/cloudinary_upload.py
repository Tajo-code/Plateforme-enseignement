# utils/cloudinary_upload.py
import cloudinary
import cloudinary.uploader
import streamlit as st
import re
import unicodedata

def initialiser_cloudinary():
    cloudinary.config(
        cloud_name = st.secrets["CLOUDINARY_CLOUD_NAME"],
        api_key    = st.secrets["CLOUDINARY_API_KEY"],
        api_secret = st.secrets["CLOUDINARY_API_SECRET"],
        secure     = True
    )
def nettoyer_nom(nom: str) -> str:
    # Enlève les accents
    nom = unicodedata.normalize('NFKD', nom).encode('ASCII', 'ignore').decode('ASCII')
    # Remplace tout ce qui n'est pas lettre/chiffre/_/- par _
    nom = re.sub(r'[^a-zA-Z0-9_-]', '_', nom)
    return nom

def uploader_fichier(fichier_bytes: bytes, nom_fichier: str,
                     dossier: str = "plateforme") -> str:
    """
    Upload un fichier sur Cloudinary et retourne l'URL publique.
    Supporte PDF, Word, images.
    """
    try:
        initialiser_cloudinary()
        # Déterminer le type de ressource
        ext = nom_fichier.split(".")[-1].lower()
        resource_type = "raw" if ext in ["pdf","docx","doc","txt"] else "image"
        dossier_prore = nettoyer_nom(dossier) # Français -> Francais
        public_id_propre = nettoyer_nom(nom_fichier.rsplit(".", 1)[0]) # enlève.docx + espaces
        resultat = cloudinary.uploader.upload(
            fichier_bytes,
            folder=dossier_prore,
            public_id=public_id_propre,
            resource_type=resource_type,
            use_filename=False,
            unique_filename=False,
            overwrite=True,

        )
        return resultat.get("secure_url","")
    except Exception as e:
        raise Exception(f"Erreur upload Cloudinary : {str(e)}")