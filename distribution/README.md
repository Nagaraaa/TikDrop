# TikDrop

Petite application de bureau en français pour télécharger des vidéos TikTok
publiques à partir de liens. Code sous licence MIT, sans publicité ni télémétrie.
Au démarrage, seul le numéro de la dernière version est demandé à GitHub pour
signaler une mise à jour (`"check_updates": false` dans `settings.json` pour l’éviter).
Les requêtes vont directement vers les services nécessaires à yt-dlp/TikTok.
Aucun mot de passe, cookie de navigateur ou clé API demandé.

## Windows, version prête à lancer

Décompresser entièrement `TikDrop-Windows.zip`, puis ouvrir `TikDrop.exe` dans
le dossier extrait. Ne pas déplacer l’exécutable seul : `_internal` est nécessaire.
Python n’est pas requis pour cette version. Le programme n’est pas signé.

Téléchargement : [dernière release Windows](https://github.com/Nagaraaa/TikDrop/releases/latest).

1. Coller un ou plusieurs liens TikTok (ou le texte du partage). Un lien copié
   est aussi proposé automatiquement : cliquer sur **Ajouter**.
2. Choisir un dossier de destination avec **Changer…** (il est mémorisé).
3. Cliquer sur **Télécharger** (ou Ctrl+Entrée), puis sur **Afficher** pour
   retrouver une vidéo. **Réessayer** relance seulement les échecs.

Les liens courts `vm.tiktok.com`, `vt.tiktok.com`, `/t/…` et les liens
`/@auteur/video/identifiant` sont acceptés. Les doublons identiques sont ignorés.
Les fichiers portent le nom de l’auteur et l’identifiant de la vidéo.
Une nouvelle tentative reprend les fichiers `.part`; les fichiers déjà présents
ne sont pas écrasés. Les doublons qui utilisent deux liens courts différents
peuvent apparaître dans la file mais le même fichier ne sera pas écrasé.
L’annulation peut laisser un fichier `.part`, supprimable ou reprenable.

## Lancer les sources

Python 3.10 ou plus récent avec Tkinter. Versions testées : Python 3.12 et 3.14 / Windows.
Double-cliquer sur `Lancer.cmd`, ou :

```sh
python -m venv .venv
# Windows : .venv\Scripts\activate
# Linux/macOS : source .venv/bin/activate
python -m pip install -r requirements.txt
python app.py
```

La première installation des sources nécessite Internet.

## Développement

`app.py` contient l’interface et sa file de tâches; `core.py` valide les liens
et appelle yt-dlp. Chaque téléchargement tourne dans un sous-processus afin de
pouvoir arrêter une requête réseau sans bloquer l’interface.

```sh
python -m unittest -v
```

Pour construire sous Windows : `Construire.cmd`. Le résultat est dans
`dist/TikDrop`. Pour actualiser le moteur après un changement de TikTok :

```sh
python -m pip install --upgrade yt-dlp curl-cffi
```

Mettre ensuite à jour `requirements.txt` et reconstruire pour distribuer une
nouvelle version portable. La version portable fournie ne s’actualise pas seule.

## Limites

Vidéos publiques individuelles uniquement; pas de profils complets, directs,
diaporamas photo, contenu privé ou contournement d’une connexion obligatoire.
TikTok peut refuser une requête selon le réseau, la région ou ses protections;
un lien valide ne garantit donc pas le téléchargement. Les erreurs courantes
sont expliquées en français dans l’interface. Pour signaler un problème, cliquer
sur **Copier l’erreur** à côté de la vidéo et coller le texte dans une issue ;
les échecs sont aussi notés dans `%APPDATA%\TikDrop\tikdrop.log`.

Le moteur sélectionne un fichier audio/vidéo combiné, de préférence MP4, pour
éviter une installation FFmpeg. Il ne garantit ni la résolution maximale parmi
les pistes séparées ni l’absence de filigrane. Aucun retrait de filigrane ajouté.
Télécharger ses créations ou les contenus pour lesquels on dispose des droits.

## Licence et dépendances

Le code TikDrop est sous MIT (`LICENSE`). Les bibliothèques tierces gardent leurs
licences propres : voir `THIRD_PARTY.md`.

Dépôt officiel : [Nagaraaa/TikDrop](https://github.com/Nagaraaa/TikDrop).
