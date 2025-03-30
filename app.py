import streamlit as st
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

# Load environment variables
load_dotenv()

# System prompt for the chatbot
INITIAL_PROMPT = """
You are Samaj-Sathi, voters ke liye ek dost aur humdard chatbot. Tumhara kaam hai voters ki baat dhyaan se sunna, unki feelings samajhna, aur local muddon ko identify karna.

Instructions:
1. User ki baat ko dhyaan se samjho. Keywords pe rely mat karo, sentiment aur emotional meaning naturally samjho.
2. Agar koi dikkat ya pareshaani lag rahi hai:
   - Empathy dikhate hue emotionally respond karo (e.g., 'Yeh toh sach mein mushkil lag raha hai...')
   - Personalize kar ke 2 follow-up sawal pucho:
     - Pehla sawal impact ke baare mein ('Isse aapki rozana zindagi kaise affect hoti hai?')
     - Doosra sawal suggestions ke baare mein ('Aapke hisaab se isko behtar karne ke liye kya kiya ja sakta hai?')
   - Follow-ups do sawalon tak hi rakho, jab tak user baat ko continue na kare.
3. Agar koi dikkat nahi hai toh friendly, conversational, Hinglish mein respond karo.
4. Har waqt neutral, empathetic aur understanding tone rakho.

Example:
- User: "Roads bohot kharab hain."
- Assistant: "Yeh sunke bura laga, sach mein dikkat hoti hogi. Isse aapki rozmarra ki life kaise affect ho rahi hai?"
- User: "Office jaana mushkil hai."
- Assistant: "Samajh sakta hoon, kaafi pareshaani hoti hogi. Aapke hisaab se ismein kya improvement honi chahiye?"

Start with a warm, welcoming Hinglish greeting.
"""

def initialize_chat_history():
    # Initialize conversation history and control variables in session_state
    if "messages" not in st.session_state:
        st.session_state.messages = [
            {"role": "system", "content": INITIAL_PROMPT},
            {"role": "assistant", "content": "Namaste! 🙏 Main hoon Samaj-Sathi, aapki baat sunne ke liye yahaan hoon. Kaisa chal raha hai sab? Koi dikkat ya pareshaani jo aap share karna chahte ho?"}
        ]
    if "is_problem" not in st.session_state:
        st.session_state.is_problem = None  # Unknown yet
    if "followup_stage" not in st.session_state:
        st.session_state.followup_stage = 0  # 0: Not in follow-up; 1: waiting for impact answer; 2: waiting for suggestions answer
    if "user_followup_responses" not in st.session_state:
        st.session_state.user_followup_responses = {}
    if "original_message" not in st.session_state:
        st.session_state.original_message = ""

def classify_input(user_input, chat_model):
    # Revised prompt instructing the model to respond with exactly one word: "problem" or "not_a_problem"
    classification_prompt = [
        {"role": "system", "content": "Kya yeh message ek problem hai ya sirf casual conversation? Kripya sirf ek word mein jawab dein: 'problem' ya 'not_a_problem'."},
        {"role": "user", "content": user_input}
    ]
    response = chat_model.invoke(classification_prompt)
    # Extract the first word from the first line of the response
    first_line = response.content.strip().splitlines()[0].lower()
    return "problem" in first_line and "not" not in first_line

def generate_followup_question(question_type, context, chat_model):
    """
    Generates an empathetic follow-up question using AI.
    question_type: "impact" or "suggestions"
    context: relevant context text (e.g., user's original message or previous answer)
    """
    if question_type == "impact":
        prompt = [
            {"role": "system", "content": "Aap ek empathetic chatbot hain jo follow-up questions generate karte hain. Sirf ek clear question generate karein."},
            {"role": "user", "content": f"User ne ye kaha: '{context}'. Iske adhar par, ek empathetic follow-up question generate karo jo user se pooche ki is problem ka unki rozana zindagi par kya asar pad raha hai?"}
        ]
    elif question_type == "suggestions":
        prompt = [
            {"role": "system", "content": "Aap ek empathetic chatbot hain jo follow-up questions generate karte hain. Sirf ek clear question generate karein."},
            {"role": "user", "content": f"User ne ye bataya: '{context}'. Iske adhar par, ek empathetic follow-up question generate karo jo user se pooche ki unke hisaab se is problem ko behtar kaise kiya ja sakta hai?"}
        ]
    response = chat_model.invoke(prompt)
    followup_question = response.content.strip().splitlines()[0]
    return followup_question

def generate_final_reply(context, chat_model):
    """
    Uses AI to generate a final, natural conversation reply based on the context of the follow-up answers.
    """
    prompt = [
        {"role": "system", "content": "Aap ek empathetic chatbot hain jo user ke feedback ko samajh ke aage conversation continue karte hain."},
        {"role": "user", "content": f"{context} Ab is adhar par, ek friendly aur natural reply generate karo jo conversation ko aage badhaaye."}
    ]
    response = chat_model.invoke(prompt)
    return response.content.strip()

