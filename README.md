# 🎌 JLPT Practice App

A comprehensive Japanese Language Proficiency Test (JLPT) learning application built with Flask, featuring AI-powered quizzes, YouTube listening practice, flashcards, and retro 1980s Adobe Illustrator-inspired design.

## 🌟 Features

### 📚 Learning Modules

#### 🎯 Core Study Features
- **Daily Onomatopoeia Quiz**: 100 diverse Japanese onomatopoeia with true randomization and AI-generated examples
- **Vocabulary Quiz**: JLPT N5-N1 vocabulary with AI-generated context sentences and scoring
- **Grammar Practice**: Translation exercises (English ↔ Japanese) with detailed feedback
- **Flashcards**: Interactive spaced repetition system with forgetting curve analytics (Google login required)
- **YouTube Listening**: Real YouTube video listening comprehension with multi-question support

#### 🎮 Interactive Games
- **You are Akinator**: Test your Japanese knowledge by asking AI questions
- **AI is Akinator**: AI asks you questions about Japanese culture and language

### 🔐 Authentication & Access Control
- **Google OAuth2**: Sign in with Google account
- **Guest Access**: Browse and use basic features without account
- **Admin Dashboard**: User and feedback management system

### 🤖 AI Integration
- **Anthropic Claude API**: Powers quiz generation, answer evaluation, feedback, and translations
- **Smart Context**: AI generates natural example sentences and appropriate distractors
- **Dynamic Content**: Real-time quiz adaptation based on user performance
- **Multilingual Support**: Japanese and English interface with automatic translations

### ☁️ Cloud Data Management
- **Google Sheets Integration**: Real-time vocabulary, grammar, and listening quiz data management
- **YouTube Data API**: Automatic channel information extraction
- **Live Updates**: Content can be edited online without server restart
- **Fallback System**: Automatic Excel backup when Google Sheets unavailable

### 🎨 Design & User Experience
- **Retro 1980s Adobe Illustrator Style**: Authentic pixel fonts and visual design
- **Responsive Layout**: Works on desktop and mobile devices
- **Accessibility**: Optimized font sizes for Japanese-English bilingual content
- **Clean Interface**: Minimal distractions for focused learning
- **Dynamic Settings System**: Modal settings panel with language/font preferences
- **Toolbar Integration**: Quick access via left toolbar (🌐 language, A font)
- **Global Loading Indicator**: Retro-style spinner for all loading states
- **Streamlined Tool Palette**: Essential tools only (language, font, feedback, sitemap)
- **Multilingual Interface**: Complete Japanese/English localization with `translations.py`

## 🏗️ Architecture

### Core Technologies
```
Flask (Web Framework)
├── Routes/
│   ├── vocab.py             # Vocabulary quiz logic
│   ├── grammar.py           # Grammar translation exercises
│   ├── flashcard.py         # Flashcard system (Google login)
│   ├── youtube_listening.py # YouTube listening comprehension
│   └── akinator.py          # Interactive guessing games
├── Authentication/
│   ├── Google OAuth2        # Google account integration
│   └── Flask-Login          # Session management
├── Templates/
│   ├── base.html            # Retro UI base template
│   ├── [feature].html       # Feature-specific templates
│   └── [feature]_en.html    # English language versions
├── Static/
│   └── style-retro.css      # 1980s Adobe Illustrator styling
└── Data Sources/
    ├── Google Sheets API    # Primary data source
    ├── YouTube Data API     # Channel information
    └── Excel Files          # Backup data source
```

### Data Flow
```
Google Sheets ↔ google_sheets_helper.py ↔ Flask Routes ↔ Templates ↔ User
                       ↕                        ↕
              Excel Files (Fallback)    YouTube Data API
                       ↕
                Anthropic Claude API
```

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Anthropic API Key
- Google Cloud Service Account (for Sheets integration)
- YouTube Data API Key (for listening features)

### Installation
1. **Clone Repository**
   ```bash
   git clone <repository-url>
   cd OpenAI-JLPT-practice-app
   ```

