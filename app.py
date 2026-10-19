import os
import subprocess
import stat
import urllib.parse
import threading
import queue
import time
import streamlit as st
from groq import Groq

# --- Page Configuration ---
st.set_page_config(page_title="Groq API + C++ Queue Generator", page_icon="⚡")

# C++ Compilation Paths
CPP_SOURCE = "cpp_queue.cpp"
CPP_EXEC = "./cpp_queue.exe" if os.name == "nt" else "./cpp_queue"

# --- Automatic C++ Compiler Helper ---
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
        
        # Grant executable permissions on Linux/macOS servers
        if os.name != "nt":
            st_mode = os.stat(CPP_EXEC).st_mode
            os.chmod(CPP_EXEC, st_mode | stat.S_IEXEC)

ensure_cpp_compiled()

# --- Shared Global Memory Across Devices ---
@st.cache_resource
def get_global_queue_system():
    return {
        "global_queue": queue.Queue(),
        "processing_lock": threading.Lock()
    }

global_system = get_global_queue_system()
global_queue = global_system["global_queue"]
processing_lock = global_system["processing_lock"]

# --- Groq API Helper Function ---
def refine_prompt_with_groq(user_prompt: str, api_key: str, model_name: str = "openai/gpt-oss-20b") -> str:
    """
    Sends user prompt to Groq API with max_tokens set to 1000.
    """
    client = Groq(api_key=api_key)
    
    completion = client.chat.completions.create(
        model=model_name,
        messages=[
            {
                "role": "system", 
                "content": "You are an expert image prompt engineer. Expand the user's short prompt into a vivid, highly detailed visual description suitable for image generation models. Keep your response concise, focused, and under 1000 tokens."
            },
            {
                "role": "user", 
                "content": user_prompt
            }
        ],
        temperature=0.7,
        max_tokens=1000, # Limited output tokens to 1000 as requested
        top_p=1,
        stream=False
    )
    return completion.choices[0].message.content.strip()

# --- Pollinations.ai API Helper ---
def get_pollinations_image_url(prompt: str, width: int = 1024, height: int = 1024) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"

# --- Execute C++ Queue ---
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
if "my_last_image" not in st.session_state:
    st.session_state.my_last_image = None
if "my_last_prompt" not in st.session_state:
    st.session_state.my_last_prompt = None
if "enhanced_prompt" not in st.session_state:
    st.session_state.enhanced_prompt = None

# --- UI Interface ---
st.title("⚡ Groq API + C++ Queue Image Generator")
st.write("User prompts are processed through **Groq API** (limited to 1000 output tokens), queued via **C++ `std::queue`**, and rendered using **Pollinations.ai**.")

# Groq API Key Input
groq_api_key = st.sidebar.text_input("Enter Groq API Key:", type="password")

# Selected Model Name Option
selected_model = st.sidebar.selectbox(
    "Select Groq Model:",
    options=["openai/gpt-oss-20b", "llama3-8b-8192", "mixtral-8x7b-32768"],
    help="Select the Groq model endpoint to refine and generate image prompts."
)

# Input Form
with st.form(key="prompt_input_form"):
    user_prompt = st.text_input("Enter Image Prompt:", placeholder="e.g. pakistan")
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
    
    st.toast("⏳ Prompt accepted! Initiating hidden 2.5s timer...")
    
    # 2.5s Hidden Delay
    time.sleep(2.5)
    
    # Push prompt into shared C++ global queue
    global_queue.put(active_prompt)
    st.toast(f"🚀 Sent '{active_prompt}' to C++ Queue!")
    
    st.session_state.pending_timer_prompt = None
    st.rerun()

# --- Global Queue Status Information ---
q_count = global_queue.qsize()
if processing_lock.locked():
    st.warning(f"⏳ **Status:** Processing image request... Devices in queue: **{q_count}**")
else:
    st.info(f"🟢 **Status:** System idle. Requests in queue: **{q_count}**")

# --- Process Priority Queue with Groq API & C++ ---
if not global_queue.empty():
    st.write("---")
    status_placeholder = st.empty()
    
    with processing_lock:
        if not global_queue.empty():
            current_prompt = global_queue.get()
            
            try:
                # 1. Enhance prompt via Groq API (max_tokens=1000)
                status_placeholder.write(f"⚡ Processing prompt with Groq API (`max_tokens=1000`)...")
                groq_enhanced_prompt = refine_prompt_with_groq(
                    user_prompt=current_prompt,
                    api_key=groq_api_key,
                    model_name=selected_model
                )
                
                # 2. Process enhanced prompt in C++ queue execution (q.push -> q.front -> q.pop)
                status_placeholder.write(f"⚙️ Running through C++ queue (`cpp_queue`)....")
                cpp_result = process_prompt_with_cpp(groq_enhanced_prompt)
                
                # 3. Request Image from Pollinations.ai
                status_placeholder.write(f"🎨 Generating image with Pollinations.ai...")
                image_url = get_pollinations_image_url(cpp_result)
                
                # Store results for display
                st.session_state.my_last_image = image_url
                st.session_state.my_last_prompt = current_prompt
                st.session_state.enhanced_prompt = cpp_result
                
                status_placeholder.success(f"✅ Finished generating for: '{current_prompt}'")
            except Exception as e:
                status_placeholder.error(f"Error during processing: {e}")
            finally:
                global_queue.task_done()
                time.sleep(1)
                st.rerun()

# --- Display Image & Prompt Output ---
if st.session_state.my_last_image:
    st.divider()
    st.markdown("### 🖼️ Generated Image")
    st.write(f"**Original Prompt:** `{st.session_state.my_last_prompt}`")
    with st.expander("Show Groq Enhanced Prompt (Limited to <= 1000 tokens)"):
        st.write(st.session_state.enhanced_prompt)
    st.image(st.session_state.my_last_image, use_container_width=True)
