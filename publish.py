"""Turns selected articles into a newsletter (HTML + Mailchimp draft)
and into LinkedIn posts."""
from __future__ import annotations

import html
import re
from datetime import datetime
from urllib.parse import quote

import requests

# ----------------------------------------------------------------- newsletter
def _article_block(a: dict, blurb: str, accent: str) -> str:
    meta = [html.escape(a["source"])]
    if a.get("published"):
        meta.append(a["published"].strftime("%d %b %Y"))
    if a.get("minutes"):
        meta.append(f"{a['minutes']} min read")
    tags = " · ".join(html.escape(t) for t in a.get("themes", [])[:2])
    image = (
        f'<a href="{html.escape(a["link"])}"><img src="{html.escape(a["image"])}" width="536" '
        f'style="width:100%;max-width:536px;height:auto;border-radius:6px;display:block;margin:0 0 12px;" alt=""></a>'
        if a.get("image") else ""
    )
    return f"""
<tr><td style="padding:24px 32px;border-bottom:1px solid #e6e6e6;">
  {image}
  {f'<p style="margin:0 0 6px;font-size:12px;letter-spacing:.04em;text-transform:uppercase;color:{accent};font-weight:bold;">{tags}</p>' if tags else ''}
  <h2 style="margin:0 0 8px;font-size:20px;line-height:1.3;">
    <a href="{html.escape(a['link'])}" style="color:#1a1a1a;text-decoration:none;">{html.escape(a['title'])}</a>
  </h2>
  <p style="margin:0 0 10px;font-size:13px;color:#777;">{' · '.join(meta)}</p>
  {f'<p style="margin:0 0 12px;font-size:15px;line-height:1.55;color:#333;">{html.escape(blurb)}</p>' if blurb else ''}
  <a href="{html.escape(a['link'])}" style="font-size:14px;font-weight:bold;color:{accent};">{'Leer más' if a['language'] == 'es' else 'Read more'} →</a>
</td></tr>"""


def build_newsletter_html(articles: list[dict], blurbs: dict[str, str], settings: dict,
                          intro: str = "", group_by_theme: bool = False,
                          for_mailchimp: bool = True) -> str:
    cfg = settings.get("newsletter", {})
    accent = cfg.get("accent_color", "#1f6f5c")
    name = html.escape(cfg.get("name", "NGO News Digest"))
    tagline = html.escape(cfg.get("tagline", ""))

    rows = []
    if group_by_theme:
        groups: dict[str, list[dict]] = {}
        for a in articles:
            groups.setdefault(a["themes"][0] if a.get("themes") else "Other news", []).append(a)
        for theme, items in groups.items():
            rows.append(f'<tr><td style="padding:28px 32px 0;"><p style="margin:0;font-size:13px;'
                        f'font-weight:bold;letter-spacing:.06em;text-transform:uppercase;color:#999;">'
                        f'{html.escape(theme)}</p></td></tr>')
            rows += [_article_block(a, blurbs.get(a["id"], a["excerpt"]), accent) for a in items]
    else:
        rows = [_article_block(a, blurbs.get(a["id"], a["excerpt"]), accent) for a in articles]

    intro_html = "".join(
        f'<p style="margin:0 0 12px;font-size:16px;line-height:1.6;color:#333;">{html.escape(p)}</p>'
        for p in intro.split("\n") if p.strip()
    )
    # Mailchimp fills in these *|...|* tags: unsubscribe link and your address (required by law)
    footer = (
        '<a href="*|UNSUB|*" style="color:#999;">Unsubscribe</a> · '
        '<a href="*|UPDATE_PROFILE|*" style="color:#999;">Update preferences</a><br>*|LIST:ADDRESSLINE|*'
        if for_mailchimp else "You received this email because you subscribed to our newsletter."
    )
    date = datetime.now().strftime("%d %B %Y")

    return f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{name}</title></head>
<body style="margin:0;padding:0;background:#f3f3f0;font-family:Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f3f3f0;">
<tr><td align="center" style="padding:24px 12px;">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:100%;max-width:600px;background:#ffffff;border-radius:8px;overflow:hidden;">
  <tr><td style="background:{accent};padding:28px 32px;color:#ffffff;">
    <p style="margin:0;font-size:26px;font-weight:bold;">{name}</p>
    <p style="margin:6px 0 0;font-size:14px;opacity:.9;">{tagline} · {date}</p>
  </td></tr>
  {f'<tr><td style="padding:28px 32px 4px;">{intro_html}</td></tr>' if intro_html else ''}
  {''.join(rows)}
  <tr><td style="padding:24px 32px;font-size:12px;line-height:1.6;color:#999;text-align:center;">{footer}</td></tr>
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
    read = "👉 Lee el artículo completo" if a["language"] == "es" else "👉 Read the full story"
    via = f"(vía {a['source']})" if a["language"] == "es" else f"(via {a['source']})"
    parts = [a["title"], text, f"{read} {via}:\n{a['link']}", hashtags]
    return "\n\n".join(p for p in parts if p)


def linkedin_share_url(link: str) -> str:
    return "https://www.linkedin.com/sharing/share-offsite/?url=" + quote(link, safe="")
