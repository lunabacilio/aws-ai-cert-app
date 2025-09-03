"""
AWS AI Practitioner Quiz - Flask Application
============================================
This web application allows users to take an interactive quiz
based on AWS AI Practitioner exam questions.

Features:
- Immediate mode: feedback after each question
- Batch mode: all questions and results at the end
- Question range selection or random questions
- User progress tracking
"""

from flask import Flask, render_template, request, session, redirect, url_for, jsonify
import json
import random
from datetime import datetime
from functools import lru_cache
import os
from session_optimizer import (
    store_large_session, 
    get_session_questions, 
    should_use_large_session,
    estimate_session_size
)

# Initialize Flask application
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'aws-ai-practitioner-quiz-secret-key-2025')  # Use environment variable

# Cache for questions to avoid loading JSON file repeatedly
_questions_cache = None

@lru_cache(maxsize=1)
def load_questions():
    """
    Load questions from JSON file with caching
    Returns:
        list: List of dictionaries with questions
    """
    global _questions_cache
    if _questions_cache is not None:
        return _questions_cache
        
    try:
        with open('questions.json', 'r', encoding='utf-8') as file:
            _questions_cache = json.load(file)
        return _questions_cache
    except FileNotFoundError:
        app.logger.error("Error: questions.json file not found")
        return []
    except json.JSONDecodeError as e:
        app.logger.error(f"Error: JSON file has invalid format: {e}")
        return []
    except Exception as e:
        app.logger.error(f"Unexpected error loading questions: {e}")
        return []

def is_multiple_choice_question(question):
    """
    Determine if a question has multiple correct answers
    
    Args:
        question (dict): Dictionary with question data
    
    Returns:
        bool: True if it has multiple correct answers, False if only one
    """
    if is_mapping_question(question):
        return False  # Mapping questions are handled separately
    return len(question['correct_answer']) > 1

def is_mapping_question(question):
    """
    Determine if a question is a multiple mapping type (HOTSPOT or similar)
    
    Args:
        question (dict): Dictionary with question data
    
    Returns:
        bool: True if it's a mapping question, False if it's a standard question
    """
    # Check if the correct answer is a dictionary (mapping)
    return isinstance(question['correct_answer'], dict)

def shuffle_question_options(question):
    """
    Shuffle answer options of a question randomly
    maintaining correct mapping of correct answers
    
    Args:
        question (dict): Dictionary with question data
    
    Returns:
        dict: Question with shuffled options and updated correct answers
    """
    # Check if it's a multiple mapping question
    if is_mapping_question(question):
        return _shuffle_mapping_question_options(question)
    
    return _shuffle_standard_question_options(question)

def _shuffle_standard_question_options(question):
    """
    Helper function to shuffle standard question options
    """
    # Create a copy of the question to not modify the original
    shuffled_question = question.copy()
    
    # Get original options
    original_options = question['options']
    option_keys = list(original_options.keys())
    option_values = list(original_options.values())
    
    # Create mapping of original correct answers
    original_correct = question['correct_answer']
    
    # Shuffle the options
    random.shuffle(option_values)
    
    # Create new mapping of shuffled options
    shuffled_options = {}
    value_to_new_key = {}  # To map values to new keys
    
    for i, value in enumerate(option_values):
        new_key = option_keys[i]
        shuffled_options[new_key] = value
        
        # Find the original key of this value to map correct answers
        for orig_key, orig_value in original_options.items():
            if orig_value == value:
                value_to_new_key[orig_key] = new_key
                break
    
    # Update correct answers according to new mapping
    new_correct_answers = [value_to_new_key[correct_key] for correct_key in original_correct]
    
    # Update question with shuffled options
    shuffled_question['options'] = shuffled_options
    shuffled_question['correct_answer'] = new_correct_answers
    
    return shuffled_question

def _shuffle_mapping_question_options(question):
    """
    Helper function to shuffle options of a multiple mapping question
    
    Args:
        question (dict): Dictionary with mapping question
    
    Returns:
        dict: Question with shuffled options and updated mappings
    """
    shuffled_question = question.copy()
    shuffled_question['options'] = {}
    shuffled_question['correct_answer'] = {}
    
    # For each sub-question, shuffle its options
    for sub_question_key, option_list in question['options'].items():
        # Create shuffled options for this sub-question
        shuffled_options = option_list.copy()
        random.shuffle(shuffled_options)
        
        # Find what the original correct answer was
        correct_answer = question['correct_answer'][sub_question_key]
        
        # The correct answer remains the same (by content)
        shuffled_question['options'][sub_question_key] = shuffled_options
        shuffled_question['correct_answer'][sub_question_key] = correct_answer
    
    return shuffled_question

