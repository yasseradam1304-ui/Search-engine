# Adogle

Adogle recherche sur le Web depuis la barre centrale ou la barre d’adresse. Les
résultats sont présentés dans l’application ; les pages Web s’ouvrent dans le
navigateur intégré.

## Fonctions

- **Moteurs :** Google, Brave, DuckDuckGo, Bing, Ecosia, Qwant, Yahoo et
  Startpage.
- **Images :** recherche dans Wikimedia Commons. Les cartes indiquent le
  créateur et la licence lorsque ces informations sont disponibles.
- **Historique :** recherches récentes conservées localement sur l’appareil.
- **Langue :** filtre de langue et de région transmis au moteur choisi.
- **Thèmes :** contraste élevé, sombre et clair.
- **Assistant IA :** résumé et questions sur les résultats avec Ollama sur votre
  ordinateur. Adogle n’envoie pas ces requêtes IA à un fournisseur distant.

Firefox et Opera sont des navigateurs, pas des moteurs de recherche distincts.
Adogle propose donc des moteurs réels plutôt que des options en double qui
renverraient aux mêmes résultats.

## Installation et lancement

Python 3.10+ :

```powershell
python -m pip install -r requirements.txt
python "Python code.py"
```

### Créer l’application Windows (.exe)

Installez PyInstaller, puis lancez le script de génération depuis PowerShell :

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

Le fichier autonome est créé dans `dist\Adogle.exe`. Il inclut Python, les
dépendances et l’interface de l’application ; Python n’est pas requis sur le
PC qui l’exécute. Le premier démarrage peut prendre quelques secondes.

Les recherches Web sont transmises au moteur sélectionné. Les images sont
recherchées sur Wikimedia Commons. L’historique et les préférences sont stockés
localement avec QSettings. Certains moteurs peuvent modifier leur page ou
présenter un CAPTCHA ; Adogle réessaie l’extraction puis permet de relancer la
recherche ou de choisir un autre moteur.

### Assistant IA local

Installez Ollama, puis téléchargez un modèle :

```powershell
ollama pull qwen2.5:3b
```

Lancez Ollama et vérifiez le modèle dans **Paramètres → Détecter mes modèles**.
L’IA utilise l’API locale `http://127.0.0.1:11434` et fonde ses réponses sur les
extraits de la recherche. Sans Ollama, les autres fonctions de recherche
continuent de fonctionner.

## Tests

```powershell
python -m unittest discover -v
```
