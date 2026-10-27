"""NGO News Digest – the web app. Start it with:  streamlit run app.py"""
from __future__ import annotations

import hmac
import html
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import streamlit as st
import streamlit.components.v1 as components
import yaml

import news
import publish

st.set_page_config(page_title="NGO News Digest", page_icon=":material/public:", layout="wide")

HERE = Path(__file__).parent
SETTINGS_FILE = HERE / "settings.yaml"
STYLE_FILE = HERE / "style.css"
LANGUAGES = {"en": "English", "es": "Spanish"}
SORTS = ["Newest", "Longest read", "Shortest read"]
NO_THEME = "Other"
PAGE_SIZE = 30
VIEWS = {
    "browse": ":material/newspaper: Choose news",
    "newsletter": ":material/mail: Newsletter",
    "linkedin": ":material/share: LinkedIn",
}
# Streamlit forgets what you typed in a field when that field is not on screen
# (e.g. after switching to another step). Re-saving these on every run keeps them.
KEEP = ("f_", "nl_", "blurb_", "li_", "mc_")

ss = st.session_state
for _k in list(ss.keys()):
    if _k.startswith(KEEP):
        ss[_k] = ss[_k]


def ensure(key: str, default):
    """Gives a field its starting value the first time it appears."""
    if key not in ss:
        ss[key] = default


def secret(name: str) -> str | None:
    """Reads a value from Streamlit 'Secrets' (online) or an environment variable."""
    try:
        if name in st.secrets:
            return str(st.secrets[name])
    except Exception:
        pass
    return os.environ.get(name)


def esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def icon(name: str) -> str:
    return f'<span class="material-symbols-outlined" aria-hidden="true">{name}</span>'


def section(number: str, title: str, text: str = ""):
    st.html(f'<div class="section-head"><div class="marker">[{number}]</div>'
            f'<h2>{esc(title)}</h2>{f"<p>{esc(text)}</p>" if text else ""}</div>')


def empty_state(symbol: str, title: str, text: str):
    st.html(f'<div class="empty">{icon(symbol)}<h3>{esc(title)}</h3><p>{esc(text)}</p></div>')


try:
    TZ = ZoneInfo(st.context.timezone) if st.context.timezone else timezone.utc
except Exception:
    TZ = timezone.utc

if STYLE_FILE.exists():
    st.html(f"<style>{STYLE_FILE.read_text(encoding='utf-8')}</style>")


# ----------------------------------------------------------------- password
password = secret("APP_PASSWORD")
if password and not ss.get("authed"):
    _, mid, _ = st.columns([1, 1.3, 1])
    with mid:
        st.html('<div class="app-header" style="border:0"><p class="eyebrow">NGO News Digest</p>'
                '<h1>Welcome back</h1><p class="callout">Enter the app password to continue.</p></div>')
        with st.form("login", border=False):
            typed = st.text_input("Password", type="password")
            entered = st.form_submit_button("Enter", type="primary", width="stretch")
        if entered:
            if hmac.compare_digest(typed.encode(), password.encode()):
                ss.authed = True
                st.rerun()
            st.error("That password isn't right. Try again.", icon=":material/priority_high:")
    st.stop()


# ----------------------------------------------------------------- settings and data
if not SETTINGS_FILE.exists():
    st.error("**settings.yaml is missing.** Upload the `settings.yaml` file to your GitHub project "
             "(same place as app.py), then reload this page in a minute.", icon=":material/priority_high:")
    st.stop()
settings_text = SETTINGS_FILE.read_text(encoding="utf-8")
try:
    settings = yaml.safe_load(settings_text) or {}
except yaml.YAMLError as e:
    st.error("**settings.yaml has a typing mistake** (usually a missing space or a missing quote). "
             f"Check the line mentioned here:\n\n```\n{e}\n```", icon=":material/priority_high:")
    st.stop()


@st.cache_data(ttl=3 * 3600, show_spinner="Gathering the latest news from all sources. "
                                         "This takes about a minute the first time.")
def load_articles(settings_text: str):
    return news.collect_articles(yaml.safe_load(settings_text)), datetime.now(timezone.utc)


@st.cache_data(ttl=600, show_spinner=False)
def load_audiences(api_key: str):
    return publish.mailchimp_audiences(api_key)


articles, fetched_at = load_articles(settings_text)
theme_names = list(settings.get("themes", {}))

ensure("selected", {})  # id -> article, in the order they were picked
ensure("limit", PAGE_SIZE)
ensure("nav", "browse")


