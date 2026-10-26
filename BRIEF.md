# NGO News Digest: project brief

## In one sentence
A private web app that collects the latest news about the NGO world, in English (international) and Spanish (Spain), lets you filter it by theme and length, and turns the articles you pick into a Mailchimp newsletter draft or into LinkedIn posts.

## The problem it solves
Following the sector means checking a dozen websites every week. This app does it for you: you open one page, see everything from the last few days in one list, pick the best items, and publish them.

## Who uses it
You, the editor. The app is protected with a password, so the public never sees it. Only your newsletter readers and LinkedIn followers see what you publish.

## What it does

### 1. Gather
- Reads 20 trusted sources automatically through their news feeds (RSS), each time you open the app (results are kept for 3 hours so it stays fast).
- **English / international:** The New Humanitarian, Devex, UN News, The Guardian Global Development, Inter Press Service, Alliance Magazine, Stanford Social Innovation Review, Bond, Human Rights Watch, and a Google News search for "NGO / nonprofit / charity".
- **Spanish / Spain:** El País Planeta Futuro, eldiario.es Desalambre, Europa Press Social, IPS Noticias, Coordinadora de ONGD, Revista Haz, Compromiso Empresarial, Corresponsables, and Google News searches for "ONG" and "tercer sector".
- Removes duplicates, such as the same story picked up by two sources.
- Sources can be added or removed by editing one file (`settings.yaml`), with no coding.

### 2. Organise
- **Theme**: each article is tagged automatically using keyword lists in English and Spanish. Starting themes:
  Humanitarian & emergencies · Climate & environment · Health · Human rights & equality · Migration & refugees · Funding & philanthropy · Children & education · Poverty & social inclusion · NGO sector & volunteering · Development & cooperation.
- **Length**: the app measures each article's real length and shows reading time:
  Short (under 3 min) · Medium (3 to 7 min) · Long (over 7 min) · Unknown (when the website doesn't allow measuring).
- **Filters**: language, theme, length, source, how many days back, and a free-text search.

### 3. Publish
- **Newsletter (Mailchimp)**: tick the articles you want, write a subject line and a short intro, optionally rewrite each article's blurb, preview the email, then press one button. A **draft** campaign appears in your Mailchimp account. Nothing is ever sent automatically: you review it in Mailchimp and press Send yourself. A downloadable HTML version is also available.
- **LinkedIn**: for each ticked article the app prepares a ready-to-edit post (in the article's language, with hashtags based on its themes). You copy the text, click "Open LinkedIn", and paste. LinkedIn does not allow apps to post on your behalf without a lengthy approval process, so this copy-and-paste step is intentional.

## What it deliberately does NOT do (for now)
- No AI writing. Summaries come from the sources' own excerpts, and you can edit them. AI summaries can be added later.
- No automatic sending of emails or posts. You always press the final button.
- It doesn't remember your selections after you close the page. You pick, publish, and done.

## Where it runs
- Online, for free, on **Streamlit Community Cloud**, connected to a free **GitHub** account that stores the app's files.
- Your Mailchimp key and app password are stored in Streamlit's "Secrets" box, never in the files.

## What you need
| Thing | Cost | Why |
|---|---|---|
| GitHub account | Free | Stores the app's files |
| Streamlit Community Cloud account | Free | Runs the app online |
| Mailchimp account + API key | Free plan works | To create newsletter drafts |
| LinkedIn account | Free | To share posts |

## Ideas for later
- AI-written summaries and LinkedIn posts (with Claude).
- A saved "reading list" that remembers articles between visits.
- A weekly email reminder with the top stories.
- More languages (e.g. Italian, French).
