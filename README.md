# 🔍 SHADOW

### **Open Source Intelligence Platform for Truth Seekers**

<p align="center">
  <img src="https://img.shields.io/badge/license-MIT-blue.svg" alt="License"/>
  <img src="https://img.shields.io/badge/python-3.9+-green.svg" alt="Python"/>
  <img src="https://img.shields.io/badge/react-18+-61dafb.svg" alt="React"/>
  <img src="https://img.shields.io/badge/PRs-welcome-brightgreen.svg" alt="PRs Welcome"/>
</p>

<p align="center">
  <strong>Process FOIA releases • Monitor social media in real-time • Uncover hidden connections</strong>
</p>

---

## 🎯 What is SHADOW?

**SHADOW** is a free, open-source investigation platform for journalists, researchers, and citizens who want to:

- 📁 **Process massive document dumps** - FOIA releases, declassified files, leaked documents
- 📡 **Monitor social media in real-time** - X/Twitter, Reddit, YouTube, Bluesky, News
- 🔗 **Discover hidden connections** - AI-powered entity extraction and relationship mapping  
- 🧠 **Use AI to analyze** - Automatic classification and relevance scoring
- 🎯 **Build visual investigations** - Drag-and-drop evidence boards

---

## ✨ Features at a Glance

| Feature | Description |
|---------|-------------|
| 📡 **Real-Time Monitoring** | Track keywords across Twitter, Reddit, YouTube, Bluesky, Mastodon, News |
| 📁 **FOIA Scrapers** | Automated collection from FBI Vault, CIA, State Dept, NSArchive, MuckRock |
| 🧠 **AI Classification** | Automatic categorization: financial, legal, travel, communications |
| 👤 **Entity Extraction** | People, organizations, locations, dates, money amounts |
| 🔗 **Relationship Detection** | Find connections across thousands of documents |
| 🔍 **Semantic Search** | Find related concepts, not just keywords |
| 🎤 **Voice Control** | Hands-free operation with speech-to-text |
| 🌙 **Dark Mode** | Easy on the eyes during long investigations |

---

## 🚀 Quick Start

```bash
# Clone
git clone https://github.com/truth-seekers/shadow.git
cd shadow

# Install
python -m venv venv && source venv/bin/activate
pip install -r requirements.txt
sudo apt-get install tesseract-ocr poppler-utils  # Ubuntu/Debian

# Initialize
python shadow_backend.py init

# Optional: Add AI key for smart classification
export ANTHROPIC_API_KEY="your-key"

# Run
python shadow_backend.py server --port 5000
```

### Add Social Monitoring

```bash
# Add a query to monitor
python social_monitor.py add "FOIA Watch" 'FOIA OR declassified OR "freedom of information"'

# Start monitoring with real-time updates
python social_monitor.py run --websocket
```

### Process FOIA Documents

```bash
# Scrape FBI Vault
python foia_scraper.py scrape fbi_vault --max 1000

# Process with AI
python shadow_backend.py process ./foia_downloads/fbi_vault --source fbi_vault

# Search
python shadow_backend.py search "wire transfer offshore"
```

---

## 📁 Supported FOIA Sources

| Source | Est. Documents | Status |
|--------|----------------|--------|
| FBI Vault | 10,000+ | ✅ Ready |
| CIA FOIA Reading Room | 100,000+ | ✅ Ready |
| CIA CREST | 13,000,000+ | ✅ Ready |
| State Department | 550,000+ | ✅ Ready |
| DOE OpenNet | 150,000+ | ✅ Ready |
| National Security Archive | 200,000+ | ✅ Ready |
| MuckRock | 100,000+ | ✅ Ready |
| Internet Archive FOIA | 100,000+ | ✅ Ready |
| NARA JFK Records | 50,000+ | 🔧 Planned |

---

## 📡 Social Media Platforms

| Platform | Method | Real-Time |
|----------|--------|-----------|
| X/Twitter | API + Nitter fallback | ✅ |
| Reddit | API + JSON fallback | ✅ |
| YouTube | Official API | ✅ |
| News | NewsAPI + RSS | ✅ |
| Bluesky | Public API | ✅ |
| Mastodon | Federation API | ✅ |

---

## 🏗️ Architecture

```
SHADOW/
├── shadow_backend.py    # Core document processing & API
├── foia_scraper.py      # FOIA source scrapers
├── social_monitor.py    # Real-time social monitoring
├── vector_db.py         # Semantic search & AI linking
├── frontend/
│   └── shadow-ui.jsx    # React dashboard
├── requirements.txt     # Python dependencies
└── README.md
```

---

## 🤝 Contributing

We welcome all contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

**Ways to help:**
- 🐛 Report bugs
- 💡 Suggest features  
- 📝 Improve documentation
- 🔧 Submit pull requests
- 🌐 Add new scrapers
- 🌍 Add translations

---

## 📜 License

MIT License - Use it, modify it, share it. See [LICENSE](LICENSE).

---

## ⚠️ Responsible Use

SHADOW is for **legitimate research**. Please:
- ✅ Verify information across sources
- ✅ Respect privacy
- ✅ Provide context
- ❌ Don't harass or dox
- ❌ Don't spread unverified claims

---

## 🌟 Community

- **Discussions**: GitHub Discussions
- **Issues**: GitHub Issues
- **Wiki**: Documentation and tutorials

---

<p align="center">
  <strong>The truth is out there. Let's find it together.</strong>
</p>

<p align="center">
  Made with ❤️ by truth seekers, for truth seekers
</p>