# ----------------------------------------------------------------- actions
def toggle(article: dict):
    if article["id"] in ss.selected:
        ss.selected.pop(article["id"])
    else:
        ss.selected[article["id"]] = article


def remove(aid: str):
    ss.selected.pop(aid, None)


def move(aid: str, step: int):
    ids = list(ss.selected)
    i = ids.index(aid)
    j = max(0, min(len(ids) - 1, i + step))
    ids[i], ids[j] = ids[j], ids[i]
    ss.selected = {k: ss.selected[k] for k in ids}


def go(view: str):
    ss.nav = view


def keep_nav():
    if ss.nav is None:  # clicking the active step again would otherwise unselect it
        ss.nav = ss.get("_nav_prev", "browse")


def keep_sort():
    if not ss.f_sort:
        ss.f_sort = "Newest"


def reset_filters():
    ss.f_days = int(settings.get("default_days", 7))
    ss.f_langs = list(LANGUAGES)
    ss.f_lengths = []
    ss.f_google = False
    ss.f_sources = []
    ss.f_search = ""
    ss.f_themes = []
    ss.f_sort = "Newest"


def reset_post(article: dict):
    blurb = ss.get(f"blurb_{article['id']}", article["excerpt"])
    ss[f"li_{article['id']}"] = publish.linkedin_post(article, settings, blurb)


def refresh():
    load_articles.clear()


# ----------------------------------------------------------------- sidebar: filters
ensure("f_days", int(settings.get("default_days", 7)))
ensure("f_langs", list(LANGUAGES))
ensure("f_lengths", [])
ensure("f_google", False)
ensure("f_sources", [])
ensure("f_search", "")
ensure("f_themes", [])
ensure("f_sort", "Newest")

with st.sidebar:
    st.html('<p class="side-title">Filters</p>')
    st.slider("Published in the last", 1, 14, key="f_days", format="%d days")
    st.segmented_control("Language", list(LANGUAGES), selection_mode="multi",
                         format_func=LANGUAGES.get, key="f_langs")
    st.pills("Reading time", news.LENGTH_BUCKETS, selection_mode="multi", key="f_lengths")
    feeds = sorted({a["feed"] for a in articles if ss.f_google or not a["is_google"]}, key=str.lower)
    ss.f_sources = [f for f in ss.f_sources if f in feeds]
    st.multiselect("Sources", feeds, key="f_sources", placeholder="All sources")
    st.toggle("Include Google News results", key="f_google",
              help="Many more articles, but noisier, and their reading time can't be measured.")
    st.button("Reset filters", icon=":material/restart_alt:", type="tertiary", on_click=reset_filters)
    st.divider()
    st.html(f'<p class="side-note">{icon("schedule")} News gathered at '
            f'{fetched_at.astimezone(TZ):%H:%M}. It refreshes by itself every 3 hours.</p>')
    st.button("Refresh news now", icon=":material/autorenew:", width="stretch", on_click=refresh)


# ----------------------------------------------------------------- filtering
if ss.f_sort not in SORTS:
    ss.f_sort = "Newest"
if ss.nav not in VIEWS:
    ss.nav = ss.get("_nav_prev", "browse")
cutoff = datetime.now(timezone.utc) - timedelta(days=ss.f_days)
query = news.normalize(ss.f_search.strip())
langs = ss.f_langs or list(LANGUAGES)


def keep(a: dict) -> bool:
    if a["published"] and a["published"] < cutoff:
        return False
    if a["language"] not in langs or (a["is_google"] and not ss.f_google):
        return False
    if ss.f_themes and not (set(a["themes"]) & set(ss.f_themes)
                            or (NO_THEME in ss.f_themes and not a["themes"])):
        return False
    if ss.f_lengths and a["length"] not in ss.f_lengths:
        return False
    if ss.f_sources and a["feed"] not in ss.f_sources:
        return False
    if query and query not in news.normalize(f"{a['title']} {a['excerpt']} {a['source']}"):
        return False
    return True


shown = [a for a in articles if keep(a)]
if ss.f_sort == "Longest read":
    shown.sort(key=lambda a: a["minutes"] or -1, reverse=True)
elif ss.f_sort == "Shortest read":
    shown.sort(key=lambda a: a["minutes"] or 10 ** 6)

signature = (ss.f_days, tuple(langs), tuple(ss.f_lengths), ss.f_google, tuple(ss.f_sources),
             query, tuple(ss.f_themes), ss.f_sort)
