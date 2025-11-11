"""
AI Engine Constants
Central configuration for AI interview system
"""

# OpenAI Configuration
OPENAI_MODEL = "gpt-4o-mini"
OPENAI_TEMPERATURE = 0.5  # Lower for faster, more consistent responses
OPENAI_MAX_TOKENS = 150  # Reduced for faster responses

# Whisper Configuration (for voice transcription)
WHISPER_MODEL = "whisper-1"
WHISPER_LANGUAGE = "en"

# WebRTC Configuration
WEBRTC_SAMPLE_RATE = 16000
WEBRTC_CHANNELS = 1
AUDIO_FORMAT = "audio/webm"

# Interview Settings
MAX_CONVERSATION_LENGTH = 50  # Maximum conversation turns
CONVERSATION_TIMEOUT = 1800  # 30 minutes in seconds
AUTO_FILL_CONFIDENCE_THRESHOLD = 0.7

# AI Personality
AI_INTERVIEWER_NAME = "Alex"
AI_PERSONALITY = "professional, friendly, and encouraging"

# Response Types
RESPONSE_TYPES = {
    'greeting': 'greeting',
    'question': 'question',
    'followup': 'followup',
    'clarification': 'clarification',
    'completion': 'completion'
}

# Question Type Mappings
QUESTION_TYPE_PROMPTS = {
    'text': "Please provide a short answer",
    'textarea': "Please provide a detailed answer",
    'multiple_choice': "Please choose one of the following options",
    'checkbox': "You can select multiple options from the following",
    'dropdown': "Please select from the following options",
    'number': "Please provide a number",
    'email': "Please provide your email address",
    'date': "Please provide a date",
    'url': "Please provide a URL or website link"
}

# Error Messages
ERROR_MESSAGES = {
    'api_error': "I apologize, but I'm having trouble processing that. Could you please try again?",
    'transcription_error': "I couldn't understand that clearly. Could you please repeat?",
    'connection_error': "Connection lost. Please check your internet connection.",
    'timeout': "I haven't heard from you in a while. Shall we continue?"
}

# Success Messages
SUCCESS_MESSAGES = {
    'answer_received': "Got it! Thank you for that answer.",
    'interview_started': "Great! Let's begin the interview.",
    'interview_completed': "Excellent! We've completed all the questions. Thank you for your time!",
    'form_submitted': "Your interview has been submitted successfully!"
}
