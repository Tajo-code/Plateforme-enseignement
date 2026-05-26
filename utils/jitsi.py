# utils/jitsi.py — Visioconférence via Jitsi Meet (gratuit, intégré)
import secrets
import streamlit as st
import streamlit.components.v1 as components


def generer_salle(prefixe: str = "cours") -> str:
    """Génère un nom de salle unique."""
    code = secrets.token_hex(4).upper()
    return f"plateforme-{prefixe}-{code}"


def afficher_visio(nom_salle: str, nom_utilisateur: str,
                   est_moderateur: bool = False, hauteur: int = 600) -> None:
    """
    Intègre Jitsi Meet directement dans l'application Streamlit.
    Gratuit, sans inscription, fonctionne dans le navigateur.
    """
    # Configuration Jitsi
    config_jitsi = f"""
    <div id="jitsi-container" style="width:100%;height:{hauteur}px;"></div>
    <script src="https://meet.jit.si/external_api.js"></script>
    <script>
        const domain = 'meet.jit.si';
        const options = {{
            roomName: '{nom_salle}',
            width: '100%',
            height: {hauteur},
            parentNode: document.getElementById('jitsi-container'),
            userInfo: {{
                displayName: '{nom_utilisateur}'
            }},
            configOverwrite: {{
                startWithAudioMuted: false,
                startWithVideoMuted: false,
                enableWelcomePage: false,
                prejoinPageEnabled: false,
                disableDeepLinking: true,
            }},
            interfaceConfigOverwrite: {{
                SHOW_JITSI_WATERMARK: false,
                SHOW_WATERMARK_FOR_GUESTS: false,
                DEFAULT_REMOTE_DISPLAY_NAME: 'Participant',
                TOOLBAR_BUTTONS: [
                    'microphone', 'camera', 'desktop', 'chat',
                    'raisehand', 'participants-pane', 'hangup',
                    {'tileview' if est_moderateur else ''},
                    {'mute-everyone' if est_moderateur else ''},
                ],
            }},
        }};
        const api = new JitsiMeetExternalAPI(domain, options);

        // Événements
        api.addEventListeners({{
            readyToClose: () => {{
                document.getElementById('jitsi-container').innerHTML =
                    '<p style="text-align:center;padding:20px;">✅ Conférence terminée.</p>';
            }},
        }});
    </script>
    """
    components.html(config_jitsi, height=hauteur + 20, scrolling=False)


def creer_session_visio(organisateur_id: str, titre: str,
                         type_session: str, etablissement_id: str = None) -> dict:
    """
    Crée une session de visioconférence et la sauvegarde dans Firestore.
    type_session: 'cours' | 'reunion_parents' | 'reunion_profs'
    """
    from config import get_db
    import datetime, uuid

    nom_salle = generer_salle(type_session)
    session = {
        "id":               str(uuid.uuid4()),
        "nom_salle":        nom_salle,
        "titre":            titre,
        "organisateur_id":  organisateur_id,
        "type_session":     type_session,
        "etablissement_id": etablissement_id,
        "date_creation":    datetime.datetime.now().isoformat(),
        "actif":            True,
        "lien":             f"https://meet.jit.si/{nom_salle}",
    }
    get_db().collection("sessions_visio").add(session)
    return session


def get_sessions_actives(etablissement_id: str = None,
                          prof_id: str = None) -> list[dict]:
    """Récupère les sessions de visioconférence actives."""
    from config import get_db
    q = get_db().collection("sessions_visio").where("actif", "==", True)
    if etablissement_id:
        q = q.where("etablissement_id", "==", etablissement_id)
    if prof_id:
        q = q.where("organisateur_id", "==", prof_id)
    return [{"id": d.id, **d.to_dict()} for d in q.stream()]