def main():
    st.set_page_config(
        page_title="Samaj-Sathi - Apni Baat, Apni Awaaz",
        page_icon="🗣️",
        layout="centered",
        initial_sidebar_state="collapsed"
    )

    # Enhanced UI styling
    st.markdown("""
    <style>
        /* Global Styles */
        .stApp {
            max-width: 1000px;
            margin: 0 auto;
        }
        
        /* Header Styling */
        .header-container {
            padding: 2rem 0;
            text-align: center;
            background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%);
            color: white;
            border-radius: 10px;
            margin-bottom: 2rem;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* Chat Container */
        .chat-container {
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background: rgba(255, 255, 255, 0.95);
            border-radius: 15px;
            box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        }
        
        /* Message Bubbles */
        .chat-message {
            padding: 15px;
            border-radius: 15px;
            margin-bottom: 15px;
            display: flex;
            flex-direction: column;
            font-size: 1rem;
            animation: fadeIn 0.5s ease-in-out;
        }
        
        .assistant {
            background: linear-gradient(135deg, #e1f5fe 0%, #b3e5fc 100%);
            margin-right: 25%;
            align-self: flex-start;
            color: #1a237e;
            border-bottom-left-radius: 5px;
            border-left: 4px solid #1a237e;
        }
        
        .user {
            background: linear-gradient(135deg, #d1c4e9 0%, #b39ddb 100%);
            margin-left: 25%;
            align-self: flex-end;
            color: #311b92;
            border-bottom-right-radius: 5px;
        }
        
        /* Input Box Styling */
        .stTextInput > div > div > input {
            background-color: #f8f9fa;
            padding: 15px;
            border-radius: 25px;
            border: 2px solid #e9ecef;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .stTextInput > div > div > input:focus {
            border-color: #FF6B6B;
            box-shadow: 0 0 0 2px rgba(255, 107, 107, 0.25);
        }
        
        /* Government Icon Style */
        .govt-icon {
            display: inline-block;
            margin-right: 8px;
            font-weight: bold;
        }
        
        /* Animations */
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        /* Footer */
        .footer {
            text-align: center;
            padding: 20px;
            color: #6c757d;
            font-size: 0.9rem;
            margin-top: 2rem;
        }
        
        /* Hide Streamlit Branding */
        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        
        /* Responsive Design */
        @media (max-width: 768px) {
            .chat-message {
                margin-left: 10%;
                margin-right: 10%;
            }
        }
    </style>
    """, unsafe_allow_html=True)

    # Header Section
    st.markdown("""
        <div class="header-container">
            <h1>🗣️ Samaj-Sathi</h1>
            <p style="font-size: 1.2rem;">Apni baat, apni awaaz - apni sarkar!</p>
        </div>
    """, unsafe_allow_html=True)

    # Chat Interface
    chat_container = st.container()
    with chat_container:
        initialize_chat_history()

        # Display chat messages (skip the system prompt)
        for message in st.session_state.messages[1:]:
            role = message["role"]
            content = message["content"]
            emoji = "👨‍💼 सेवक: " if role == "assistant" else "👤 "
            st.markdown(f"""
                <div class="chat-message {role}">
                    <span class="govt-icon">{emoji}</span>
                    {content}
                </div>
            """, unsafe_allow_html=True)

    # Chat input with improved styling
    user_input = st.chat_input("Apni baat yahaan likhein...", key="chat_input")

    if user_input:
        # Append the user message to the conversation
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Initialize the chat model
        chat_model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.7,
            convert_system_message_to_human=True
        )

        # If this is the first user message in this interaction
        if st.session_state.is_problem is None:
            # Store original message for context
            st.session_state.original_message = user_input
            # Only classify if deep dive mode is enabled; otherwise, skip deep dive
            if True:
                is_problem = classify_input(user_input, chat_model)
                st.session_state.is_problem = is_problem
            else:
                st.session_state.is_problem = True  # No deep dive if disabled

            # If classified as a problem and deep dive is enabled, generate a follow-up question using AI
            if st.session_state.is_problem:
                st.session_state.followup_stage = 1
                followup_q = generate_followup_question("impact", user_input, chat_model)
                st.session_state.messages.append({"role": "assistant", "content": followup_q})
            else:
                # Otherwise, continue with normal conversation
                response = chat_model.invoke(st.session_state.messages)
                bot_response = response.content.strip()
                st.session_state.messages.append({"role": "assistant", "content": bot_response})
        else:
            # In an ongoing deep dive conversation
            if st.session_state.is_problem:
                if st.session_state.followup_stage == 1:
                    # Record impact answer and generate suggestions follow-up question
                    st.session_state.user_followup_responses["impact"] = user_input
                    st.session_state.followup_stage = 2
                    context_for_suggestions = f"Original message: {st.session_state.original_message}. Impact: {user_input}"
                    followup_q = generate_followup_question("suggestions", context_for_suggestions, chat_model)
                    st.session_state.messages.append({"role": "assistant", "content": followup_q})
                elif st.session_state.followup_stage == 2:
                    # Record suggestions answer and generate a final reply using AI
                    st.session_state.user_followup_responses["suggestions"] = user_input
                    # Create context without exposing internal details
                    context = (
                        f"Impact: {st.session_state.user_followup_responses.get('impact', '')}; "
                        f"Suggestions: {st.session_state.user_followup_responses.get('suggestions', '')}."
                    )
                    final_reply = generate_final_reply(context, chat_model)
                    st.session_state.messages.append({"role": "assistant", "content": final_reply})
                    # Reset deep dive controls for future messages
                    st.session_state.is_problem = None
                    st.session_state.followup_stage = 0
                    st.session_state.user_followup_responses = {}
                else:
                    # If follow-up stages are complete, continue with normal conversation
                    response = chat_model.invoke(st.session_state.messages)
                    bot_response = response.content.strip()
                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
            else:
                # Not a problem or deep dive mode is disabled—continue normal conversation
                response = chat_model.invoke(st.session_state.messages)
                bot_response = response.content.strip()
                st.session_state.messages.append({"role": "assistant", "content": bot_response})

        st.rerun()

    # Footer
    st.markdown("""
        <div class="footer">
            <p>जनता की आवाज़, सरकार के साथ</p>
        </div>
    """, unsafe_allow_html=True)

if __name__ == "__main__":
    main()