if ss.get("_signature") != signature:
    ss._signature = signature
    ss.limit = PAGE_SIZE

selected = list(ss.selected.values())
active_sources = len({a["feed"] for a in articles if ss.f_google or not a["is_google"]})


# ----------------------------------------------------------------- header + steps
PIXELS = ["ooomyggy", "oooomygm", "oooooomy"]
pixel_html = "".join(f'<i class="{c}"></i>' for row in PIXELS for c in row)
st.html(f"""
<div class="app-header">
  <div class="pixel-grid" aria-hidden="true">{pixel_html}</div>
  <p class="eyebrow">NGO News Digest</p>
  <h1>The NGO world, this week</h1>
  <p class="callout">News from {active_sources} sources in English and Spanish. Pick the stories
  worth sharing, then turn them into a newsletter or LinkedIn posts.</p>
  <div class="stats">
    <div class="stat"><div class="num">{len(shown)}</div><div class="lbl-txt">Articles match</div></div>
    <div class="stat"><div class="num">{active_sources}</div><div class="lbl-txt">Sources</div></div>
    <div class="stat{' hl' if selected else ''}"><div class="num">{len(selected)}</div><div class="lbl-txt">Selected</div></div>
  </div>
</div>""")


# Labels must never change (e.g. with a count in them): Streamlit would treat the
# control as a new one and forget which step is open.
st.segmented_control("Step", list(VIEWS), format_func=VIEWS.get, key="nav",
                     on_change=keep_nav, label_visibility="collapsed")
view = ss.nav or "browse"
ss._nav_prev = view


# ----------------------------------------------------------------- [01] browse
def article_card(a: dict):
    on = a["id"] in ss.selected
    with st.container(key=f"card-{'on' if on else 'off'}-{a['id']}"):
        body, side = st.columns([4, 1.25], gap="medium")
        with body:
            tags = [f'<span class="tag lang">{a["language"].upper()}</span>']
            if on:
                tags.append('<span class="tag accent">Selected</span>')
            tags += [f'<span class="tag">{esc(t)}</span>' for t in a["themes"]]
            meta = [f'<span>{icon("public")} {esc(a["source"])}</span>']
            if a["published"]:
                meta.append(f'<span>{icon("calendar_today")} {a["published"].astimezone(TZ):%d %b %Y, %H:%M}</span>')
            meta.append(f'<span>{icon("timer")} '
                        f'{str(a["minutes"]) + " min read" if a["minutes"] else "Reading time unknown"}</span>')
            also = (f'<p class="also">Also covered by {esc(", ".join(a["also_in"]))}</p>'
                    if a.get("also_in") else "")
            st.html(f"""
<div class="tags">{''.join(tags)}</div>
<p class="card-title"><a href="{esc(a['link'])}" target="_blank" rel="noopener noreferrer">{esc(a['title'])}</a></p>
<div class="meta">{''.join(meta)}</div>
{f'<p class="excerpt">{esc(a["excerpt"])}</p>' if a['excerpt'] else ''}
{also}""")
        with side:
            if a["image"]:
                st.html(f'<img class="thumb" src="{esc(a["image"])}" alt="" loading="lazy" referrerpolicy="no-referrer">')
            st.button("Added" if on else "Add", key=f"add-{a['id']}",
                      icon=":material/check:" if on else ":material/add:",
                      help="Click to remove it from your selection" if on
                      else "Add to your newsletter and LinkedIn selection",
                      on_click=toggle, args=(a,), width="stretch")


if view == "browse":
    section("01", "Choose news", "Add the stories worth sharing. They'll be ready in the Newsletter and LinkedIn steps.")
    c1, c2 = st.columns([3, 2], vertical_alignment="center")
    c1.text_input("Search", key="f_search", icon=":material/search:", label_visibility="collapsed",
                  placeholder="Search titles and summaries, e.g. Sudan, voluntariado")
    c2.segmented_control("Sort by", SORTS, key="f_sort", on_change=keep_sort, label_visibility="collapsed")
    st.pills("Themes", theme_names + [NO_THEME], selection_mode="multi", key="f_themes",
             label_visibility="collapsed")

    if not shown:
        empty_state("search_off", "No articles match these filters",
                    "Try fewer themes, a longer period, or Reset filters in the left panel.")
        st.button("Reset filters", icon=":material/restart_alt:", on_click=reset_filters, key="reset-main")
    else:
        st.html(f'<p class="hint">Showing {min(ss.limit, len(shown))} of {len(shown)} articles, '
                f'{ss.f_sort.lower()} first.</p>')
        for a in shown[: ss.limit]:
            article_card(a)
        if len(shown) > ss.limit:
            _, mid, _ = st.columns([1, 1, 1])
            if mid.button(f"Show more ({len(shown) - ss.limit} left)", icon=":material/expand_more:",
                          width="stretch"):
                ss.limit += PAGE_SIZE
                st.rerun()

    if selected:
        with st.container(key="tray", horizontal=True, vertical_alignment="center", gap="medium"):
            st.markdown(f"{len(selected)} selected")
            st.button("Continue to newsletter", key="tray-go", icon=":material/keyboard_double_arrow_right:",
                      on_click=go, args=("newsletter",))


