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
        st.session_state.followup_stage = 0  # 0: Not in follow-up; 1: waiting for impact; 2: waiting for suggestions
    if "user_followup_responses" not in st.session_state:
        st.session_state.user_followup_responses = {}

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

def main():
    st.set_page_config(page_title="Samaj-Sathi - Apni Baat, Apni Awaaz", page_icon="🗣️", layout="centered")

    # Sidebar toggle for deep dive mode
    deep_dive_enabled = st.sidebar.checkbox("Deep Dive Mode", value=True)

    st.markdown("""
    <style>
    .stTextInput > div > div > input {
        background-color: #f9f9f9;
        padding: 12px;
        border-radius: 10px;
    }
    .chat-message {
        padding: 15px;
        border-radius: 15px;
        margin-bottom: 12px;
        display: flex;
        flex-direction: column;
        font-size: 1rem;
    }
    .assistant {
        background-color: #e1f5fe;
        margin-right: 25%;
        align-self: flex-start;
        color: black;
    }
    .user {
        background-color: #d1c4e9;
        margin-left: 25%;
        align-self: flex-end;
        color: black;
    }
    </style>
    """, unsafe_allow_html=True)

    st.title("🗣️ Samaj-Sathi")
    st.markdown("_Apni baat, apni awaaz - voter engagement simplified!_")

    initialize_chat_history()

    # Display previous messages (excluding system prompt)
    for message in st.session_state.messages[1:]:
        role = message["role"]
        st.markdown(f"""
            <div class="chat-message {role}">
                {message['content']}
            </div>
        """, unsafe_allow_html=True)

    if user_input := st.chat_input("Apni baat yahaan likhein..."):
        # Append the user message to the conversation
        st.session_state.messages.append({"role": "user", "content": user_input})

        # Initialize the chat model
        chat_model = ChatGoogleGenerativeAI(
            model="gemini-2.0-flash",
            google_api_key=os.getenv("GOOGLE_API_KEY"),
            temperature=0.7,
            convert_system_message_to_human=True
        )

        # Check if we have not classified this input yet
        if st.session_state.is_problem is None:
            # Only classify if deep dive mode is enabled
            if deep_dive_enabled:
                is_problem = classify_input(user_input, chat_model)
                st.session_state.is_problem = is_problem
            else:
                st.session_state.is_problem = True  # Skip deep dive if disabled

            # If classified as a problem and deep dive is enabled, initiate follow-up
            if st.session_state.is_problem:
                st.session_state.followup_stage = 1
                followup_q = "Yeh sunke thoda dikkat lag raha hai. Isse aapki rozana zindagi kaise affect hoti hai?"
                st.session_state.messages.append({"role": "assistant", "content": followup_q})
            else:
                # Otherwise, get a normal conversation response
                response = chat_model.invoke(st.session_state.messages)
                bot_response = response.content.strip()
                st.session_state.messages.append({"role": "assistant", "content": bot_response})
        else:
            # If already in a deep dive conversation
            if st.session_state.is_problem:
                if st.session_state.followup_stage == 1:
                    # Record impact response and ask for suggestions
                    st.session_state.user_followup_responses["impact"] = user_input
                    st.session_state.followup_stage = 2
                    followup_q = "Aapke hisaab se isko behtar karne ke liye kya kiya ja sakta hai?"
                    st.session_state.messages.append({"role": "assistant", "content": followup_q})
                elif st.session_state.followup_stage == 2:
                    # Record suggestions response and then incorporate context
                    st.session_state.user_followup_responses["suggestions"] = user_input
                    st.session_state.followup_stage = 3
                    followup_context = (
                        f"User ne bataya: Impact - {st.session_state.user_followup_responses.get('impact', '')}; "
                        f"Suggestions - {st.session_state.user_followup_responses.get('suggestions', '')}. "
                        "Ab hum aage conversation ko in points ko dhyaan me rakhte hue continue karte hain."
                    )
                    st.session_state.messages.append({"role": "assistant", "content": followup_context})
                    # Reset deep dive controls for future messages
                    st.session_state.is_problem = None
                    st.session_state.followup_stage = 0
                    st.session_state.user_followup_responses = {}
                else:
                    # If follow-up stages are complete, continue normal conversation
                    response = chat_model.invoke(st.session_state.messages)
                    bot_response = response.content.strip()
                    st.session_state.messages.append({"role": "assistant", "content": bot_response})
            else:
                # Not a problem or deep dive mode disabled—continue normal conversation
                response = chat_model.invoke(st.session_state.messages)
                bot_response = response.content.strip()
                st.session_state.messages.append({"role": "assistant", "content": bot_response})

        st.rerun()

if __name__ == "__main__":
    main()