2. **Install Dependencies**
   ```bash
   pip install flask anthropic pandas gspread google-auth python-dotenv APScheduler flask-login flask-dance flask-sqlalchemy requests
   ```

3. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (see Configuration section)
   ```

4. **Set Up Google Service Account**
   - Download service account JSON from Google Cloud Console
   - Place in project root as specified in GOOGLE_SHEETS_CREDENTIALS_PATH
   - Enable Google Sheets API and YouTube Data API v3

5. **Run Application**
   ```bash
   python app.py
   ```
   Access at `http://localhost:5000`

## 📊 Data Structure

### Google Sheets Format

#### Vocabulary Sheets (5 sheets: N5, N4, N3, N2, N1)
| Column | Description | Example |
|--------|-------------|---------|
| Kanji | Japanese kanji | 学校 |
| Word | Hiragana reading | がっこう |
| Meaning | English meaning | school |
| Type | Word category | noun |

#### Grammar Sheets (5 sheets: N5, N4, N3, N2, N1)
| Column | Description | Example |
|--------|-------------|---------|
| Grammar | Grammar pattern | てもいい |

#### YouTube Listening Quiz Sheet
| Column | Description | Example |
|--------|-------------|---------|
| id | Quiz identifier | quiz001 |
| quiz_num | Question number | 1 |
| level | JLPT level | N3 |
| title | Video title | Japanese Daily Conversation |
| video_id | YouTube video ID | dQw4w9WgXcQ |
| start | Start time (seconds) | 30 |
| end | End time (seconds) | 60 |
| question | Quiz question | What did the speaker say? |
| opt1-4 | Answer options | おはよう |
| correct | Correct answer (1-4) | 2 |
| explanation | Answer explanation | This is a morning greeting |
| explanation_time | Explanation timestamp | 45 |
| channel_link | YouTube channel URL/ID | https://youtube.com/@channel |

### Onomatopoeia Database
100 categorized onomatopoeia in `onomatopoeia_data.py`:
- **擬音語 (Giongo)**: Sound imitations (30 items)
- **擬態語 (Gitaigo)**: Manner/condition descriptions (40 items)
- **擬情語 (Gijougo)**: Emotional states (30 items)

## 🔧 Configuration

### Environment Variables
```bash
# Core API Keys
ANTHROPIC_API_KEY=sk-ant-...             # Claude API for AI features
CLAUDE_MODEL=claude-sonnet-5             # Optional model override
GOOGLE_DRIVE_API_KEY=AIza...            # Google Drive API (optional)
YOUTUBE_API_KEY=AIza...                 # YouTube Data API v3

# Google Sheets Integration
GOOGLE_SHEETS_ID=1ABC...                # Vocabulary data spreadsheet
GOOGLE_SHEETS_GRAMMAR_ID=1XYZ...        # Grammar data spreadsheet
LISTENING_QUIZ_SHEET_ID=1DEF...         # YouTube listening quiz data
LISTENING_QUIZ_SHEET_NAME=YouTube Listening Quiz
GOOGLE_SHEETS_CREDENTIALS_PATH=service.json  # Service account file

# Authentication
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret

# Flask Configuration
FLASK_SECRET_KEY=your_secret_key        # Session security
DATABASE_URL=sqlite:///app.db           # Database URL
OAUTHLIB_INSECURE_TRANSPORT=1          # Development only
```

### Database Setup
The app uses SQLite by default with the following models:
- **User**: Authentication and preferences
- **Feedback**: User feedback system (login required)
- **VocabMaster**: Vocabulary data cache
- **FlashcardProgress**: User flashcard progress tracking
- **QuizPlayCount**: YouTube listening quiz play statistics
- **OAuth**: OAuth token storage

## 🎯 Key Features Explained

### Authentication System
- **Google OAuth**: Google account login
- **Tiered Access**: Basic (guest) → Google account
- **Login Features**: Flashcards and grammar logs require a Google login
- **Feedback System**: Login required for feedback submission

