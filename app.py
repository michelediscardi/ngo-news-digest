"""NGO News Digest – the web app. Start it with:  streamlit run app.py"""
from __future__ import annotations

import hmac
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components
import yaml

import news
import publish

st.set_page_config(page_title="NGO News Digest", page_icon="📰", layout="wide")

SETTINGS_FILE = Path(__file__).with_name("settings.yaml")
LANGUAGES = {"en": "English", "es": "Spanish"}
PAGE_SIZE = 30


def secret(name: str) -> str | None:
    """Reads a value from Streamlit 'Secrets' (online) or an environment variable."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name)


def md(text: str) -> str:
    """Stops titles with * _ [ ] from being read as formatting."""
    return re.sub(r"([\\`*_\[\]#<>|~$])", r"\\\1", text)


# ----------------------------------------------------------------- password
password = secret("APP_PASSWORD")
if password and not st.session_state.get("authed"):
    st.title("📰 NGO News Digest")
    typed = st.text_input("Password", type="password")
    if typed:
        if hmac.compare_digest(typed, password):
            st.session_state.authed = True
            st.rerun()
        st.error("Wrong password.")
    st.stop()


# ----------------------------------------------------------------- data
settings_text = SETTINGS_FILE.read_text(encoding="utf-8")
settings = yaml.safe_load(settings_text)


@st.cache_data(ttl=3 * 3600, show_spinner="Gathering the latest news… (about a minute the first time)")
def load_articles(settings_text: str):
    return news.collect_articles(yaml.safe_load(settings_text)), datetime.now(timezone.utc)


@st.cache_data(ttl=600, show_spinner=False)
def load_audiences(api_key: str):
    return publish.mailchimp_audiences(api_key)


articles, fetched_at = load_articles(settings_text)

ss = st.session_state
ss.setdefault("selected", {})  # id -> article, kept in the order they were picked
ss.setdefault("limit", PAGE_SIZE)


def toggle(article: dict):
    if ss[f"sel_{article['id']}"]:
        ss.selected[article["id"]] = article
    else:
        ss.selected.pop(article["id"], None)


def remove(aid: str):
    ss.selected.pop(aid, None)
    ss.pop(f"sel_{aid}", None)


def move(aid: str, step: int):
    ids = list(ss.selected)
    i = ids.index(aid)
    j = max(0, min(len(ids) - 1, i + step))
    ids[i], ids[j] = ids[j], ids[i]
    ss.selected = {k: ss.selected[k] for k in ids}


# ----------------------------------------------------------------- sidebar filters
with st.sidebar:
    st.header("🔎 Filters")
    days = st.slider("Published in the last … days", 1, 14, int(settings.get("default_days", 7)))
    langs = st.multiselect("Language", list(LANGUAGES), default=list(LANGUAGES), format_func=LANGUAGES.get)
    theme_names = list(settings.get("themes", {})) + ["No theme"]
    themes = st.multiselect("Theme", theme_names, placeholder="All themes")
    lengths = st.multiselect("Length", news.LENGTH_BUCKETS, placeholder="Any length")
    use_google = st.toggle("Include Google News results", value=False,
                           help="Many more articles, but noisier, and their length can't be measured.")
    feeds = sorted({a["feed"] for a in articles if use_google or not a["is_google"]})
    chosen_feeds = st.multiselect("Source", feeds, placeholder="All sources")
    search = st.text_input("Search words", placeholder="e.g. Sudan, voluntariado…")

    st.divider()
    st.caption(f"News gathered at {fetched_at.astimezone():%H:%M} · refreshed every 3 hours")
    if st.button("🔄 Get fresh news now", width="stretch"):
        load_articles.clear()
        st.rerun()

cutoff = datetime.now(timezone.utc) - timedelta(days=days)
query = news.normalize(search.strip())


def keep(a: dict) -> bool:
    if a["published"] and a["published"] < cutoff:
        return False
    if a["language"] not in langs or (a["is_google"] and not use_google):
        return False
    if themes and not (set(a["themes"]) & set(themes) or ("No theme" in themes and not a["themes"])):
        return False
    if lengths and a["length"] not in lengths:
        return False
    if chosen_feeds and a["feed"] not in chosen_feeds:
        return False
    if query and query not in news.normalize(f"{a['title']} {a['excerpt']} {a['source']}"):
        return False
    return True


shown = [a for a in articles if keep(a)]
selected = list(ss.selected.values())

st.title("📰 NGO News Digest")
tab_browse, tab_news, tab_li = st.tabs([
    f"📰 Browse news ({len(shown)})",
    f"✉️ Newsletter ({len(selected)} selected)",
    "💼 LinkedIn posts",
])

# ----------------------------------------------------------------- tab 1: browse
with tab_browse:
    st.caption("Tick **Select** on the articles you like. They'll appear in the Newsletter and LinkedIn tabs.")
    if not shown:
        st.info("No articles match these filters. Try removing some filters in the left panel.")
    for a in shown[: ss.limit]:
        with st.container(border=True):
            left, right = st.columns([5, 1])
            with left:
                st.markdown(f"##### [{md(a['title'])}](<{a['link']}>)")
                meta = [md(a["source"])]
                if a["published"]:
                    meta.append(a["published"].astimezone().strftime("%d %b %Y, %H:%M"))
                meta.append(f"{a['minutes']} min read" if a["minutes"] else "length unknown")
                badges = [f":gray-badge[{a['language'].upper()}]"] + [f":green-badge[{md(t)}]" for t in a["themes"]]
                st.markdown(" · ".join(meta) + "  \n" + " ".join(badges))
                if a["excerpt"]:
                    st.write(a["excerpt"])
            with right:
                if a["image"]:
                    st.image(a["image"], width="stretch")
                st.checkbox("Select", key=f"sel_{a['id']}", value=a["id"] in ss.selected,
                            on_change=toggle, args=(a,))
    if len(shown) > ss.limit:
        if st.button(f"Show more ({len(shown) - ss.limit} remaining)"):
            ss.limit += PAGE_SIZE
            st.rerun()

# ----------------------------------------------------------------- tab 2: newsletter
with tab_news:
    if not selected:
        st.info("No articles selected yet. Go to **Browse news** and tick **Select** on the ones you want.")
    else:
        cfg = settings.get("newsletter", {})
        c1, c2 = st.columns(2)
        subject = c1.text_input("Email subject", f"{cfg.get('name', 'NGO News Digest')} – {datetime.now():%d %B %Y}")
        preview_text = c2.text_input("Preview text (the grey line shown after the subject in the inbox)",
                                     cfg.get("tagline", ""))
        intro = st.text_area("Intro (optional, a few words from you at the top of the email)", height=100)
        group = st.checkbox("Group articles by theme")

        st.subheader("Articles in this newsletter")
        st.caption("Change the order with ⬆️ ⬇️, and rewrite each short text if you want.")
        blurbs = {}
        ids = list(ss.selected)
        for i, a in enumerate(selected):
            with st.container(border=True):
                t, b1, b2, b3 = st.columns([12, 1, 1, 1])
                t.markdown(f"**{i + 1}. {md(a['title'])}**  \n{md(a['source'])}")
                b1.button("⬆️", key=f"up_{a['id']}", on_click=move, args=(a["id"], -1), disabled=i == 0)
                b2.button("⬇️", key=f"down_{a['id']}", on_click=move, args=(a["id"], 1), disabled=i == len(ids) - 1)
                b3.button("✕", key=f"rm_{a['id']}", on_click=remove, args=(a["id"],), help="Remove")
                blurbs[a["id"]] = st.text_area("Short text", a["excerpt"], key=f"blurb_{a['id']}",
                                               label_visibility="collapsed", height=90)

        html_out = publish.build_newsletter_html(selected, blurbs, settings, intro, group)

        st.subheader("Preview")
        components.html(html_out, height=700, scrolling=True)

        st.subheader("Send to Mailchimp")
        api_key = secret("MAILCHIMP_API_KEY")
        if not api_key:
            st.warning("Mailchimp isn't connected yet. Add your **MAILCHIMP_API_KEY** in the app's Secrets "
                       "(see SETUP.md, step 5). Meanwhile you can download the HTML and paste it into a "
                       "Mailchimp 'Code your own' template.")
        else:
            try:
                audiences = load_audiences(api_key)
            except Exception as e:
                audiences = []
                st.error(f"Couldn't connect to Mailchimp. {e}")
            if audiences:
                aud = st.selectbox("Audience (who will receive it)", audiences,
                                   format_func=lambda x: f"{x['name']} ({x['stats']['member_count']} contacts)")
                defaults = aud.get("campaign_defaults", {})
                c1, c2 = st.columns(2)
                from_name = c1.text_input("From name", defaults.get("from_name", ""))
                reply_to = c2.text_input("Reply-to email", defaults.get("from_email", ""))
                st.caption("This creates a **draft** only. Nothing is sent until you press Send inside Mailchimp.")
                if st.button("📨 Create Mailchimp draft", type="primary"):
                    if not (subject and from_name and reply_to):
                        st.error("Please fill in subject, From name and Reply-to email.")
                    else:
                        try:
                            with st.spinner("Creating the draft…"):
                                url = publish.create_mailchimp_draft(api_key, aud["id"], subject, preview_text,
                                                                     from_name, reply_to, html_out)
                            st.success("Done! Your draft is waiting in Mailchimp.")
                            st.link_button("Open the draft in Mailchimp ↗", url)
                        except Exception as e:
                            st.error(str(e))

        st.download_button("⬇️ Download newsletter HTML", html_out,
                           file_name=f"newsletter-{datetime.now():%Y-%m-%d}.html", mime="text/html")

# ----------------------------------------------------------------- tab 3: LinkedIn
with tab_li:
    if not selected:
        st.info("No articles selected yet. Go to **Browse news** and tick **Select** on the ones you want.")
    else:
        st.markdown("**How to post:** 1) edit the text if you like, 2) click the 📋 icon on the grey box to copy it, "
                    "3) click **Open LinkedIn**, 4) paste the text into the post and publish.")
        for a in selected:
            with st.container(border=True):
                st.markdown(f"**{md(a['title'])}** · {md(a['source'])}")
                blurb = ss.get(f"blurb_{a['id']}", a["excerpt"])
                post = st.text_area("Post text", publish.linkedin_post(a, settings, blurb),
                                    key=f"li_{a['id']}", height=220)
                over = len(post) > 3000
                st.caption(f"{len(post)} / 3000 characters" + (" — too long for LinkedIn!" if over else ""))
                st.code(post, language=None, wrap_lines=True)
                st.link_button("Open LinkedIn ↗", publish.linkedin_share_url(a["link"]))
