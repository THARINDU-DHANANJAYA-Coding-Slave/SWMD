### 🧩 SWMD — Steam Workshop Mod Downloader

**SWMD** is a powerful Python-based tool that automatically downloads mods and collections from the **Steam Workshop** using just a **collection or item URL**.
Perfect for gamers, server hosts, and modpack creators who want to save time manually managing Workshop mods.

#### 🚀 Features

* 🔗 **Automatic download** from Workshop **collection URLs** or **single mod links**
* 📦 **Batch download** all mods in a collection
* 💾 Saves files directly to a chosen folder (ready for use or upload)
* ⚙️ Supports **SteamCMD integration** for faster, official downloads
* 🧠 Smart parsing to handle mixed links or invalid entries
* 🪶 Lightweight, portable, and easy to run — no installation required

#### 🖥️ Usage

```bash
python swmd.py
```

Then simply enter your **Steam Workshop collection URL** or **mod link**, and SWMD handles the rest!

#### 📜 Requirements

* Python 3.8+
* `requests`
* `beautifulsoup4`
* (optional) `steamcmd` for official downloads

#### 💡 Example

```
https://steamcommunity.com/sharedfiles/filedetails/?id=123456789
https://steamcommunity.com/workshop/filedetails/?id=987654321
```
