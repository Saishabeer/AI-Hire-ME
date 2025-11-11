"""
OpenAI Client for AI Interview System
Handles all OpenAI API interactions
"""

import os
import json
from openai import OpenAI
from django.conf import settings
from .constants import (
    OPENAI_MODEL, 
    OPENAI_TEMPERATURE, 
    OPENAI_MAX_TOKENS,
    WHISPER_MODEL,
    ERROR_MESSAGES
)
from .prompts import SYSTEM_PROMPT


class AIInterviewClient:
    """Client for managing AI interview conversations"""
    
    def __init__(self):
        # Prefer Django setting if defined; fallback to environment variable
        self.api_key = getattr(settings, 'OPENAI_API_KEY', None) or os.environ.get('OPENAI_API_KEY', '')
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY not found in environment variables")
        
        self.client = OpenAI(api_key=self.api_key)
        self.conversation_history = []
    
    def initialize_conversation(self, system_message=None):
        """Initialize a new conversation with system prompt"""
        if system_message:
            self.conversation_history = [{
                "role": "system",
                "content": system_message
            }]
        else:
            self.conversation_history = [{
                "role": "system",
                "content": SYSTEM_PROMPT
            }]
    
    def add_message(self, role, content):
        """Add a message to conversation history"""
        self.conversation_history.append({
            "role": role,
            "content": content
        })
    
    def get_ai_response(self, user_message=None, custom_prompt=None):
        """Get response from AI"""
        try:
            # Add user message if provided
            if user_message:
                self.add_message("user", user_message)
            
            # Add custom prompt as system message if provided
            if custom_prompt:
                self.add_message("system", custom_prompt)
            
            # Get AI response
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=self.conversation_history,
                temperature=OPENAI_TEMPERATURE,
                max_tokens=OPENAI_MAX_TOKENS
            )
            
            ai_message = response.choices[0].message.content
            self.add_message("assistant", ai_message)
            
            return {
                'success': True,
                'message': ai_message,
                'usage': response.usage.dict() if response.usage else None
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': ERROR_MESSAGES['api_error']
            }
    
    def transcribe_audio(self, audio_file):
        """Transcribe audio using Whisper"""
        try:
            transcript = self.client.audio.transcriptions.create(
                model=WHISPER_MODEL,
                file=audio_file,
                language="en"
            )
            
            return {
                'success': True,
                'text': transcript.text
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'message': ERROR_MESSAGES['transcription_error']
            }
    
    def text_to_speech(self, text):
        """Convert text to speech using OpenAI TTS"""
        try:
            response = self.client.audio.speech.create(
                model="tts-1",
                voice="alloy",  # Options: alloy, echo, fable, onyx, nova, shimmer
                input=text,
                speed=1.0
            )
            
            return {
                'success': True,
                'audio': response.content
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def extract_structured_data(self, prompt):
        """Extract structured data (JSON) from AI response"""
        try:
            response = self.client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": "You are a data extraction assistant. Always return valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.3,
                response_format={"type": "json_object"}
            )
            
            result = json.loads(response.choices[0].message.content)
            
            return {
                'success': True,
                'data': result
            }
        
        except Exception as e:
            return {
                'success': False,
                'error': str(e)
            }
    
    def reset_conversation(self):
        """Reset conversation history"""
        self.conversation_history = []
    
    def get_conversation_summary(self):
        """Get a summary of the conversation"""
        return {
            'total_messages': len(self.conversation_history),
            'history': self.conversation_history
        }
