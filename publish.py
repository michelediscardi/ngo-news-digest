"""Turns selected articles into a newsletter (HTML + Mailchimp draft)
and into LinkedIn posts."""
from __future__ import annotations

import html
import re
from datetime import datetime
from urllib.parse import quote

import requests

FONT = "Inter,'Helvetica Neue',Helvetica,Arial,sans-serif"
INK, MUTED, LINE, PAPER, MIST = "#000000", "#4d4d4d", "#808080", "#eeeeee", "#d6e2e2"


def _esc(text) -> str:
    return html.escape(str(text or ""), quote=True)


def _label(text: str, bg: str) -> str:
    return (f'<span style="display:inline-block;background:{bg};color:{INK};font-family:{FONT};font-size:11px;'
            f'font-weight:500;letter-spacing:.04em;text-transform:uppercase;padding:3px 7px;'
            f'margin:0 4px 4px 0;">{_esc(text)}</span>')


# ----------------------------------------------------------------- newsletter
def _article_block(a: dict, blurb: str, green: str, highlight: str) -> str:
    meta = [_esc(a["source"])]
    if a.get("published"):
        meta.append(a["published"].strftime("%d %b %Y"))
    if a.get("minutes"):
        meta.append(f"{a['minutes']} min read")
    labels = "".join(_label(t, MIST) for t in a.get("themes", [])[:2])
    link = _esc(a["link"])
    image = (
        f'<a href="{link}"><img src="{_esc(a["image"])}" width="536" alt="" '
        f'style="width:100%;max-width:536px;height:auto;display:block;border:0;margin:0 0 16px;"></a>'
        if a.get("image") else ""
    )
    more = "Leer más" if a["language"] == "es" else "Read more"
    return f"""
<tr><td style="padding:28px 32px;border-bottom:1px solid {LINE};">
  {image}
  {f'<div style="margin:0 0 8px;">{labels}</div>' if labels else ''}
  <h2 style="margin:0 0 8px;font-family:{FONT};font-size:20px;line-height:1.3;font-weight:600;">
    <a href="{link}" style="color:{green};text-decoration:none;">{_esc(a['title'])}</a>
  </h2>
  <p style="margin:0 0 12px;font-family:{FONT};font-size:13px;line-height:1.4;color:{MUTED};">{' &middot; '.join(meta)}</p>
  {f'<p style="margin:0 0 16px;font-family:{FONT};font-size:16px;line-height:1.5;color:{INK};">{_esc(blurb)}</p>' if blurb else ''}
  <a href="{link}" style="font-family:{FONT};font-size:14px;font-weight:600;color:{green};text-decoration:underline;">{more} &rarr;</a>
</td></tr>"""


def build_newsletter_html(articles: list[dict], blurbs: dict[str, str], settings: dict,
                          intro: str = "", group_by_theme: bool = False,
                          for_mailchimp: bool = True) -> str:
    cfg = settings.get("newsletter", {})
    green = cfg.get("accent_color", "#0a523a")
    highlight = cfg.get("highlight_color", "#e9ff5e")
    name = _esc(cfg.get("name", "NGO News Digest"))
    tagline = _esc(cfg.get("tagline", ""))

    rows = []
    if group_by_theme:
        groups: dict[str, list[dict]] = {}
        for a in articles:
            groups.setdefault(a["themes"][0] if a.get("themes") else "More news", []).append(a)
        for n, (theme, items) in enumerate(groups.items(), 1):
            rows.append(f'<tr><td style="padding:32px 32px 0;"><p style="margin:0;font-family:{FONT};font-size:12px;'
                        f'font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:{INK};">'
                        f'[{n:02d}] {_esc(theme)}</p></td></tr>')
            rows += [_article_block(a, blurbs.get(a["id"], a["excerpt"]), green, highlight) for a in items]
    else:
        rows = [_article_block(a, blurbs.get(a["id"], a["excerpt"]), green, highlight) for a in articles]

    intro_html = "".join(
        f'<p style="margin:0 0 12px;font-family:{FONT};font-size:18px;font-weight:300;line-height:1.5;color:{INK};">'
        f'{_esc(p)}</p>'
        for p in intro.split("\n") if p.strip()
    )
    # Mailchimp fills in these *|...|* tags: unsubscribe link and your address (required by law)
    footer = (
        f'<a href="*|UNSUB|*" style="color:{MUTED};">Unsubscribe</a> &middot; '
        f'<a href="*|UPDATE_PROFILE|*" style="color:{MUTED};">Update preferences</a><br>*|LIST:ADDRESSLINE|*'
        if for_mailchimp else "You received this email because you subscribed to our newsletter."
    )
    date = datetime.now().strftime("%d %B %Y")
    count = len(articles)

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<title>{name}</title></head>
<body style="margin:0;padding:0;background:{PAPER};">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:{PAPER};">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border:1px solid {LINE};">
  <tr><td style="background:{green};padding:32px;">
    <p style="margin:0 0 12px;font-family:{FONT};font-size:12px;font-weight:500;letter-spacing:.04em;text-transform:uppercase;color:#ffffff;">{date} &middot; {count} {'story' if count == 1 else 'stories'}</p>
    <p style="margin:0;font-family:{FONT};font-size:32px;line-height:1.1;font-weight:600;color:#ffffff;">{name}</p>
    {f'<p style="margin:10px 0 0;font-family:{FONT};font-size:16px;line-height:1.4;font-weight:300;color:#ffffff;">{tagline}</p>' if tagline else ''}
  </td></tr>
  <tr><td style="background:{highlight};height:8px;line-height:8px;font-size:0;">&nbsp;</td></tr>
  {f'<tr><td style="padding:32px 32px 8px;">{intro_html}</td></tr>' if intro_html else ''}
  {''.join(rows)}
  <tr><td style="padding:24px 32px;font-family:{FONT};font-size:12px;line-height:1.6;color:{MUTED};text-align:center;">{footer}</td></tr>
