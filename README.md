# 450 DSA Tracker - Flask Edition

A Python Flask web application to track your progress through the 450 DSA problems. This is a complete conversion from the original React + LocalBase version to Flask + SQLAlchemy with a SQLite database.

## Features

- **Topic-wise tracking**: View progress for each Data Structures & Algorithms topic
- **Question status**: Mark questions as done/incomplete
- **Bookmarking**: Bookmark important questions for quick reference
- **Notes**: Add and save notes for each problem
- **Progress dashboard**: Visual progress bars showing completion percentage
- **Persistent storage**: All data stored in SQLite database

## Quick Start

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Set up environment variables**
```bash
copy .env.example .env
```
Update `SECRET_KEY` and any OAuth or MongoDB credentials in `.env` before running the app.

3. **Run the Flask app**
```bash
python run.py
```

4. **Open in browser**
```
http://localhost:5000
```

## Project Structure

```
450-DSA/
├── app.py                 # Flask application & SQLAlchemy models
├── .env.example           # Example environment variables
├── data.json              # Question data (converted from JS)
├── requirements.txt       # Python dependencies
├── templates/             # Jinja2 HTML templates
│   ├── base.html         # Base template (Bootstrap 4)
│   ├── index.html        # Dashboard view
│   └── topic.html        # Questions table view
├── venv/                 # Python virtual environment
└── instance/
    └── dsa.db            # SQLite database (auto-created)
```

## Database Models

The project uses SQLAlchemy ORM with SQLite:

**Topic Model**
- `id`: Primary key
- `name`: Topic name (unique)
- `position`: Order in curriculum
- `started`: Whether user initiated this topic
- `questions`: Relationship to Question records

**Question Model**
- `id`: Primary key
- `topic_id`: Foreign key to Topic
- `problem`: Problem statement
- `done`: Completion status
- `bookmark`: Bookmark flag
- `notes`: User notes/solutions
- `url`: Main problem link
- `url2`: Alternative link (Coding Ninjas)

## Features

- ✅ **Dashboard**: Overview of all topics with progress bars
- ✅ **Topic View**: All questions for a specific topic
- ✅ **Status Tracking**: Mark questions as complete
- ✅ **Bookmarks**: Bookmark important questions
- ✅ **Notes**: Add personal notes for each question
- ✅ **Progress**: Track completion percentage
- ✅ **Persistent Storage**: All data saved to SQLite

## API Endpoints

Interactive Swagger/OpenAPI documentation is available after starting the app:

```
http://localhost:5000/apidocs
```

### Frontend Routes
- `GET /` - Dashboard with all topics
- `GET /topic/<topic_id>` - View questions for a topic

### REST API
- `GET /api/search_questions` - Search DSA questions by query and optional limit.
- `GET /api/leaderboard` - Fetch paginated leaderboard data by ranking mode.
- `POST /update_question/<question_id>` - Update question (body: `{done, bookmark, notes}`)
- `POST /sync_platforms` - Sync authenticated user's coding platform statistics.
- `POST /edit_profile` - Update authenticated user's profile fields.
- `POST /upload_photo` - Upload a profile image when photo storage is configured.
- `GET /search_universities` - Search university names for profile autocomplete.

## Conversion from React

This represents a complete rewrite from React + LocalBase to Flask + SQLAlchemy:

| Original | New |
|----------|-----|
| React Components | Jinja2 Templates |
| React Hooks/Context | Flask Routes & SQLAlchemy |
| LocalBase | SQLite Database |
| 450DSAFinal.js | data.json |
| Package.json | requirements.txt |

The `450DSAFinal.js` data was converted to valid JSON using `pyjson5` and loaded into the database on first run.

## Technologies Used

- **Backend**: Flask 2.3.2
- **ORM**: Flask-SQLAlchemy 3.0.5  
- **Database**: SQLite 3
- **Frontend**: Jinja2, Bootstrap 4, jQuery
- **Data Format**: JSON

## Future Enhancements

- [ ] User authentication & registration
- [ ] Import/Export functionality
- [ ] Dark mode theme
- [ ] Advanced search and filtering
- [ ] Statistics dashboard
- [ ] REST API with API documentation
- [ ] Rate limiting and caching
- [ ] Deployment to cloud (Render, Heroku, etc.)

## Notes

- Database is created automatically on first run in `instance/dsa.db`
- All 450+ problems are preloaded from `data.json`
- Uses AJAX for seamless updates without page reload

## Credits

Original 450 DSA dataset by **Love Babbar** for his "Cracking the Coding Interview" course.

Flask version conversion: 2026

[![OPEN-PR](https://img.shields.io/badge/Open%20For-PR-orange?style=for-the-badge&logo=github)](https://github.com/mohitkumhar/450-dsa)

## Credits 🙏🏻

#### Curated list of question in [450dsa] is based on _[DSA Cracker Sheet]_ by [Love Babbar]



## Docker Quick Start

### Prerequisites
- Docker Desktop installed

### Run with Docker

```bash
git clone https://github.com/mohitkumhar/450-dsa.git
cd 450-dsa
docker compose up
```

Open the application at:

http://localhost:5000
