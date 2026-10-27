# How to put NGO News Digest online (step by step, no coding)

It takes about 20–30 minutes the first time. You will create two free accounts, upload the app's files, and paste two secret values. Websites change their buttons from time to time, so if a label looks slightly different, look for the closest match.

---

## Step 1 — Create a GitHub account (5 min)
GitHub is where the app's files live. Think of it as Google Drive for code.

1. Go to **https://github.com/signup**.
2. Enter your email, a password and a username, then confirm your email.
3. Choose the **Free** plan.

## Step 2 — Upload the app's files to GitHub (5 min)
1. Once logged in, click the **+** at the top right → **New repository**. (A "repository" is a project folder.)
2. **Repository name**: `ngo-news-digest`.
3. Choose **Public**. This is fine: the files contain no passwords, and the app itself will still be password-protected. You can choose **Private** if you prefer; Streamlit will then ask for extra permission in step 4.
4. Tick **Add a README file**, then click **Create repository**.
5. On the new page, click **Add file** → **Upload files**.
6. Open the `ngo-news-digest` folder on your Mac in Finder and drag these files into the browser window:
   - `app.py`
   - `news.py`
   - `publish.py`
   - `settings.yaml`
   - `style.css`
   - `requirements.txt`
   - `BRIEF.md`
   - `SETUP.md`
   - `README.md`
   - the **`.streamlit`** folder (it holds `config.toml`, the app's colours and fonts). Your Mac hides folders whose name starts with a dot: in Finder press **Cmd + Shift + .** (full stop) to show it, then drag the whole folder in. Press the same keys again to hide it.
7. Scroll down and click the green **Commit changes** button. ("Commit" just means "save".)
8. **Check that everything is listed** on your project page: the 9 files plus the `.streamlit` folder. If something is missing, repeat steps 5–7 with just that file or folder.

## Step 3 — Get your Mailchimp API key (3 min)
The API key is like a password that lets the app create drafts in your Mailchimp account.

1. Log in to **Mailchimp**.
2. Click your **profile picture** (bottom left or top right) → **Profile**.
3. Open **Extras** → **API keys**.
4. Click **Create A Key**, name it `NGO News Digest`, and click **Generate Key**.
5. **Copy the key right away** and paste it into a note for the next few minutes. Mailchimp shows it only once. It looks like `a1b2c3d4e5f6...-us21`. The part after the dash matters, so copy the whole thing.

> 🔒 Never share this key or put it in a GitHub file. It only goes in Streamlit's "Secrets" box (next step).

## Step 4 — Put the app online with Streamlit (5 min)
1. Go to **https://share.streamlit.io** and click **Continue with GitHub**. Allow access when asked.
2. Click **Create app** → **Deploy a public app from GitHub** (or "from existing repo").
3. Fill in:
   - **Repository**: `your-username/ngo-news-digest`
   - **Branch**: `main`
   - **Main file path**: `app.py`
   - **App URL**: choose a name, e.g. `my-ngo-digest` (this becomes your web address).
4. Click **Advanced settings**:
   - **Python version**: `3.12`
   - **Secrets**: paste these two lines, replacing the parts in quotes with your own:
     ```toml
     APP_PASSWORD = "choose-a-password-for-the-app"
     MAILCHIMP_API_KEY = "paste-your-mailchimp-key-here-us21"
     ```
     Keep the quotes `" "`. Click **Save**.
5. Click **Deploy**. Wait 2–3 minutes while it installs. You'll then see the password screen. 🎉

Bookmark the address. That's your app.

## Step 5 — Use it
1. Open the app and enter your password.
2. **First load takes about a minute** (it reads more than 70 websites and measures every article). After that it's instant for 3 hours.
3. **Browse news**: use the filters on the left, then tick **Select** on the articles you like.
4. **Newsletter tab**: write a subject and intro, reorder or rewrite the articles, check the preview, then click **📨 Create Mailchimp draft**. Click **Open the draft in Mailchimp**, check it, send yourself a test, and press **Send** when ready.
5. **LinkedIn tab**: edit the post, click the 📋 icon on the grey box to copy it, click **Open LinkedIn**, paste, and publish.

---

## Updating the app with new files from Claude
When Claude changes the app, you get new versions of some files. To put them online:
1. On GitHub, open your `ngo-news-digest` project → **Add file** → **Upload files**.
2. Drag in the changed files. Files with the same name are replaced. For the `.streamlit` folder, first press **Cmd + Shift + .** in Finder so it becomes visible.
3. Click **Commit changes**. The online app restarts with the new version within a minute or two.
4. Not sure which files changed? Upload all of them. It's always safe.

**If you can't get the `.streamlit` folder to upload:** on GitHub click **Add file**, then **Create new file**. Type `.streamlit/config.toml` as the name (the `/` creates the folder). Open `config.toml` from your Mac in TextEdit, copy everything, paste it into the GitHub box, and click **Commit changes**.

## Changing things later (no coding)
All the "content" settings are in **`settings.yaml`**: newsletter name and colour, the list of sources, and the themes with their keywords.

1. On GitHub, open your `ngo-news-digest` project → click **settings.yaml** → click the **pencil ✏️** icon.
2. Make your change (e.g. add a source by copying three lines and changing them).
3. Click **Commit changes**. The app updates itself within a minute or two.
4. In the app, click **🔄 Get fresh news now** to see the effect immediately.

Tip: keep the spaces at the start of each line exactly as they are. YAML files are fussy about spacing.

To change a secret (password or Mailchimp key): at share.streamlit.io click the **⋮** next to your app → **Settings** → **Secrets**.

## Good to know
- **The app "sleeps"** if nobody opens it for a while (free plan). You'll see a button like "Yes, get this app back up!": click it and wait about 30 seconds.
- **"Length unknown"** means the website blocked measuring (e.g. paywalls). The article is still fine to use.
- **Google News results** are switched off by default because they're noisier. Turn them on in the left panel when you want more stories.
- **Mailchimp sender email**: Mailchimp works best when the "Reply-to email" uses your organisation's own domain (e.g. `news@yourngo.org`) rather than Gmail. Mailchimp will guide you to verify it.
- **Nothing is sent automatically.** The app only creates drafts.

## Something went wrong?
- **Red error box on Streamlit after deploy**: at share.streamlit.io click your app → **Manage app** (bottom right) to see the log, and copy the red lines to Claude, who can help.
- **"Mailchimp isn't connected yet"**: the key is missing from Secrets, or the line name is misspelled (must be exactly `MAILCHIMP_API_KEY`).
- **"Mailchimp said: Your API key may be invalid"**: copy the key again (whole thing, including `-us21` or similar).

## Running it on your own Mac instead (optional)
Open the **Terminal** app, go to the folder, and run:
```
python3 -m pip install -r requirements.txt
python3 -m streamlit run app.py
```
Your browser opens the app. To use Mailchimp locally, create a file `.streamlit/secrets.toml` inside the folder with the same two lines as in step 4.
