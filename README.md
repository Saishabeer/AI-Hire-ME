# AI Hiring – Voice-Only AI Interview (Django)

Conversational interview app built with Django. The interviewer creates questions in the dashboard; candidates take a voice-only AI interview:
- AI greets and asks each question out loud (TTS).
- Candidate answers by speaking; audio is transcribed (Whisper).
- Answers are saved to the database after the last question.

## Tech
- Django 5, Django REST Framework, CORS Headers
- OpenAI API (Chat Completions, Whisper, TTS)
- python-dotenv for `.env`

## Quickstart

1) Create and activate a virtual environment
```
python -m venv venv
venv\Scripts\activate  # Windows
```

2) Install dependencies
```
pip install -r requirements.txt
```

3) Configure environment
Create a `.env` in project root:
```
OPENAI_API_KEY=your_openai_api_key_here
SECRET_KEY=your_django_dev_secret
DEBUG=1
ALLOWED_HOSTS=localhost,127.0.0.1
```
Note: `.env` is git-ignored.

4) Run the app
```
python manage.py migrate
python manage.py runserver
```

5) Create an interview
- Register/login (top-right)
- Create an interview and add questions (Short Answer, Detailed Answer, Multiple Choice)

6) Start a voice interview
- From the list or edit page, click “Start Interview”
- Enter your name and email
- Click Start; AI will speak the first question
- Hold the mic button to answer each question by voice
- On completion, responses are saved

## Project structure
- `interviews/` – CRUD for interviews and responses, voice endpoints in `ai_views.py`
- `templates/interviews/ai_voice_interview.html` – Voice UI page
- `static/js/voice-interview.js` – Client logic (record, transcribe, respond, TTS)
- `ai_engine/` – OpenAI client utilities
- `config/settings.py` – Settings (loads `.env` if present)

## Notes
- `db.sqlite3`, `.env`, `staticfiles/`, and `venv/` are ignored by `.gitignore`.
- Requires a valid OpenAI API key in `.env`.

## License
MIT (add a LICENSE file if needed)