# ----------------------------------------------------------------- [02] newsletter
elif view == "newsletter":
    section("02", "Build your newsletter",
            "Check the order and wording, look at the preview, then send it to Mailchimp as a draft.")
    if not selected:
        empty_state("mail", "No articles selected yet", "Go to Choose news and press Add on the stories you want.")
        st.button("Choose news", type="primary", icon=":material/newspaper:", on_click=go, args=("browse",))
    else:
        cfg = settings.get("newsletter", {})
        ensure("nl_subject", f"{cfg.get('name', 'NGO News Digest')} – {datetime.now(TZ):%d %B %Y}")
        ensure("nl_preview", cfg.get("tagline", ""))
        ensure("nl_intro", "")
        ensure("nl_group", False)

        left, right = st.columns([1, 1.1], gap="large")
        with left:
            with st.container(key="panel-details"):
                st.html('<p class="panel-title">Details</p>')
                st.text_input("Email subject", key="nl_subject")
                st.text_input("Preview text", key="nl_preview",
                              help="The grey line shown after the subject in the inbox.")
                st.text_area("Intro (optional)", key="nl_intro", height=100,
                             placeholder="A few words from you at the top of the email")
                st.toggle("Group articles by theme", key="nl_group")

            with st.container(key="panel-articles"):
                st.html(f'<p class="panel-title">Articles ({len(selected)})</p>'
                        '<p class="hint">Change the order, and rewrite the short text if you want.</p>')
                for i, a in enumerate(selected):
                    ensure(f"blurb_{a['id']}", a["excerpt"])
                    with st.container(key=f"nlitem-{a['id']}"):
                        st.html(f'<p style="margin:0;font-weight:600">{i + 1}. {esc(a["title"])}</p>'
                                f'<p class="hint" style="margin:2px 0 0">{esc(a["source"])}</p>')
                        st.text_area("Short text", key=f"blurb_{a['id']}", label_visibility="collapsed", height=96)
                        with st.container(horizontal=True, gap="small"):
                            st.button("Up", key=f"up-{a['id']}", icon=":material/arrow_upward:", type="tertiary",
                                      on_click=move, args=(a["id"], -1), disabled=i == 0)
                            st.button("Down", key=f"down-{a['id']}", icon=":material/arrow_downward:",
                                      type="tertiary", on_click=move, args=(a["id"], 1),
                                      disabled=i == len(selected) - 1)
                            st.button("Remove", key=f"rm-{a['id']}", icon=":material/close:", type="tertiary",
                                      on_click=remove, args=(a["id"],))

        blurbs = {a["id"]: ss.get(f"blurb_{a['id']}", a["excerpt"]) for a in selected}
        html_out = publish.build_newsletter_html(selected, blurbs, settings, ss.nl_intro, ss.nl_group)

        with right:
            st.html('<p class="panel-title">Preview</p><p class="hint">This is how the email will look.</p>')
            components.html(html_out, height=720, scrolling=True)

            with st.container(key="panel-send"):
                st.html('<p class="panel-title">Send</p>')
                api_key = secret("MAILCHIMP_API_KEY")
                if not api_key:
                    st.info("Mailchimp isn't connected yet. Add your **MAILCHIMP_API_KEY** in the app's Secrets "
                            "(SETUP.md, step 4). Meanwhile you can download the email and paste it into a "
                            "Mailchimp 'Code your own' template.", icon=":material/link_off:")
                else:
                    try:
                        audiences = load_audiences(api_key)
                    except Exception as e:
                        audiences = []
                        st.error(f"Couldn't connect to Mailchimp. {e}", icon=":material/priority_high:")
                    if audiences:
                        by_id = {x["id"]: x for x in audiences}
                        ensure("mc_audience", audiences[0]["id"])
                        if ss.mc_audience not in by_id:
                            ss.mc_audience = audiences[0]["id"]
                        st.selectbox("Audience (who will receive it)", list(by_id), key="mc_audience",
                                     format_func=lambda i: f"{by_id[i]['name']} "
                                                           f"({by_id[i]['stats']['member_count']} contacts)")
                        defaults = by_id[ss.mc_audience].get("campaign_defaults", {})
                        ensure("mc_from", defaults.get("from_name", ""))
                        ensure("mc_reply", defaults.get("from_email", ""))
                        c1, c2 = st.columns(2)
                        c1.text_input("From name", key="mc_from")
                        c2.text_input("Reply-to email", key="mc_reply")
                        st.html('<p class="hint">This creates a draft only. Nothing is sent until you press '
                                'Send inside Mailchimp.</p>')
                        if st.button("Create Mailchimp draft", type="primary", icon=":material/send:",
                                     width="stretch"):
                            problems = []
                            if not ss.nl_subject.strip():
                                problems.append("add an email subject")
                            if not ss.mc_from.strip():
                                problems.append("add a From name")
                            if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", ss.mc_reply.strip()):
                                problems.append("enter a valid reply-to email")
                            if problems:
                                st.error("Before creating the draft, please " + ", ".join(problems) + ".",
                                         icon=":material/priority_high:")
                            else:
                                try:
                                    with st.spinner("Creating the draft in Mailchimp…"):
                                        ss._draft_url = publish.create_mailchimp_draft(
                                            api_key, ss.mc_audience, ss.nl_subject.strip(), ss.nl_preview.strip(),
                                            ss.mc_from.strip(), ss.mc_reply.strip(), html_out)
                                except Exception as e:
                                    st.error(str(e), icon=":material/priority_high:")
                        if ss.get("_draft_url"):
                            st.success("Your draft is waiting in Mailchimp.", icon=":material/check:")
                            st.link_button("Open the draft in Mailchimp", ss._draft_url,
                                           icon=":material/north_east:", width="stretch")
                st.download_button("Download the email (HTML)", html_out, icon=":material/download:",
                                   file_name=f"newsletter-{datetime.now(TZ):%Y-%m-%d}.html",
                                   mime="text/html", width="stretch")