class AnswerProcessor:
    """
    Class to handle answer processing logic and avoid code duplication
    """
    
    def __init__(self, question):
        self.question = question
        self.is_mapping = is_mapping_question(question)
        self.is_multiple_choice = is_multiple_choice_question(question)
        
    def process_user_answer(self, form_data, question_prefix=""):
        """
        Process user answer from form data
        
        Args:
            form_data: Flask request.form data
            question_prefix: Prefix for form field names (for batch mode)
            
        Returns:
            tuple: (user_answer_data, is_correct, user_display, correct_display)
        """
        correct_answers = self.question['correct_answer']
        
        if self.is_mapping:
            return self._process_mapping_answer(form_data, question_prefix, correct_answers)
        elif self.is_multiple_choice:
            return self._process_multiple_choice_answer(form_data, question_prefix, correct_answers)
        else:
            return self._process_single_answer(form_data, question_prefix, correct_answers)
    
    def _process_mapping_answer(self, form_data, question_prefix, correct_answers):
        """Process mapping question answer"""
        user_answers = {}
        is_correct = True
        
        for sub_question_key in self.question['options'].keys():
            if question_prefix == "batch":
                field_name = f'mapping_{self.question["question_number"]}_{sub_question_key}'
            else:
                field_name = f'{question_prefix}mapping_{sub_question_key}'
            user_answer = form_data.get(field_name)
            user_answers[sub_question_key] = user_answer
            
            if user_answer != correct_answers[sub_question_key]:
                is_correct = False
        
        user_display, correct_display = get_mapping_answer_display(self.question, user_answers)
        return user_answers, is_correct, user_display, correct_display
    
    def _process_multiple_choice_answer(self, form_data, question_prefix, correct_answers):
        """Process multiple choice answer"""
        if question_prefix == "batch":
            field_name = f'question_{self.question["question_number"]}'
        else:
            field_name = f'{question_prefix}answer'
        
        user_answers = form_data.getlist(field_name)
        user_answers.sort()
        correct_answers_sorted = sorted(correct_answers)
        is_correct = user_answers == correct_answers_sorted
        
        user_answer_texts = get_answer_text_from_keys(self.question, user_answers) if user_answers else ['None']
        correct_answer_texts = get_answer_text_from_keys(self.question, correct_answers_sorted)
        
        user_display = ' | '.join(user_answer_texts)
        correct_display = ' | '.join(correct_answer_texts)
        
        return user_answers, is_correct, user_display, correct_display
    
    def _process_single_answer(self, form_data, question_prefix, correct_answers):
        """Process single choice answer"""
        if question_prefix == "batch":
            field_name = f'question_{self.question["question_number"]}'
        else:
            field_name = f'{question_prefix}answer'
            
        user_answer = form_data.get(field_name)
        user_answers = [user_answer] if user_answer else []
        is_correct = user_answer == correct_answers[0]
        
        user_answer_texts = get_answer_text_from_keys(self.question, [user_answer]) if user_answer else ['None']
        correct_answer_texts = get_answer_text_from_keys(self.question, correct_answers)
        
        user_display = user_answer_texts[0]
        correct_display = correct_answer_texts[0]
        
        return user_answers, is_correct, user_display, correct_display

def get_answer_text_from_keys(question, answer_keys):
    """
    Convert answer letters to full text of options
    
    Args:
        question (dict): Dictionary with question data
        answer_keys (list): List of answer keys (e.g: ['A', 'B'])
    
    Returns:
        list: List with full texts of options
    """
    answer_texts = []
    for key in answer_keys:
        if key in question['options']:
            answer_texts.append(f"{key}) {question['options'][key]}")
    return answer_texts

