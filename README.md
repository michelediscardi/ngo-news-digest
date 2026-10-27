# 📰 NGO News Digest

Collects the latest NGO-sector news in English and Spanish, filters it by theme and length, and turns your picks into a Mailchimp newsletter draft or LinkedIn posts.

- **What it does and why:** see [BRIEF.md](BRIEF.md)
- **How to put it online (step by step):** see [SETUP.md](SETUP.md)
- **Change sources, themes or newsletter name:** edit [settings.yaml](settings.yaml)

| File | What it is |
|---|---|
| `app.py` | The app's screens (filters, tabs, buttons) |
| `news.py` | Reads the news sources, tags themes, measures length |
| `publish.py` | Builds the newsletter email, talks to Mailchimp, prepares LinkedIn posts |
| `settings.yaml` | Your editable settings |
| `style.css` | The app's visual details (El Cami design system) |
| `theme.py` | Applies the El Cami colours and font, always in light mode |
| `assets/` | The El Cami logo |
| `.streamlit/config.toml` | The same theme as a settings file (optional) |
| `requirements.txt` | The list of free building blocks the app needs |