</table>
</td></tr></table>
</body></html>"""


# ----------------------------------------------------------------- Mailchimp
class MailchimpError(Exception):
    pass


def _mc(api_key: str, method: str, path: str, **kwargs) -> dict:
    if "-" not in api_key:
        raise MailchimpError("The Mailchimp API key looks wrong: it should end with something like '-us21'.")
    dc = api_key.rsplit("-", 1)[1]
    resp = requests.request(method, f"https://{dc}.api.mailchimp.com/3.0{path}",
                            auth=("anystring", api_key), timeout=30, **kwargs)
    if not resp.ok:
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise MailchimpError(f"Mailchimp said: {detail}")
    return resp.json() if resp.content else {}


def mailchimp_audiences(api_key: str) -> list[dict]:
    data = _mc(api_key, "GET", "/lists", params={
        "count": 100, "fields": "lists.id,lists.name,lists.stats.member_count,lists.campaign_defaults"})
    return data.get("lists", [])


def create_mailchimp_draft(api_key: str, audience_id: str, subject: str, preview_text: str,
                           from_name: str, reply_to: str, html_body: str) -> str:
    """Creates a DRAFT campaign (never sends it) and returns the link to edit it."""
    campaign = _mc(api_key, "POST", "/campaigns", json={
        "type": "regular",
        "recipients": {"list_id": audience_id},
        "settings": {
            "subject_line": subject,
            "preview_text": preview_text,
            "title": f"{subject} ({datetime.now():%Y-%m-%d})",
            "from_name": from_name,
            "reply_to": reply_to,
        },
    })
    _mc(api_key, "PUT", f"/campaigns/{campaign['id']}/content", json={"html": html_body})
    dc = api_key.rsplit("-", 1)[1]
    return f"https://{dc}.admin.mailchimp.com/campaigns/edit?id={campaign['web_id']}"


# ----------------------------------------------------------------- LinkedIn
def linkedin_post(a: dict, settings: dict, blurb: str | None = None) -> str:
    themes_cfg = settings.get("themes", {})
    tags = ["ONG" if a["language"] == "es" else "NGO"]
    for t in a.get("themes", []):
        for h in themes_cfg.get(t, {}).get("hashtags", []):
            if h not in tags:
                tags.append(h)
    hashtags = " ".join("#" + re.sub(r"\W", "", h) for h in tags[:5])
    text = blurb if blurb is not None else a.get("excerpt", "")
    if a["language"] == "es":
        read = f"Lee el artículo completo (vía {a['source']}):"
    else:
        read = f"Read the full story (via {a['source']}):"
    parts = [a["title"], text, f"{read}\n{a['link']}", hashtags]
    return "\n\n".join(p for p in parts if p)


def linkedin_share_url(link: str) -> str:
    return "https://www.linkedin.com/sharing/share-offsite/?url=" + quote(link, safe="")
