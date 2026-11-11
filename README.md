# Adogle

Adogle lets you search the web from the central search bar or the address bar.
Results appear in the app, and web pages open in the built-in browser.

## Features

- **Search engines:** Google, Brave, DuckDuckGo, Bing, Ecosia, Qwant, Yahoo,
  and Startpage.
- **Images:** Search Wikimedia Commons. Cards show the creator and license
  when that information is available.
- **History:** Recent searches are stored locally on your device.
- **Language:** A language and region filter is sent to the selected search
  engine.
- **Themes:** High contrast, dark, and light.
- **AI assistant:** Summarize and ask questions about search results using
  Ollama on your computer. Adogle does not send AI requests to a remote
  provider.

Firefox and Opera are browsers, not separate search engines. Adogle therefore
offers actual search engines rather than duplicate options that would return
the same results.

## Installation and launch

Python 3.10+:

```powershell
python -m pip install -r requirements.txt
python "Python code.py"
```

### Build the Windows app (.exe)

Install PyInstaller, then run the build script from PowerShell:

```powershell
python -m pip install pyinstaller
.\build_exe.ps1
```

The standalone executable is created at `dist\Adogle.exe`. It bundles Python,
the dependencies, and the app interface; Python is not required on the
computer running it. The first launch may take a few seconds.

Web searches are sent to the selected search engine. Images are searched on
Wikimedia Commons. Search history and preferences are stored locally using
QSettings. Some search engines may change their pages or show a CAPTCHA;
Adogle retries extraction and lets you retry the search or choose another
engine.

### Local AI assistant

Install Ollama, then download a model:

```powershell
ollama pull qwen2.5:3b
```

Start Ollama and check for the model under **Settings → Detect my models**.
The AI uses the local API at `http://127.0.0.1:11434` and bases its answers on
search snippets. Without Ollama, the other search features continue to work.

## Tests

```powershell
python -m unittest discover -v
```
