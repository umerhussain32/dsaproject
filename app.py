import os
import subprocess
import stat
import threading
import queue
import time
import streamlit as st
from groq import Groq

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Streaming C++ Queue with GPT-OSS-20B", page_icon="⚡")

# Paths for C++ compilation
CPP_SOURCE = "cpp_queue.cpp"
CPP_EXEC = "./cpp_queue.exe" if os.name == "nt" else "./cpp_queue"

# --- Automatic C++ Compilation Helper ---
def ensure_cpp_compiled():
    if not os.path.exists(CPP_EXEC):
        if not os.path.exists(CPP_SOURCE):
            st.error(f"Source file `{CPP_SOURCE}` missing from repository.")
            st.stop()
            
        compile_res = subprocess.run(
            ["g++", "-O2", CPP_SOURCE, "-o", CPP_EXEC],
            capture_output=True,
            text=True
        )
        if compile_res.returncode != 0:
            st.error(f"Compilation Error:\n{compile_res.stderr}")
            st.stop()
        
        # Grant execution permissions on Linux/macOS
        if os.name != "nt":
            st_mode = os.stat(CPP_EXEC).st_mode
            os.chmod(CPP_EXEC, st_mode | stat.S_IEXEC)

ensure_cpp_compiled()

# --- Shared Global Memory across all connected devices ---
@st.cache_resource
def get_global_queue_system():
    return {
        "global_queue": queue.Queue(),
        "processing_lock": threading.Lock()
    }

global_system = get_global_queue_system()
global_queue = global_system["global_queue"]
processing_lock = global_system["processing_lock"]

# --- Helper function for C++ queue execution ---
def process_prompt_with_cpp(prompt: str) -> str:
    cpp_stdin = f"1\n{prompt}\n"
    
    process = subprocess.run(
        [CPP_EXEC],
        input=cpp_stdin,
        text=True,
        capture_output=True
    )
    
    if process.returncode != 0:
        raise RuntimeError(f"C++ Execution Error: {process.stderr}")
    
    return process.stdout.strip()

# --- Session State Initializations ---
if "pending_timer_prompt" not in st.session_state:
    st.session_state.pending_timer_prompt = None
if "last_prompt" not in st.session_state:
    st.session_state.last_prompt = None
if "last_response" not in st.session_state:
    st.session_state.last_response = ""

# --- UI Interface ---
st.title("⚡ Streaming Text Generator (`openai/gpt-oss-20b`)")
st.write("Prompts are managed globally via **C++ `std::queue`** and processed using **Groq API** with streaming text output limited to **1000 tokens**.")

# Groq API Key Input
groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")

# Fixed model selection
MODEL_NAME = "openai/gpt-oss-20b"
st.sidebar.info(f"**Model:** `{MODEL_NAME}`\n\n**Max Token Limit:** `1000 tokens`")

# Input Form
with st.form(key="prompt_input_form"):
    user_prompt = st.text_area("Enter your Prompt / Query:", placeholder="e.g. Explain quantum computing in simple terms.", height=120)
    submit = st.form_submit_button("Submit Prompt")

if submit and user_prompt:
    if not groq_api_key:
        st.error("Please enter a valid Groq API Key in the sidebar!")
    else:
        st.session_state.pending_timer_prompt = user_prompt
        st.rerun()

# --- Hidden Backend Timer (2.5 Seconds) ---
if st.session_state.pending_timer_prompt:
    active_prompt = st.session_state.pending_timer_prompt
    
    st.toast("⏳ Prompt received! Running 2.5s backend timer...")
    time.sleep(2.5)
    
    # Send prompt to the shared C++ queue
    global_queue.put(active_prompt)
    st.toast(f"🚀 Sent to C++ queue!")
    
    st.session_state.pending_timer_prompt = None
    st.rerun()

# --- Queue Status Bar ---
q_count = global_queue.qsize()
if processing_lock.locked():
    st.warning(f"⏳ **Status:** Processing text generation... Requests waiting in queue: **{q_count}**")
else:
    st.info(f"🟢 **Status:** System idle. Requests waiting in queue: **{q_count}**")

# --- Stream Processing from C++ Queue ---
if not global_queue.empty():
    st.write("---")
    status_placeholder = st.empty()
    
    with processing_lock:
        if not global_queue.empty():
            current_prompt = global_queue.get()
            
            try:
                # 1. Process via C++ Queue Engine
                status_placeholder.write("⚙️ Routing prompt through C++ `std::queue`...")
                cpp_processed_prompt = process_prompt_with_cpp(current_prompt)
                
                status_placeholder.write(f"⚡ Streaming response from `{MODEL_NAME}`...")
                
                # 2. Setup Groq Client with Streaming
                client = Groq(api_key=groq_api_key)
                
                response_stream = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant. Provide detailed and accurate responses within the given token limit."},
                        {"role": "user", "content": cpp_processed_prompt}
                    ],
                    temperature=0.7,
                    max_tokens=1000, # Strict 1000 token output limit per response
                    stream=True      # Enables real-time streaming
                )
                
                # Container for real-time text output
                st.markdown("### 💬 Generated Response")
                st.write(f"**Prompt:** `{cpp_processed_prompt}`")
                
                # Generator function to yield streaming text chunks
                def stream_response():
                    full_text = ""
                    for chunk in response_stream:
                        if chunk.choices[0].delta.content:
                            content = chunk.choices[0].delta.content
                            full_text += content
                            yield content
                    st.session_state.last_response = full_text

                # Render live streaming text block
                st.write_stream(stream_response)
                st.session_state.last_prompt = cpp_processed_prompt
                
                status_placeholder.success("✅ Completed text generation!")
                
            except Exception as e:
                status_placeholder.error(f"Error during processing: {e}")
            finally:
                global_queue.task_done()
                time.sleep(1)
                st.rerun()

# --- Display Last Completed Response ---
elif st.session_state.last_response:
    st.divider()
    st.markdown("### 💬 Last Response")
    st.write(f"**Prompt:** `{st.session_state.last_prompt}`")
    st.markdown(st.session_state.last_response)