### Daily Onomatopoeia System
- **True Randomization**: Uses Python's `random.choice()` on predefined list
- **No Repetition Bias**: Eliminates AI selection patterns
- **Category Balance**: Equal probability across 3 onomatopoeia types
- **Caching**: Daily quiz cached until midnight, then regenerates

### YouTube Listening System
- **Real Video Integration**: Embedded YouTube videos with time controls
- **Multi-Question Support**: Multiple questions per video
- **Channel Information**: Automatic channel name and icon extraction
- **Progress Tracking**: User play counts and statistics
- **Responsive Table**: Clickable rows with text overflow handling

### Flashcard System (Google Login Required)
- **Spaced Repetition**: Forgetting curve-based review scheduling
- **Progress Tracking**: Individual word mastery tracking
- **Visual Analytics**: Progress charts and statistics
- **JLPT Level Filtering**: Study by specific proficiency levels

### AI-Powered Content Generation
```python
# Example generation flow:
1. Random vocabulary selection from Google Sheets
2. AI generates contextual Japanese sentence with blank
3. AI creates 3 plausible distractors
4. User receives multiple choice quiz
5. AI provides feedback and translations on incorrect answers
```

## 🎨 User Interface Features

### Retro Design Elements
- **1980s Adobe Illustrator Aesthetic**: Pixel fonts, retro colors, classic UI elements
- **Streamlined Tool Palette**: Left sidebar with essential tools: 🌐 (language), A (font), ✋ (feedback), 🔍 (sitemap)
- **Modal Windows**: Authentic retro popup dialogs
- **Menu System**: Classic dropdown menus with hover effects

### Accessibility & Localization
- **Dual Language Support**: Complete Japanese and English interfaces
- **Dynamic Translation System**: Real-time language switching via `translations.py`
- **Font Options**: DotGothic16 (pixel) and Klee One (textbook) fonts
- **Settings Panel**: Modal settings dialog accessible via Help menu
- **Toolbar Quick Access**: Language (🌐) and font (A) buttons in left toolbar
- **User Preferences**: Settings persist across sessions
- **Responsive Design**: Mobile and desktop compatibility

## 🚢 Deployment

### Railway (Recommended)
1. **Connect Repository**: Link GitHub repo to Railway
2. **Environment Variables**: Set all required env vars in Railway dashboard
3. **Service Account**: Upload JSON file or set as base64 env variable
4. **Deploy**: Automatic deployment on git push

### Production Configuration
```python
# Recommended production settings
OAUTHLIB_INSECURE_TRANSPORT=0  # Enable HTTPS requirement
DATABASE_URL=postgresql://...   # Use PostgreSQL for production
FLASK_ENV=production
DEBUG=False
```

### Production Checklist
- [ ] Set `OAUTHLIB_INSECURE_TRANSPORT=0` for HTTPS
- [ ] Use production database (PostgreSQL recommended)
- [ ] Configure proper logging and error monitoring
- [ ] Set up regular database backups
- [ ] Monitor API usage and costs
- [ ] Configure CORS and security headers

## 🔍 Troubleshooting

### Common Issues

**Google Sheets Authentication Failed**
```bash
# Check service account file
ls -la your-service-account.json
# Verify sheet permissions (service account email must have access)
# Check environment variable
echo $GOOGLE_SHEETS_CREDENTIALS_PATH
```

**Claude API Errors**
```python
# Check ANTHROPIC_API_KEY (starts with sk-ant-)
# Monitor usage at https://console.anthropic.com/
# Verify the model in CLAUDE_MODEL is available to your key
```

**YouTube API Issues**
```bash
# Verify YouTube Data API v3 is enabled
# Check API key quotas and usage
# Ensure channel URLs are properly formatted
```

**Database Migration Issues**
```python
# Force database recreation
with app.app_context():
    db.drop_all()
    db.create_all()
```

## 🧪 Development

