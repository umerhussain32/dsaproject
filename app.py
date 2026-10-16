import os
import subprocess
import stat
import urllib.parse
import streamlit as st

# --- Page Config ---
st.set_page_config(page_title="C++ Queue Image Generator", page_icon="🎨")

# C++ Source & Target Executable
CPP_SOURCE = "cpp_queue.cpp"
CPP_EXEC = "./cpp_queue.exe" if os.name == "nt" else "./cpp_queue"

# --- Automatic C++ Compiler Helper ---
def ensure_cpp_compiled():
    if not os.path.exists(CPP_EXEC):
        if not os.path.exists(CPP_SOURCE):
            st.error(f"Source file `{CPP_SOURCE}` missing from repository.")
            st.stop()
            
        with st.spinner("Compiling C++ code with g++..."):
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

# --- Helper function for Pollinations API ---
def get_pollinations_image_url(prompt: str, width: int = 1024, height: int = 1024) -> str:
    # URL-encode the user prompt to make it safe for the browser request
    encoded_prompt = urllib.parse.quote(prompt)
    return f"https://image.pollinations.ai/prompt/{encoded_prompt}?width={width}&height={height}&nologo=true"

# --- Session State ---
if "pending_prompts" not in st.session_state:
    st.session_state.pending_prompts = []

# --- UI Setup ---
st.title("🎨 Pollinations.ai Image Generator (C++ `std::queue`)")

# Input Form
with st.form(key="prompt_form"):
    user_prompt = st.text_input("Enter Image Prompt:", placeholder="e.g. pakistan")
    submit = st.form_submit_button("Add Prompt to Batch")

if submit and user_prompt:
    st.session_state.pending_prompts.append(user_prompt)
    st.success(f"Added '{user_prompt}'! Prompts waiting: {len(st.session_state.pending_prompts)}")

st.info(f"Prompts in batch waiting for C++ processing: **{len(st.session_state.pending_prompts)}**")

gallery = st.container()

# --- Run C++ Queue Processing ---
if st.button("🚀 Process Queue with C++ (`q.push` → `q.front` → `q.pop`)"):
    if not st.session_state.pending_prompts:
        st.warning("No prompts in queue! Add some above first.")
    else:
        # Format stdin for C++: line count followed by each prompt
        cpp_stdin = f"{len(st.session_state.pending_prompts)}\n" + "\n".join(st.session_state.pending_prompts) + "\n"

        # Execute C++ program via subprocess
        process = subprocess.run(
            [CPP_EXEC],
            input=cpp_stdin,
            text=True,
            capture_output=True
        )

        if process.returncode != 0:
            st.error(f"C++ Execution Error: {process.stderr}")
        else:
            # Output returned line by line via q.front() and q.pop()
            ordered_prompts = [p.strip() for p in process.stdout.strip().split("\n") if p.strip()]

            st.subheader("Generated Results (Processed in FIFO order via C++)")
            
            for idx, prompt in enumerate(ordered_prompts, start=1):
                image_url = get_pollinations_image_url(prompt)
                
                with gallery:
                    st.markdown(f"### #{idx}: Item from C++ `q.front()`")
                    st.caption(f"**Prompt:** {prompt}")
                    st.image(image_url, caption=f"URL: {image_url}", use_container_width=True)
                    st.divider()

            # Reset prompt list
            st.session_state.pending_prompts = []
            st.success("🎉 All queued items processed and popped from C++ queue!")
