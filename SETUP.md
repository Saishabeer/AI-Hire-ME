# AI Voice Interview Platform

## Quick Start

```bash
# 1. Activate virtual environment
venv\Scripts\activate

# 2. Collect static files (first time only)
python manage.py collectstatic --noinput

# 3. Run server
python manage.py runserver

# 4. Open browser
http://localhost:8000/
```

## Features

✅ **AI Speaks Questions** - OpenAI TTS with natural voice
✅ **Voice-Only Answers** - Hold button to speak (WebRTC)
✅ **Auto Transcription** - Whisper converts speech to text
✅ **Clean UI** - Dark theme, minimal design
✅ **Smart Conversation** - AI understands context

## Project Structure

```
ai_hiring/
├── static/
│   └── css/
│       └── app.css                 # Single dark theme stylesheet
├── templates/
│   └── interviews/
│       ├── ai_voice_interview.html # Live interview page (inline JS)
│       └── ai_voice_info.html      # Info/consent page
├── interviews/
│   ├── urls.py                     # Routes (including realtime session)
│   └── views.py                    # CRUD + realtime token endpoint
├── accounts/
│   ├── urls.py                     # Auth routes (login/register/logout)
│   └── views.py
└── config/
    ├── settings.py
    └── urls.py
```

## How It Works

### For HR:
1. Create interview
2. Add 3 types of questions:
   - Short Answer
   - Detailed Answer
   - Multiple Choice
3. Share interview link

### For Candidates:
1. Enter name & email
2. Click "Start Interview"
3. **AI speaks question** 🔊
4. **Hold button → Speak answer** 🎤
5. Release button
6. AI processes & asks next
7. Submit when complete

## Technical Flow

```
1. Candidate speaks → WebRTC captures audio
2. Audio → Whisper API → Text transcription
3. Text → GPT-4o-mini → AI response
4. AI text → TTS API → Audio
5. Audio plays automatically
6. Repeat for all questions
```

## API Endpoints

- `POST /interviews/ai-interview/realtime/session/` — Mint ephemeral OpenAI Realtime session token for the browser (used by the live page).

## Requirements

- Python 3.8+
- Django 5.0
- OpenAI API key in `.env` file

```env
OPENAI_API_KEY=sk-your-api-key-here
SECRET_KEY=your-secret-key
DEBUG=True
```

## Technologies

- **Backend**: Django 5.0
- **AI**: OpenAI GPT-4o-mini, TTS, Whisper
- **Frontend**: Vanilla JS, WebRTC
- **UI**: TailwindCSS (dark theme)
- **Audio**: WebRTC MediaRecorder API
