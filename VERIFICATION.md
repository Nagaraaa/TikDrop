# Vérification

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
