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
- `interviews/` – CRUD for interviews and responses, realtime token endpoint and pages in `views.py`
- `templates/interviews/ai_voice_interview.html` – Live interview page (inline JS)
- `static/css/app.css` – Single dark theme stylesheet
- `accounts/` – Auth (login/register/logout)
- `config/` – Django project settings and URLs

## Notes
- `db.sqlite3`, `.env`, `staticfiles/`, and `venv/` are ignored by `.gitignore`.
- Requires a valid OpenAI API key in `.env`.

## License
MIT (add a LICENSE file if needed)

## Audio testing and troubleshooting

Use this checklist if you can’t hear the AI voice.

Run and prepare
- Start the server:
  - python manage.py migrate
  - python manage.py runserver
- Open http://localhost:8000 (use localhost to avoid insecure-origin WebRTC issues)
- Create an interview with at least one question

Start the voice interview
- From the interview, click “AI Interview”, fill in your name and email, then continue
- On the live interview page, click the “Start Audio” button to satisfy browser autoplay policies
- When prompted, allow microphone access

What you should see/hear
- The AI greets you and asks the first question
- Transcripts appear in real time on the page
- If realtime audio is blocked, you will still see the AI text and:
  - The page will try to play a server-generated MP3 greeting, OR
  - Your browser’s local TTS will speak the greeting

Environment requirements
- .env must include: OPENAI_API_KEY=your_openai_api_key_here
- On first launch, browsers may block autoplay; always click “Start Audio” if you don’t hear anything
- Use Chrome/Edge latest for best WebRTC compatibility
- Keep testing on https:// or http://localhost to avoid mixed/insecure origin blocks

Common issues and fixes
- Nothing plays automatically:
  - Click “Start Audio” on the page (autoplay policy)
  - Check the status text; if it mentions fallback TTS, remote audio may be blocked, but local TTS should speak
- Still silent after clicking:
  - Verify your system output device and volume
  - Check DevTools Console for errors
  - Confirm OPENAI_API_KEY in .env and restart the server
- Insecure origin:
  - If you’re not on https:// or localhost, many browsers block WebRTC audio. Use http://localhost or configure HTTPS
- Corporate network or VPN:
  - STUN/ICE traffic may be blocked. You may still receive AI text; fallback TTS will try to read it locally

Advanced options (URL query params on the live page)
- ?voice=alloy (or another supported OpenAI voice) to override the voice
- ?transcribeModel=gpt-4o-mini-transcribe or whisper-1 to choose STT model
- ?disableLocalTTS=true to turn off the local speech fallback (for debugging)

Where the behavior is implemented (for reference)
- Live page and logic: templates/interviews/ai_voice_interview.html (inline JS for WebRTC + OpenAI Realtime)
- Server endpoint: interviews/views.py → realtime_session
- Routing: interviews/urls.py
