"""
AI Interview Session Manager
Manages the flow of conversational interviews
"""

import json
from datetime import datetime
from .openai_client import AIInterviewClient
from .prompts import (
    get_interview_start_prompt,
    get_question_prompt,
    get_answer_extraction_prompt,
    FOLLOWUP_PROMPT,
    COMPLETION_PROMPT
)
from .constants import SUCCESS_MESSAGES


class InterviewSession:
    """Manages a single AI interview session"""
    
    def __init__(self, interview_obj):
        """
        Initialize interview session
        
        Args:
            interview_obj: Django Interview model instance
        """
        self.interview = interview_obj
        self.ai_client = AIInterviewClient()
        self.current_question_index = 0
        self.questions = list(interview_obj.questions.all())
        self.answers = {}
        self.conversation_log = []
        self.started_at = datetime.now()
        self.completed = False
    
    def start_interview(self):
        """Start the interview with AI greeting"""
        # Initialize AI with system prompt
        self.ai_client.initialize_conversation()
        
        # Generate start prompt
        start_prompt = get_interview_start_prompt(
            interview_title=self.interview.title,
            interview_description=self.interview.description,
            total_questions=len(self.questions)
        )
        
        # Get AI greeting
        response = self.ai_client.get_ai_response(custom_prompt=start_prompt)
        
        self._log_interaction('system', 'interview_started', start_prompt)
        self._log_interaction('assistant', 'greeting', response.get('message', ''))
        
        return {
            'success': response['success'],
            'message': response['message'],
            'session_id': id(self),
            'total_questions': len(self.questions),
            'current_question': 0
        }
    
    def ask_next_question(self):
        """Ask the next question in the interview"""
        if self.current_question_index >= len(self.questions):
            return self.complete_interview()
        
        current_question = self.questions[self.current_question_index]
        
        # Prepare question data
        question_data = {
            'question_text': current_question.question_text,
            'question_type': current_question.question_type,
            'is_required': current_question.is_required,
            'options': [opt.option_text for opt in current_question.options.all()] if hasattr(current_question, 'options') else []
        }
        
        # Generate question prompt
        question_prompt = get_question_prompt(question_data)
        
        # Get AI to ask the question
        response = self.ai_client.get_ai_response(custom_prompt=question_prompt)
        
        self._log_interaction('system', 'question_prompt', question_prompt)
        self._log_interaction('assistant', 'question', response.get('message', ''))
        
        return {
            'success': response['success'],
            'message': response['message'],
            'question_number': self.current_question_index + 1,
            'total_questions': len(self.questions),
            'question_id': current_question.id,
            'question_type': current_question.question_type,
            'is_required': current_question.is_required
        }
    
    def process_answer(self, candidate_response):
        """Process candidate's answer to current question"""
        if self.current_question_index >= len(self.questions):
            return self.complete_interview()
        
        current_question = self.questions[self.current_question_index]
        
        # Prepare question data for extraction
        question_data = {
            'question_text': current_question.question_text,
            'question_type': current_question.question_type,
            'options': [opt.option_text for opt in current_question.options.all()] if hasattr(current_question, 'options') else []
        }
        
        # Log user response
        self._log_interaction('user', 'answer', candidate_response)
        
        # Extract and validate answer
        extraction_prompt = get_answer_extraction_prompt(question_data, candidate_response)
        extraction_result = self.ai_client.extract_structured_data(extraction_prompt)
        
        if not extraction_result['success']:
            # Fallback: just use the raw response
            extracted_data = {
                'answer': candidate_response,
                'is_valid': True,
                'confidence': 0.5,
                'needs_clarification': False
            }
        else:
            extracted_data = extraction_result['data']
        
        # Check if clarification needed
        if extracted_data.get('needs_clarification', False):
            followup_message = extracted_data.get('clarification_message', 'Could you please clarify your answer?')
            
            self._log_interaction('assistant', 'followup', followup_message)
            
            return {
                'success': True,
                'needs_clarification': True,
                'message': followup_message,
                'question_number': self.current_question_index + 1,
                'total_questions': len(self.questions)
            }
        
        # Save the answer
        self.answers[current_question.id] = {
            'question': current_question,
            'answer': extracted_data.get('answer', candidate_response),
            'confidence': extracted_data.get('confidence', 0.8),
            'raw_response': candidate_response
        }
        
        # Acknowledge answer
        acknowledgment = f"{SUCCESS_MESSAGES['answer_received']} "
        
        # Store current question ID before moving
        answered_question_id = current_question.id
        
        # Move to next question
        self.current_question_index += 1
        
        if self.current_question_index >= len(self.questions):
            return self.complete_interview()
        
        # Ask next question
        next_question_response = self.ask_next_question()
        
        return {
            'success': True,
            'message': acknowledgment + next_question_response['message'],
            'answer_saved': True,
            'answered_question_id': answered_question_id,
            'question_number': self.current_question_index + 1,
            'total_questions': len(self.questions)
        }
    
    def complete_interview(self):
        """Complete the interview"""
        if self.completed:
            return {
                'success': True,
                'completed': True,
                'message': 'Interview already completed'
            }
        
        # Get completion message from AI
        response = self.ai_client.get_ai_response(custom_prompt=COMPLETION_PROMPT)
        
        self._log_interaction('system', 'completion', COMPLETION_PROMPT)
        self._log_interaction('assistant', 'completion', response.get('message', ''))
        
        self.completed = True
        
        return {
            'success': True,
            'completed': True,
            'message': response['message'],
            'answers': self.get_formatted_answers(),
            'total_questions': len(self.questions),
            'answered_questions': len(self.answers)
        }
    
    def get_formatted_answers(self):
        """Get all answers in a formatted structure"""
        formatted = []
        for question_id, answer_data in self.answers.items():
            formatted.append({
                'question_id': question_id,
                'question_text': answer_data['question'].question_text,
                'question_type': answer_data['question'].question_type,
                'answer': answer_data['answer'],
                'confidence': answer_data['confidence'],
                'raw_response': answer_data['raw_response']
            })
        return formatted
    
    def _log_interaction(self, role, interaction_type, content):
        """Log conversation interaction"""
        self.conversation_log.append({
            'timestamp': datetime.now().isoformat(),
            'role': role,
            'type': interaction_type,
            'content': content
        })
    
    def get_session_data(self):
        """Get complete session data"""
        return {
            'interview_id': self.interview.id,
            'interview_title': self.interview.title,
            'started_at': self.started_at.isoformat(),
            'completed': self.completed,
            'current_question': self.current_question_index,
            'total_questions': len(self.questions),
            'answers': self.get_formatted_answers(),
            'conversation_log': self.conversation_log
        }