def get_mapping_answer_display(question, user_answers):
    """
    Generate answer display for mapping questions
    
    Args:
        question (dict): Dictionary with mapping question
        user_answers (dict): User answers {sub_question: answer}
    
    Returns:
        tuple: (user_display, correct_display)
    """
    user_parts = []
    correct_parts = []
    
    for sub_question_key in question['options'].keys():
        # Format sub-question key for display
        display_key = sub_question_key.replace('_', ' ').title()
        
        # User answer
        user_answer = user_answers.get(sub_question_key, 'Not answered')
        user_parts.append(f"{display_key}: {user_answer}")
        
        # Correct answer
        correct_answer = question['correct_answer'][sub_question_key]
        correct_parts.append(f"{display_key}: {correct_answer}")
    
    return ' | '.join(user_parts), ' | '.join(correct_parts)

def get_question_subset(questions, selection_type, start_range=None, end_range=None, num_random=None):
    """
    Get a subset of questions according to selected criteria
    
    Args:
        questions (list): Complete list of questions
        selection_type (str): 'all', 'range', or 'random'
        start_range (int): Initial range number (for 'range')
        end_range (int): Final range number (for 'range')
        num_random (int): Number of random questions (for 'random')
    
    Returns:
        list: Subset of selected questions
    """
    app.logger.info(f"get_question_subset called with: type={selection_type}, start={start_range}, end={end_range}, random={num_random}")
    
    if selection_type == 'all':
        return questions
    elif selection_type == 'range' and start_range and end_range:
        # Filter questions by range
        filtered = [q for q in questions 
                   if start_range <= q['question_number'] <= end_range]
        app.logger.info(f"Range filter {start_range}-{end_range}: found {len(filtered)} questions")
        
        # Log the actual question numbers found for debugging
        if len(filtered) > 0:
            question_nums = [q['question_number'] for q in filtered]
            app.logger.info(f"Question numbers found: {sorted(question_nums)[:10]}..." if len(question_nums) > 10 else f"Question numbers found: {sorted(question_nums)}")
        
        return filtered
    elif selection_type == 'random' and num_random:
        # Select random questions
        return random.sample(questions, min(num_random, len(questions)))
    else:
        app.logger.warning(f"Invalid selection criteria: type={selection_type}, start={start_range}, end={end_range}")
        return questions

@app.route('/')
def index():
    """
    Main route - Quiz start screen
    """
    questions = load_questions()
    total_questions = len(questions)
    
    # Clear session when returning to start
    session.clear()
    
    return render_template('index.html', total_questions=total_questions)

# Helper function for templates
@app.template_filter('is_multiple_choice')
def is_multiple_choice_filter(question):
    """
    Filter to determine if a question is multiple choice in templates
    """
    return is_multiple_choice_question(question)

@app.route('/start', methods=['POST'])
def start_quiz():
    """
    Start quiz according to user selected options
    """
    questions = load_questions()
    if not questions:
        app.logger.error("No questions available")
        return redirect(url_for('index'))
    
    # Get form configuration with defaults
    quiz_mode = request.form.get('quiz_mode', 'immediate')
    selection_type = request.form.get('selection_type', 'all')
    
    # Process question selection
    try:
        selected_questions = _get_selected_questions(questions, selection_type, request.form)
    except ValueError as e:
        app.logger.error(f"Error selecting questions: {e}")
        return redirect(url_for('index'))
    
    # Shuffle answer options for each question
    shuffled_questions = [shuffle_question_options(question) for question in selected_questions]
    
    # Initialize session
    _initialize_quiz_session(quiz_mode, shuffled_questions)
    
    # Redirect according to quiz mode
    return redirect(url_for('quiz_immediate' if quiz_mode == 'immediate' else 'quiz_batch'))

def _get_selected_questions(questions, selection_type, form_data):
    """
    Helper function to get selected questions based on criteria
    """
    app.logger.info(f"Selection type: {selection_type}")
    
    if selection_type == 'range':
        start_range = int(form_data.get('start_range', 1))
        end_range = int(form_data.get('end_range', len(questions)))
        app.logger.info(f"Range selection: {start_range} to {end_range}")
        
        result = get_question_subset(questions, 'range', start_range, end_range)
        app.logger.info(f"Questions found in range: {len(result)}")
        
        return result
    elif selection_type == 'random':
        num_random = int(form_data.get('num_random', 10))
        app.logger.info(f"Random selection: {num_random} questions")
        return get_question_subset(questions, 'random', num_random=num_random)
    else:
        app.logger.info("All questions selected")
        return questions

