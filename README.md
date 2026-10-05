# Japanese with B — JLPT Practice

A Flask web app for practicing Japanese for the JLPT (N5–N1), with a retro 1980s-style interface.
Live at [japanese-b.com](https://japanese-b.com).

## Features

- **Daily onomatopoeia quiz** — one new 擬音語・擬態語 each day with example sentences
- **Vocabulary quiz** — fill-in-the-blank questions with AI-generated sentences
- **Grammar (translation) practice** — AI scores your translation and gives feedback
- **Flashcards** — spaced repetition with a review schedule (Google login required)
- **YouTube listening** — comprehension questions on clips from real YouTube videos
- **Word Akinator** — guess the word, or let the AI guess yours
- **Blog** — articles loaded from Google Docs
- English / Japanese / Spanish interface

## Tech stack

- Python, Flask, SQLAlchemy (SQLite locally, PostgreSQL in production)
- Anthropic Claude API for quiz generation and answer evaluation
- Google Sheets (quiz data, with Excel files as fallback), Google Drive (blog), YouTube Data API
- Google OAuth login
- Deployed on Railway

## Project structure

```
app.py                  # App setup, home, auth, settings
claude_helper.py        # Claude API wrapper
google_sheets_helper.py # Quiz data from Google Sheets
google_drive_helper.py  # Blog posts from Google Drive
models.py               # Database models
translations.py         # UI text (en / ja / es)
routes/                 # grammar, vocab, flashcard, youtube_listening, akinator, blog, admin
templates/              # Jinja2 templates
static/style-retro.css  # Shared styles
static/css/             # Page-specific styles
database/               # Excel fallback data and images
```

## Running locally

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your keys
python app.py
```

## Environment variables

| Variable | Purpose |
|---|---|
| `ANTHROPIC_API_KEY` | Claude API (`CLAUDE_MODEL` optionally overrides the model) |
| `FLASK_SECRET_KEY` | Session security |
| `GOOGLE_SHEETS_ID`, `GOOGLE_SHEETS_GRAMMAR_ID` | Vocabulary / grammar spreadsheets |
| `LISTENING_QUIZ_SHEET_ID`, `LISTENING_QUIZ_SHEET_NAME` | YouTube listening quiz sheet |
| `GOOGLE_SHEETS_CREDENTIALS_PATH` | Service account JSON |
| `GOOGLE_DRIVE_API_KEY` | Blog (Google Drive) |
| `YOUTUBE_API_KEY` | YouTube channel info |
| `GOOGLE_OAUTH_CLIENT_ID`, `GOOGLE_OAUTH_CLIENT_SECRET` | Google login |
| `ADMIN_USERNAME`, `ADMIN_PASSWORD`, `ADMIN_EMAIL` | Admin account |
| `DATABASE_URL` | PostgreSQL in production (SQLite if unset) |
| `OAUTHLIB_INSECURE_TRANSPORT` | `1` for local HTTP only; `0` in production |

## Quiz data (Google Sheets)

- **Vocabulary** (one sheet per level): `Kanji`, `Word`, `Meaning`, `Type`
- **Grammar** (one sheet per level): `Grammar`
- **YouTube listening**: `id`, `quiz_num`, `level`, `title`, `video_id`, `start`, `end`,
  `question`, `opt1`–`opt4`, `correct`, `explanation`, `explanation_time`, `channel_link`

## Deployment

Railway deploys automatically on push. Set the environment variables above in the
Railway dashboard and use PostgreSQL via `DATABASE_URL`.

## Credits

Built by B. Development was assisted by [Claude](https://claude.com) (Anthropic) through
Claude Code, which is why Claude appears among the contributors. The app also uses the
Claude API for its AI features.
