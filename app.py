import os
import subprocess
import stat
import urllib.parse
import threading
import queue
import time
import streamlit as st

# --- Streamlit Page Configuration ---
st.set_page_config(page_title="Multi-User C++ Queue Generator", page_icon="🎨")

# Pathing for C++ execution
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

# --- Pollinations.ai API URL Generator ---
def get_pollinations_image_url(prompt: str, width: int = 1024, height: int = 1024) -> str:
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&safe=true"

# --- Execute C++ Executable ---
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

# --- Session State Initialization ---
if "pending_timer_prompt" not in st.session_state:
    st.session_state.pending_timer_prompt = None
if "my_last_image" not in st.session_state:
    st.session_state.my_last_image = None
if "my_last_prompt" not in st.session_state:
    st.session_state.my_last_prompt = None



# --- User Input Form ---
with st.form(key="prompt_input_form"):
    user_prompt = st.text_input("Enter Image Prompt:", placeholder="e.g. pakistan")
    submit = st.form_submit_button("Submit Prompt")

if submit and user_prompt:
    # Save user input to session state to trigger backend timer
    st.session_state.pending_timer_prompt = user_prompt
    st.rerun()

# --- Hidden Backend Timer (4.5 Seconds) ---
if st.session_state.pending_timer_prompt:
    active_prompt = st.session_state.pending_timer_prompt
    
    # 1. Inform user request is preparing
    st.toast("⏳ Prompt accepted! Preparing backend transmission...")
    
    # 2. Hidden Delay (2.5 Seconds)
    time.sleep(2.5)
    
    # 3. Add to Global C++ Queue after hidden delay completes
    global_queue.put(active_prompt)
    st.toast(f"🚀 Sent '{active_prompt}' to C++ queue!")
    
    # Reset pending timer state
    st.session_state.pending_timer_prompt = None
    st.rerun()

# --- Global Queue Status Information ---
q_count = global_queue.qsize()
if processing_lock.locked():
    st.warning(f"⏳ **Status:** Generating image... Devices waiting in queue: **{q_count}**")
else:
    st.info(f"🟢 **Status:** System idle. Devices waiting in queue: **{q_count}**")

# --- Process C++ Priority Engine ---
if not global_queue.empty():
    st.write("---")
    status_placeholder = st.empty()
    
    # Acquire lock so only 1 user/device processes at a time
    with processing_lock:
        if not global_queue.empty():
            current_prompt = global_queue.get()
            
            status_placeholder.write(f"🔄 **Processing C++ Queue:** '{current_prompt}'...")
            
            try:
                # Execute C++ logic (q.push -> q.front -> q.pop)
                cpp_result = process_prompt_with_cpp(current_prompt)
                
                # Get image from Pollinations API
                image_url = get_pollinations_image_url(cpp_result)
                
                # Save output for frontend rendering
                st.session_state.my_last_image = image_url
                st.session_state.my_last_prompt = cpp_result
                
                status_placeholder.success(f"✅ Generated image for: '{cpp_result}'")
            except Exception as e:
                status_placeholder.error(f"Error processing prompt: {e}")
            finally:
                global_queue.task_done()
                time.sleep(1) # Small gap before allowing next queue item
                st.rerun()

# --- Display Last Generated Image ---
if st.session_state.my_last_image:
    st.divider()
    st.markdown("### 🖼️ Your Generated Image")
    st.caption(f"**Prompt:** {st.session_state.my_last_prompt}")
    st.image(st.session_state.my_last_image, use_container_width=True)
