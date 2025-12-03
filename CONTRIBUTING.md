# Contributing to SHADOW

First off, thank you for considering contributing to SHADOW! It's people like you who make this tool valuable for truth seekers everywhere.

## 🌟 Ways to Contribute

### 🐛 Reporting Bugs

Found a bug? Please open an issue with:
- A clear title and description
- Steps to reproduce
- Expected vs actual behavior
- Your environment (OS, Python version, etc.)

### 💡 Suggesting Features

Have an idea? Open an issue with:
- Clear description of the feature
- Why it would be useful
- Possible implementation approach (optional)

### 📝 Improving Documentation

Documentation improvements are always welcome:
- Fix typos or unclear explanations
- Add tutorials or examples
- Translate to other languages

### 🔧 Submitting Code

#### First Time Setup

```bash
# Fork the repo on GitHub, then:
git clone https://github.com/YOUR_USERNAME/shadow.git
cd shadow
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt  # Dev dependencies
```

#### Making Changes

1. Create a branch:
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. Make your changes

3. Run tests:
   ```bash
   python -m pytest tests/
   ```

4. Format code:
   ```bash
   black .
   isort .
   ```

5. Commit with a clear message:
   ```bash
   git commit -m "feat: add support for new FOIA source"
   ```

6. Push and create a PR:
   ```bash
   git push origin feature/your-feature-name
   ```

### 🌐 Adding New Scrapers

We especially welcome new FOIA source scrapers! See `foia_scraper.py` for examples.

Requirements for new scrapers:
- Extend `BaseFOIAScraper` class
- Implement `discover_documents()` method
- Add to `FOIA_SOURCES` dictionary
- Add documentation

### 🎨 Frontend Contributions

The frontend uses React with Tailwind CSS. To contribute:

```bash
cd frontend
npm install
npm run dev
```

## 📋 Code Style

- **Python**: Follow PEP 8, use Black formatter
- **JavaScript/React**: Use Prettier, follow existing patterns
- **Commits**: Use conventional commits (feat:, fix:, docs:, etc.)

## 🤝 Code of Conduct

- Be respectful and inclusive
- Focus on constructive feedback
- Help newcomers learn
- Assume good intentions

## 📄 License

By contributing, you agree that your contributions will be licensed under the MIT License.

## 🙏 Thank You!

Every contribution, no matter how small, helps make SHADOW better for everyone. Thank you for being part of this community!