### Project Structure
```
OpenAI-JLPT-practice-app/
├── app.py                    # Main Flask application
├── models.py                 # Database models
├── forms.py                  # WTForms definitions
├── translations.py           # Complete multilingual text database (EN/JA)
├── google_sheets_helper.py   # Google Sheets API wrapper
├── onomatopoeia_data.py     # Onomatopoeia database
├── routes/                   # Feature modules
│   ├── vocab.py             # Vocabulary quizzes
│   ├── grammar.py           # Grammar practice
│   ├── flashcard.py         # Flashcard system
│   ├── youtube_listening.py # Listening comprehension
│   └── akinator.py          # Interactive games
├── templates/               # Jinja2 HTML templates
│   ├── base.html           # Base template with retro UI
│   ├── [feature].html      # Japanese versions
│   └── [feature]_en.html   # English versions
├── static/                 # CSS, JS, assets
│   └── style-retro.css     # Main retro styling
├── database/               # Excel backup files
└── instance/               # SQLite database files
```

### Adding New Features
1. **Create Route Module**: Add new file in `routes/` directory
2. **Register Blueprint**: Import and register in `app.py`
3. **Create Templates**: Add Japanese and English HTML templates
4. **Update Navigation**: Add to `base.html` menu and sitemap
5. **Add Translations**: Update `translations.py` with Japanese/English text keys
6. **Test Localization**: Verify proper translation function usage in templates
7. **Test Integration**: Ensure Google Sheets compatibility if needed

### Code Style Guidelines
- **Python**: Follow PEP 8 guidelines
- **HTML**: Use semantic markup with accessibility in mind
- **CSS**: Maintain retro 1980s aesthetic consistency
- **JavaScript**: Minimal usage, prefer server-side rendering
- **Comments**: Japanese and English comments for international developers

## 📝 API Reference

### Authentication Decorators
```python
@login_required              # Requires any authenticated user
@google_login_required      # Requires Google authentication
@admin_required             # Requires admin privileges
```

### Google Sheets Helper Functions
```python
# Load vocabulary data
load_vocab_data_from_sheets(sheet_id, sheet_name) -> pd.DataFrame

# Load grammar patterns  
load_grammar_data_from_sheets(sheet_id, sheet_name) -> List[str]

# Load YouTube listening quiz data
load_youtube_listening_data_from_sheets(sheet_id, sheet_name) -> List[Dict]

# Get authentication client
get_google_sheets_client() -> gspread.Client
```

### YouTube Integration Functions
```python
# Extract channel information
extract_channel_info(channel_data) -> Tuple[str, str]

# Get channel info from API
get_channel_info_from_api(channel_id) -> Tuple[str, str]

# Record quiz play
record_quiz_play(user_id, quiz_id) -> None
```

## 🤝 Contributing

### For Developers
1. Fork repository
2. Create feature branch: `git checkout -b feature-name`
3. Follow existing code patterns and retro styling
4. Test with both Google Sheets and Excel fallback
5. Ensure mobile responsiveness
6. Add appropriate authentication checks
7. Submit pull request with clear description

### For Content Contributors
- **Vocabulary**: Add entries to Google Sheets (requires sheet access)
- **Grammar**: Submit grammar patterns via issues
- **YouTube Content**: Suggest educational channels for listening practice
- **Translations**: Help improve Japanese-English text accuracy

### For AI Agents
This README provides comprehensive context for:
- **Architecture Understanding**: Clear data flow and component relationships
- **Authentication System**: Multi-provider OAuth implementation
- **Feature Development**: Patterns for adding new functionality
- **Database Management**: Models and migration procedures
- **API Integration**: Google Sheets, Google Drive, YouTube, and Claude APIs
- **UI/UX Guidelines**: Retro design system and accessibility considerations

## 📄 License

MIT License - see LICENSE file for details.

## 🙏 Acknowledgments

- **Anthropic**: Claude API for intelligent content generation
- **Google**: Sheets API and YouTube Data API for cloud data management
- **Flask Community**: Web framework and extension ecosystem
- **Japanese Language Community**: Vocabulary and grammar resources
- **Retro Design Enthusiasts**: 1980s aesthetic inspiration

---

**🎯 Ready to deploy? This app is optimized for Railway, Render, or any Python-hosting platform with comprehensive configuration options and fallback systems for reliability.**