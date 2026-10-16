import os
import subprocess
import stat
import urllib.parse
import threading
import queue
import time
import streamlit as st

# --- Page Config ---
st.set_page_config(page_title="Global C++ Multi-User Queue", page_icon="🎨")

# C++ Source & Target Executable
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
        
        # Set executable permissions on Linux/macOS
        if os.name != "nt":
            st_mode = os.stat(CPP_EXEC).st_mode
            os.chmod(CPP_EXEC, st_mode | stat.S_IEXEC)

ensure_cpp_compiled()

# --- Global Multi-User State Shared Across All Devices ---
@st.cache_resource
def get_global_queue_system():
    """
    Returns a shared thread-safe Queue and Lock persistent across 
    all connected browser sessions and different devices.
    """
    return {
        "global_queue": queue.Queue(),
        "processing_lock": threading.Lock()
    }

global_system = get_global_queue_system()
global_queue = global_system["global_queue"]
processing_lock = global_system["processing_lock"]

# --- Helper: Pollinations.ai API ---
def get_pollinations_image_url(prompt: str, width: int = 1024, height: int = 1024) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}"

# --- Function to Execute C++ Queue Program ---
def process_prompt_with_cpp(prompt: str) -> str:
    """Passes 1 prompt into C++ binary stdin, running q.push, q.front, and q.pop."""
    cpp_stdin = f"1\n{prompt}\n"
    
    process = subprocess.run(
        [CPP_EXEC],
        input=cpp_stdin,
        text=True,
        capture_output=True
    )
    
    if process.returncode != 0:
        raise RuntimeError(f"C++ Execution Error: {process.stderr}")
    
    # C++ returns prompt output back via stdout using q.front() and q.pop()
    return process.stdout.strip()

# --- UI Interface ---
st.title("🎨 Multi-User Priority Queue Generator")
st.write("One image is processed at a time globally across all devices using C++ queue logic.")

# Form Input
with st.form(key="single_prompt_form"):
    user_prompt = st.text_input("Enter Image Prompt:", placeholder="e.g. pakistan")
    submit = st.form_submit_button("Submit Prompt to Queue")

# Initialize session result storage
if "my_last_image" not in st.session_state:
    st.session_state.my_last_image = None
if "my_last_prompt" not in st.session_state:
    st.session_state.my_last_prompt = None

if submit and user_prompt:
    # Check if this user is already waiting in queue
    global_queue.put(user_prompt)
    st.toast(f"Submitted '{user_prompt}' to the global queue!")

# Queue Status Info Displayed to All Devices
q_count = global_queue.qsize()
if processing_lock.locked():
    st.warning(f"⏳ **Status:** An image is currently generating. Requests waiting in line: **{q_count}**")
else:
    st.info(f"🟢 **Status:** System idle. Requests in queue: **{q_count}**")

# Processing Mechanism
if not global_queue.empty():
    st.write("---")
    status_placeholder = st.empty()
    
    # Acquire lock so ONLY 1 user/device processes at a time
    with processing_lock:
        if not global_queue.empty():
            # Get next prompt waiting in queue
            current_prompt = global_queue.get()
            
            status_placeholder.write(f"🔄 **Processing request:** '{current_prompt}' via C++ queue...")
            
            try:
                # 1. Feed prompt to C++ program (runs q.push, q.front, q.pop)
                cpp_result_prompt = process_prompt_with_cpp(current_prompt)
                
                # 2. Get Pollinations image URL
                image_url = get_pollinations_image_url(cpp_result_prompt)
                
                # Store result for display
                st.session_state.my_last_image = image_url
                st.session_state.my_last_prompt = cpp_result_prompt
                
                status_placeholder.success(f"✅ Finished generating for: '{cpp_result_prompt}'!")
            except Exception as e:
                status_placeholder.error(f"Error processing prompt: {e}")
            finally:
                global_queue.task_done()
                time.sleep(1) # Small delay before letting next user take turn
                st.rerun()

# Display Generated Image for User
if st.session_state.my_last_image:
    st.divider()
    st.markdown("### 🖼️ Your Generated Image")
    st.caption(f"**Prompt:** {st.session_state.my_last_prompt}")
    st.image(st.session_state.my_last_image, use_container_width=True)
