import streamlit as st
from langgraph_backend import chatbot, retrieve_all_threads, delete_thread
from langchain_core.messages import HumanMessage, AIMessage
import uuid



# with st.chat_message('user'):
#     st.text('Hi')

# with st.chat_message('assistant'):
#     st.text("How can i help u?")

def generate_thread_id():
    thread_id = uuid.uuid4()
    return thread_id

def reset_chat():
    thread_id = generate_thread_id()
    st.session_state['thread_id'] = thread_id
    add_thread(st.session_state['thread_id'])
    st.session_state['message_history'] = []
    
def add_thread(thread_id):
    if thread_id not in st.session_state['chat_threads']:
        st.session_state['chat_threads'].append(thread_id)
        
# def load_conv(thread_id):
#     return chatbot.get_state(config={'configurable': {'thread_id': thread_id}}).values['messages']
def load_conv(thread_id):
    try:
        state = chatbot.get_state(config={'configurable': {'thread_id': thread_id}})
        # Check if 'messages' key exists in values
        if state.values and 'messages' in state.values:
            return state.values['messages']
        else:
            return []  # Return empty list if no messages
    except Exception as e:
        print(f"Error loading conversation: {e}")
        return []  # Return empty list on any error

def get_thread_title(thread_id):
    """
    Derive a display label for a thread using its first human message.
    Falls back to 'New chat' if no messages are present.
    """
    messages = load_conv(thread_id)
    for message in messages:
        if isinstance(message, HumanMessage):
            title = message.content.strip()
            # Keep labels short for the sidebar
            return (title[:40] + "...") if len(title) > 40 else title
    return "New chat"

# # st.session_state -> dict ->  (the things inside the session state dont get erased)



# --------------SESSION SETUPIF EMPTY ----------------
if 'message_history' not in st.session_state:
    st.session_state['message_history'] = [] 
    
if 'thread_id' not in st.session_state:
    st.session_state['thread_id'] = generate_thread_id()
    
if 'chat_threads' not in st.session_state:
    st.session_state['chat_threads'] = retrieve_all_threads()
    
add_thread(st.session_state['thread_id'])

# ------------SIDEBAR UI -----------------------------
st.sidebar.title('Chatbot')

if st.sidebar.button('New chat'): 
    reset_chat()

st.sidebar.header('My conversations')

for thread_id in st.session_state['chat_threads'][::-1]:
    # if st.sidebar.button(str(thread_id)):
    #     st.session_state['thread_id'] = thread_id
    #     messages = load_conv(thread_id)
        
    #     temp_messages = []
        
    #     for message in messages:
    #         if isinstance(message, HumanMessage):
    #             role='user'
    #         else:
    #             role='assistant'
    #         temp_messages.append({'role': role, 'content': message.content})
        
    #     st.session_state['message_history'] = temp_messages
    col1, col2 = st.sidebar.columns([3, 2])  # ✅ Create two columns
    
    # with col1:
    #     if st.button(str(thread_id), key=f"btn_{thread_id}"):  # ✅ Add unique key
    #         st.session_state['thread_id'] = thread_id
    #         messages = load_conv(thread_id)
            
    #         temp_messages = []
            
    #         for message in messages:
    #             if isinstance(message, HumanMessage):
    #                 role='user'
    #             else:
    #                 role='assistant'
    #             temp_messages.append({'role': role, 'content': message.content})
            
    #         st.session_state['message_history'] = temp_messages
    with col1:
        thread_label = get_thread_title(thread_id)
        if st.button(thread_label, key=f"btn_{thread_id}"):
            st.session_state['thread_id'] = thread_id
            messages = load_conv(thread_id)
        
            temp_messages = []
        
            for message in messages:
                if isinstance(message, HumanMessage):
                    role='user'
                else:
                    role='assistant'
                temp_messages.append({'role': role, 'content': message.content})
        
            st.session_state['message_history'] = temp_messages
    
    with col2:
        if st.button("Delete", key=f"del_{thread_id}"):  # ✅ Delete button
            # Delete from database
            if delete_thread(thread_id):
                # Remove from session state
                st.session_state['chat_threads'].remove(thread_id)
                
                # If deleted current thread, start new chat
                if st.session_state['thread_id'] == thread_id:
                    reset_chat()
                
                st.rerun()



# ------------MAIN UI --------------------------------
# loading the conversation history
for message in st.session_state['message_history']:
    with st.chat_message(message['role']):
        st.text(message['content'])

# {'role': 'user', 'content': 'Hi'}
# {'role': 'assistant', 'content': 'Hi=ello'}

user_input = st.chat_input('Type here')

if user_input:

    # first add the message to message_history
    st.session_state['message_history'].append({'role': 'user', 'content': user_input})
    with st.chat_message('user'):
        st.text(user_input)

    # response = chatbot.invoke({'messages': [HumanMessage(content=user_input)]}, config=CONFIG)
    
    # ai_message = response['messages'][-1].content
    # first add the message to message_history
    
    CONFIG = {'configurable': {'thread_id': st.session_state['thread_id']}}
    
    with st.chat_message('assistant'):
        # st.text(ai_message)
#CHANGES WERE MADE HERE TO ACTIVATE THE STREAMING FUNCTION  
        def ai_only_stream():
            for message_chunk, metadata in chatbot.stream(
                {'messages': [HumanMessage(content=user_input)]},
                config = CONFIG,
                stream_mode = 'messages',
            ):
                if isinstance(message_chunk, AIMessage):
                    yield message_chunk.content
                
       
        ai_message = st.write_stream(ai_only_stream())
        
    st.session_state['message_history'].append({'role': 'assistant', 'content': ai_message})