def _initialize_quiz_session(quiz_mode, questions):
    """
    Helper function to initialize quiz session data
    Usa optimización para sesiones grandes
    """
    session.clear()  # Clear any existing session data
    
    # Verificar si necesitamos usar el sistema optimizado
    if should_use_large_session(questions):
        app.logger.info(f"🔧 Using optimized session for {len(questions)} questions")
        
        # Usar sistema optimizado para sesiones grandes
        compact_data = store_large_session(questions, quiz_mode)
        session.update(compact_data)
        
        # Log del tamaño estimado
        estimated_size = estimate_session_size(questions)
        app.logger.info(f"📊 Estimated session size: {estimated_size} bytes (optimized)")
        
    else:
        app.logger.info(f"📝 Using standard session for {len(questions)} questions")
        
        # Usar sistema estándar para sesiones pequeñas
        session.update({
            'quiz_mode': quiz_mode,
            'questions': questions,
            'current_question': 0,
            'user_answers': {},
            'correct_answers': 0,
            'start_time': datetime.now().isoformat(),
            'is_large_session': False
        })

def _get_session_questions():
    """
    Helper function to get questions from session (optimized or standard)
    """
    if session.get('is_large_session'):
        # Usar sistema optimizado
        questions = get_session_questions(session)
        if questions is None:
            app.logger.error("❌ Large session cache expired or lost")
            return None
        return questions
    else:
        # Usar sistema estándar
        return session.get('questions', [])

@app.route('/quiz/immediate')
def quiz_immediate():
    """
    Immediate mode - Show one question at a time
    """
    questions = _get_session_questions()
    if not questions:
        app.logger.error("❌ No questions available in session")
        return redirect(url_for('index'))
    
    current_index = session.get('current_question', 0)
    
    # Check if quiz is completed
    if current_index >= len(questions):
        return redirect(url_for('results'))
    
    current_question = questions[current_index]
    progress = _calculate_progress(current_index + 1, len(questions))
    
    return render_template('quiz_immediate.html', 
                         question=current_question, 
                         progress=progress)

@app.route('/quiz/batch')
def quiz_batch():
    """
    Batch mode - Show all questions on one page
    """
    questions = _get_session_questions()
    if not questions:
        app.logger.error("❌ No questions available in session")
        return redirect(url_for('index'))
    
    return render_template('quiz_batch.html', questions=questions)

@app.route('/submit_immediate', methods=['POST'])
def submit_immediate():
    """
    Process answer in immediate mode
    """
    questions = _get_session_questions()
    if not questions:
        app.logger.error("❌ No questions available in session")
        return redirect(url_for('index'))
    
    current_index = session.get('current_question', 0)
    
    if current_index >= len(questions):
        return redirect(url_for('results'))
    
    current_question = questions[current_index]
    
    # Process answer using the AnswerProcessor
    processor = AnswerProcessor(current_question)
    user_answers, is_correct, user_display, correct_display = processor.process_user_answer(request.form)
    
    # Save user answer
    question_id = current_question['question_number']
    session['user_answers'][str(question_id)] = user_answers
    
    # Update correct answer count
    if is_correct:
        session['correct_answers'] = session.get('correct_answers', 0) + 1
    
    # Prepare feedback data
    feedback = {
        'user_answer': user_display,
        'correct_answer': correct_display,
        'is_correct': is_correct,
        'is_multiple_choice': processor.is_multiple_choice,
        'is_mapping': processor.is_mapping,
        'explanation': f"The correct answer{'s' if processor.is_multiple_choice or processor.is_mapping else ''}: {correct_display}"
    }
    
    # Advance to next question
    session['current_question'] = current_index + 1
    
    progress = _calculate_progress(current_index + 1, len(questions))
    
    return render_template('feedback.html', 
                         question=current_question, 
                         feedback=feedback,
                         progress=progress)

def _calculate_progress(current, total):
    """
    Helper function to calculate progress data
    """
    return {
        'current': current,
        'total': total,
        'percentage': round((current / total) * 100, 1)
    }

