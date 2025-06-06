import streamlit as st
import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI
import speech_recognition as sr
from google.cloud.speech_v1 import SpeechClient
from google.cloud.speech_v1.types import RecognitionAudio, RecognitionConfig
import wave
import queue

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

def process_audio():
    """Process audio using Google Speech-to-Text with Hinglish support"""
    try:
        client = SpeechClient()
        
        # Try both Hindi and English recognition
        configs = [
            RecognitionConfig(
                encoding=RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-IN",  # Hindi
                alternative_language_codes=["en-IN"],  # Indian English
                enable_automatic_punctuation=True,
            ),
            RecognitionConfig(
                encoding=RecognitionConfig.AudioEncoding.LINEAR16,
                sample_rate_hertz=16000,
                language_code="en-IN",  # Indian English
                alternative_language_codes=["hi-IN"],  # Hindi
                enable_automatic_punctuation=True,
            )
        ]

        with open("temp_audio.wav", "rb") as audio_file:
            content = audio_file.read()

        audio = RecognitionAudio(content=content)
        
        # Try both configurations and use the best result
        best_transcript = ""
        max_confidence = 0

        for config in configs:
            try:
                response = client.recognize(config=config, audio=audio)
                for result in response.results:
                    if result.alternatives:
                        alt = result.alternatives[0]
                        if alt.confidence > max_confidence:
                            max_confidence = alt.confidence
                            best_transcript = alt.transcript
            except Exception:
                continue

        if best_transcript:
            return best_transcript
        else:
            st.error("Could not understand the speech clearly. Please try again.")
            return None

    except Exception as e:
        st.error(f"Speech recognition error: {str(e)}")
        return None

def save_audio_file(frames, filename="temp_audio.wav"):
    """Save audio frames to a WAV file"""
    try:
        wf = wave.open(filename, 'wb')
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(b''.join(frames))
        wf.close()
        return True
    except Exception as e:
        st.error(f"Error saving audio: {str(e)}")
        return False

# Add these at the top with your other initializations
if 'audio_queue' not in st.session_state:
    st.session_state.audio_queue = queue.Queue()

if 'recording' not in st.session_state:
    st.session_state.recording = False

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

        /* Input Container Styling */
        .input-container {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 10px;
            background: #f8f9fa;
            border-radius: 10px;
            margin-top: 20px;
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            z-index: 100;
            background: white;
            box-shadow: 0 -2px 10px rgba(0,0,0,0.1);
        }

        .stButton > button {
            background: linear-gradient(135deg, #FF6B6B 0%, #FF8E53 100%);
            color: white;
            border: none;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
        }

        /* Add padding at the bottom to prevent content from being hidden behind fixed input */
        .main {
            padding-bottom: 80px;
        }

        /* Chat container */
        .chat-container {
            margin-bottom: 100px;
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

    initialize_chat_history()

    # Display chat messages in a container
    st.markdown('<div class="chat-container">', unsafe_allow_html=True)
    # Only display messages after the system prompt
    for message in st.session_state.messages[1:]:
        role = message["role"]
        content = message["content"]
        
        if role == "assistant":
            emoji = "👨‍💼 सेवक: "
        else:
            emoji = "👤 "
        
        st.markdown(f"""
            <div class="chat-message {role}">
                <span class="govt-icon">{emoji}</span>
                {content}
            </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

    # Create a container for input elements
    st.markdown('<div class="input-container">', unsafe_allow_html=True)
    
    # Create two columns for the input and record button
    col1, col2 = st.columns([4, 1])
    
    with col1:
        user_input = st.chat_input("Apni baat yahaan likhein...")
    
    # with col2:
    #     if st.button("🎤", help="बोल कर बताएं"):
    #         if not st.session_state.recording:
    #             # Start recording
    #             st.session_state.recording = True
    #             st.session_state.audio_frames = []
                
    #             try:
    #                 p = pyaudio.PyAudio()
    #                 stream = p.open(
    #                     format=pyaudio.paInt16,
    #                     channels=1,
    #                     rate=16000,
    #                     input=True,
    #                     frames_per_buffer=1024
    #                 )
                    
    #                 placeholder = st.empty()
    #                 placeholder.markdown('<p class="recording-indicator">● Recording...</p>', unsafe_allow_html=True)
                    
    #                 while st.session_state.recording:
    #                     data = stream.read(1024, exception_on_overflow=False)
    #                     st.session_state.audio_frames.append(data)
                        
    #             except Exception as e:
    #                 st.error(f"Recording error: {str(e)}")
    #             finally:
    #                 try:
    #                     stream.stop_stream()
    #                     stream.close()
    #                     p.terminate()
    #                 except:
    #                     pass
    #         else:
    #             # Stop recording
    #             st.session_state.recording = False
    #             if hasattr(st.session_state, 'audio_frames'):
    #                 if save_audio_file(st.session_state.audio_frames):
    #                     with st.spinner('Processing audio...'):
    #                         transcript = process_audio()
    #                         if transcript:
    #                             st.session_state.user_input = transcript
    #                             st.rerun()
    #                         else:
    #                             st.error("Could not transcribe audio. Please try again.")
    
    st.markdown('</div>', unsafe_allow_html=True)

    # Process user input (text or transcribed audio)
    if 'user_input' in st.session_state:
        user_input = st.session_state.user_input
        del st.session_state.user_input

    # If there's user input, show it immediately and then process it
    if user_input:
        # Show user message immediately
        st.markdown(f"""
            <div class="chat-message user">
                <span class="govt-icon">👤 </span>
                {user_input}
            </div>
        """, unsafe_allow_html=True)

        # Append the user message to the conversation
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Show a loading spinner while processing
        with st.spinner('Processing...'):
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