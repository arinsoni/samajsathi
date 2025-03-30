from flask import Flask, render_template, request, session
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()  # Load environment variables

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'your-default-secret-key')
api_key = os.getenv("GOOGLE_API_KEY")

# Updated system prompt with your requirements
INITIAL_PROMPT = """
You are Samaj-Sathi, a friendly and empathetic chatbot designed to listen to voters and understand their concerns.
Your goal is to engage users in natural conversations, ask open-ended questions, and collect insights on local issues.

Instructions:
1. Use your AI capabilities to analyze the user's input and determine if it indicates a problem or concern. Do not rely on keywords—interpret the sentiment and meaning naturally.
2. If a problem is detected:
   - Respond with emotional engagement (e.g., acknowledge their feelings with empathy like 'That sounds really tough').
   - Ask two personalized follow-up questions based on their input:
     - First: Ask about the impact (e.g., 'How does this affect you day-to-day?').
     - Second: Ask for suggestions (e.g., 'What do you think could help with this?').
   - Limit follow-ups to these two questions unless the user continues the topic.
3. If no problem is detected, respond in a friendly, conversational way to keep the chat flowing.
4. Always use a neutral, empathetic, and understanding tone.

Example:
- User: "The roads are terrible."
- Assistant: "That sounds really frustrating. How does that affect your day-to-day?"
- User: "It's hard to get to work."
- Assistant: "I can see why that'd be tough. What do you think could help with this?"
- User: "Better repairs."
- Assistant: "Got it, thanks for sharing! What else is on your mind?"

Start with a broad, welcoming question.
"""

@app.route('/')
def home():
    """Render the homepage."""
    return render_template('index.html')

@app.route('/chat', methods=['GET'])
def chat():
    """Start a new chat session."""
    session['history'] = [{'role': 'system', 'content': INITIAL_PROMPT}]
    first_message = "Hi! I'm Samaj-Sathi, here to listen. What's on your mind today?"
    session['history'].append({'role': 'assistant', 'content': first_message})
    return render_template('chat.html', history=[(msg['role'], msg['content']) for msg in session['history'][1:]])

@app.route('/respond', methods=['POST'])
def respond():
    """Generate a response using Google's Gemini model."""
    user_input = request.form['user_input'].strip()
    history = session.get('history')

    # Add user input to history
    history.append({'role': 'user', 'content': user_input})

    try:
        # Initialize the chat model
        chat_model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=api_key,
            temperature=0.7,
            convert_system_message_to_human=True
        )
        
        # Generate response
        messages = [{"role": msg["role"], "content": msg["content"]} for msg in history]
        response = chat_model.invoke(messages)
        bot_response = response.content.strip()
    except Exception as e:
        print(f"Error: {e}")
        bot_response = "Sorry, I'm having trouble right now. Please try again!"

    # Add bot response to history
    history.append({'role': 'assistant', 'content': bot_response})
    session['history'] = history

    return render_template('chat.html', history=[(msg['role'], msg['content']) for msg in history[1:]])

if __name__ == '__main__':
    app.run(debug=True, port=6001)