# ----------------------------------------------------------------- [03] LinkedIn
elif view == "linkedin":
    section("03", "Share on LinkedIn", "One ready-to-edit post per article, in the article's language.")
    if not selected:
        empty_state("share", "No articles selected yet", "Go to Choose news and press Add on the stories you want.")
        st.button("Choose news", type="primary", icon=":material/newspaper:", on_click=go, args=("browse",))
    else:
        st.html('<div class="steps">'
                '<div class="step"><span class="n">1</span><div class="t">Edit the text on the left if you want.</div></div>'
                '<div class="step"><span class="n">2</span><div class="t">Copy it with the copy icon on the right-hand box.</div></div>'
                '<div class="step"><span class="n">3</span><div class="t">Open LinkedIn, paste the text and publish.</div></div>'
                '</div>')
        for a in selected:
            ensure(f"li_{a['id']}", publish.linkedin_post(a, settings, ss.get(f"blurb_{a['id']}", a["excerpt"])))
            with st.container(key=f"panel-li-{a['id']}"):
                st.html(f'<div class="tags"><span class="tag lang">{a["language"].upper()}</span>'
                        + "".join(f'<span class="tag">{esc(t)}</span>' for t in a["themes"][:3]) + '</div>'
                        f'<p class="card-title"><a href="{esc(a["link"])}" target="_blank" rel="noopener noreferrer">'
                        f'{esc(a["title"])}</a></p><div class="meta"><span>{icon("public")} {esc(a["source"])}</span></div>')
                edit, ready = st.columns(2, gap="large")
                with edit:
                    post = st.text_area("Post text", key=f"li_{a['id']}", height=280)
                    over = len(post) > 3000
                    st.html(f'<span class="{"count-over" if over else "count-ok"}">{len(post)} / 3000 characters'
                            f'{" · too long for LinkedIn" if over else ""}</span>')
                    st.button("Reset text", key=f"reset-{a['id']}", icon=":material/restart_alt:", type="tertiary",
                              on_click=reset_post, args=(a,))
                with ready:
                    st.html('<p class="hint" style="margin:0 0 6px">Ready to copy</p>')
                    st.code(post, language=None, wrap_lines=True)
                    st.link_button("Open LinkedIn", publish.linkedin_share_url(a["link"]),
                                   icon=":material/north_east:", width="stretch")
