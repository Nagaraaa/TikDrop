# Vérification

## Version 1.2.0 — 10 novembre 2026

Exécutable construit par GitHub Actions (`windows-latest`, Windows Server 2025
10.0.26100) avec `Construire.cmd` : Python 3.12.10, yt-dlp 2026.10.26,
curl-cffi 0.17.0, PyInstaller 6.22.3.

- 19 tests unitaires réussis sous Windows avec Python 3.12 et 3.14
  (`python -m unittest -v`) : les 9 de la 1.1.0, plus les messages d’erreur
  (format absent, erreurs réseau de Python et de curl), le choix du H.264
  par la vraie sélection de formats de yt-dlp, et `test_app.py` (sous-processus
  réel qui réussit, signale une erreur, plante ou sort sans fichier ; rapport
  copié ; journal des échecs).
- Exécutable fenêtré lancé en mode worker par la CI : il démarre, charge yt-dlp
  et curl_cffi et renvoie ses événements. TikTok bloque l’adresse IP des
  serveurs de GitHub (« IP address is blocked »), message correctement traduit.
- Archive `TikDrop-Windows.zip` : même structure que celle de la 1.1.0.
- Interface pilotée par script sous Linux (Python 3.12, Tk 8.6, Xvfb) avec de
  vrais sous-processus : échecs réseau affichés « Problème de connexion
  Internet », bouton « Copier l’erreur », rapport dans le presse-papiers,
  journal `tikdrop.log`, pas de bandeau presse-papiers après la copie.
  Capture inspectée.

Non vérifié avant publication : téléchargement réel réussi (TikTok inaccessible
depuis les environnements de test), lecture des vidéos H.264 dans l’application
Photos, rendu de l’interface sous Windows pour cette version.

## Version 1.1.0 — 10 novembre 2026

Environnement : Windows 11 x64, yt-dlp 2026.10.26, curl-cffi 0.17.0,
PyInstaller 6.22.3. Développement sous Python 3.14.7 (Tk 9.0) ; exécutable de la
release construit et retesté sous Python 3.12.10 (Tk 8.6).

- 9 tests unitaires réussis (`python -m unittest -v`) : liens courts, texte de
  partage et doublons, rejet des domaines trompeurs et profils, liens ignorés sans
  bloquer les autres, port invalide, progression simulée, fichier déjà présent et
  métadonnées, refus d’un faux succès sans fichier, messages d’erreur en français.
- Téléchargements réels depuis les sources : 2 vidéos publiques enregistrées
  (1,2 Mo et 1,8 Mo), puis un second passage correctement marqué « Déjà présente ».
  Un identifiant inexistant produit un échec propre avec message en français.
- Interface pilotée par script : état vide, bandeau presse-papiers, liens ignorés,
  progression, fin, annulation, bouton Réessayer, défilement automatique, fenêtre
  réduite à 680 × 560. Captures inspectées visuellement.
- Exécutable construit en mode fenêtré (`--windowed`) : la fenêtre s’ouvre sans
  console, avec l’icône TikDrop et la barre de titre sombre. Le sous-processus de
  téléchargement de l’exécutable renvoie bien ses événements (téléchargement réel,
  fichier déjà présent, erreur).
- Mêmes vérifications répétées sous Python 3.12.10 / Tk 8.6 : tests unitaires,
  parcours complet de l’interface, exécutable fenêtré et téléchargements réels.

Non vérifié : Windows 10, autres réseaux ou régions, écrans à 125–200 %
d’échelle, annulation au milieu d’un long téléchargement réel.

## Version 1.0.0 — 9 novembre 2026

Windows 11 x64, Python 3.12.10 : 5 tests unitaires réussis, test Tk scripté,
construction Windows réussie. Fonctionnement confirmé par l’utilisateur.