@app.route('/submit_batch', methods=['POST'])
def submit_batch():
    """
    Process all answers in batch mode
    """
    questions = _get_session_questions()
    if not questions:
        app.logger.error("❌ No questions available in session")
        return redirect(url_for('index'))
    
    app.logger.info(f"🔍 Processing batch submission for {len(questions)} questions")
    app.logger.info(f"🔍 Form data keys: {list(request.form.keys())}")
    
    correct_answers = 0
    user_answers = {}
    
    # Process all answers using AnswerProcessor
    for question in questions:
        question_id = str(question['question_number'])
        processor = AnswerProcessor(question)
        
        # For batch mode, we need to use question-specific field names
        # No prefix needed - the AnswerProcessor will handle batch mode field names
        user_answer_data, is_correct, _, _ = processor.process_user_answer(request.form, "batch")
        
        app.logger.info(f"🔍 Question {question_id}: user_answer={user_answer_data}, is_correct={is_correct}")
        
        user_answers[question_id] = user_answer_data
        if is_correct:
            correct_answers += 1
    
    app.logger.info(f"🔍 Final results: {correct_answers}/{len(questions)} correct")
    
    # Save results in session
    session['user_answers'] = user_answers
    session['correct_answers'] = correct_answers
    
    return redirect(url_for('results'))

@app.route('/results')
def results():
    """
    Show final quiz results
    """
    questions = _get_session_questions()
    if not questions:
        app.logger.error("❌ No questions available in session")
        return redirect(url_for('index'))
    
    user_answers = session.get('user_answers', {})
    correct_answers = session.get('correct_answers', 0)
    total_questions = len(questions)
    
    # Calculate statistics
    score_percentage = round((correct_answers / total_questions) * 100, 1)
    certification_level, level_class = _get_certification_level(score_percentage)
    
    # Prepare answer details
    question_details = _generate_question_details(questions, user_answers)
    
    results_data = {
        'correct_answers': correct_answers,
        'total_questions': total_questions,
        'score_percentage': score_percentage,
        'certification_level': certification_level,
        'level_class': level_class,
        'question_details': question_details
    }
    
    return render_template('results.html', results=results_data)

def _get_certification_level(score_percentage):
    """
    Determine certification level based on score
    """
    if score_percentage >= 80:
        return "Excellent - Ready for the exam", "success"
    elif score_percentage >= 70:
        return "Good - Almost ready", "warning"
    else:
        return "Needs more study", "danger"

def _generate_question_details(questions, user_answers):
    """
    Generate detailed results for each question
    """
    question_details = []
    
    for question in questions:
        question_id = str(question['question_number'])
        user_answer_data = user_answers.get(question_id, [])
        
        processor = AnswerProcessor(question)
        
        # Generate display for results
        if processor.is_mapping:
            if user_answer_data:
                user_display, correct_display = get_mapping_answer_display(question, user_answer_data)
                is_correct = all(
                    user_answer_data.get(key) == question['correct_answer'][key]
                    for key in question['options'].keys()
                )
            else:
                user_display = 'Not answered'
                _, correct_display = get_mapping_answer_display(question, {})
                is_correct = False
        else:
            if user_answer_data:
                if processor.is_multiple_choice:
                    user_answer_texts = get_answer_text_from_keys(question, sorted(user_answer_data))
                    user_display = ' | '.join(user_answer_texts)
                    is_correct = sorted(user_answer_data) == sorted(question['correct_answer'])
                else:
                    user_answer_texts = get_answer_text_from_keys(question, [user_answer_data[0]])
                    user_display = user_answer_texts[0]
                    is_correct = user_answer_data[0] == question['correct_answer'][0]
            else:
                user_display = 'Not answered'
                is_correct = False
            
            # Generate correct answer display
            if processor.is_multiple_choice:
                correct_answer_texts = get_answer_text_from_keys(question, sorted(question['correct_answer']))
                correct_display = ' | '.join(correct_answer_texts)
            else:
                correct_answer_texts = get_answer_text_from_keys(question, [question['correct_answer'][0]])
                correct_display = correct_answer_texts[0]
        
        question_details.append({
            'question': question,
            'user_answer': user_display,
            'correct_answer': correct_display,
            'is_correct': is_correct,
            'is_multiple_choice': processor.is_multiple_choice,
            'is_mapping': processor.is_mapping
        })
    
    return question_details

@app.route('/api/questions/count')
def api_questions_count():
    """
    API endpoint to get the total number of questions
    """
    questions = load_questions()
    return jsonify({
        'total': len(questions),
        'status': 'success' if questions else 'error',
        'message': 'Questions loaded successfully' if questions else 'No questions found'
    })

if __name__ == '__main__':
    # Run the application in debug mode for development
    app.run(debug=True, host='0.0.0.0', port=5000)
