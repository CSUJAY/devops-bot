import streamlit as st
import os
import whisper
import subprocess # <--- NEW: Needed for running Git commands
from streamlit_mic_recorder import mic_recorder
from jira import JIRA
from github import Github
from langchain_ollama import ChatOllama
from langchain_core.tools import tool
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage

# ==========================================
# 1. CONFIGURATION (PASTE NEW KEYS HERE)
# ==========================================

st.set_page_config(page_title="DevOps AI Agent", page_icon="🤖", layout="wide")

# --- JIRA SETUP ---
JIRA_URL = "https://sujayc331.atlassian.net"
JIRA_EMAIL = "sujayc331@gmail.com"
JIRA_TOKEN = "JIRA API"  # <--- SECURITY: PASTE NEW TOKEN

JIRA_PROJECT_KEY = "SCRUM" 

# --- GITHUB SETUP ---
GITHUB_TOKEN = "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" # <--- SECURITY: PASTE NEW TOKEN
GITHUB_REPO_NAME = "CSUJAY/bot-test" # I corrected this to the one that worked previously

# --- USER MAPPING ---
USER_MAP = {
    "me": "712020:54d95681-3f71-4359-bf71-8a8a34712476",
    "sujay": "712020:54d95681-3f71-4359-bf71-8a8a34712476",
}

# ==========================================
# 2. SETUP (TOOLS & AI)
# ==========================================

@st.cache_resource
def init_clients():
    try:
        j = JIRA(server=JIRA_URL, basic_auth=(JIRA_EMAIL, JIRA_TOKEN))
        g = Github(GITHUB_TOKEN)
        r = g.get_repo(GITHUB_REPO_NAME)
        return j, r, None
    except Exception as e:
        return None, None, str(e)

jira_client, repo, err = init_clients()

@st.cache_resource
def load_whisper():
    return whisper.load_model("base") 

whisper_model = load_whisper()

# --- DEFINE TOOLS ---
@tool
def create_jira_task(summary: str, description: str, priority: str = "Medium", assignee_name: str = "me"):
    """Creates a Jira Task. Priority defaults to Medium."""
    if not priority: priority = "Medium"
    if not summary: summary = "Task created by AI"
    
    account_id = USER_MAP.get(assignee_name.lower())
    
    issue_dict = {
        'project': {'key': JIRA_PROJECT_KEY},
        'summary': summary,
        'description': description,
        'issuetype': {'name': 'Task'},
        'priority': {'name': priority},
    }
    if account_id: issue_dict['assignee'] = {'id': account_id}

    try:
        new_issue = jira_client.create_issue(fields=issue_dict)
        return f"✅ Jira Ticket Created: {new_issue.key}"
    except Exception as e:
        return f"❌ Error: {e}"

@tool
def create_github_issue(title: str, body: str, labels: str = ""):
    """Creates a GitHub Issue."""
    label_list = [l.strip() for l in labels.split(",")] if labels else []
    gh_labels = []
    for l in label_list:
        try: gh_labels.append(repo.get_label(l))
        except: pass 

    try:
        issue = repo.create_issue(title=title, body=body, labels=gh_labels)
        return f"✅ GitHub Issue Created: #{issue.number}"
    except Exception as e:
        return f"❌ Error: {e}"

@tool
def read_file_content(file_path: str):
    """Reads local code file."""
    try:
        if not os.path.exists(file_path): return f"❌ Error: File '{file_path}' not found."
        with open(file_path, 'r', encoding='utf-8') as f: return f.read()[:2000]
    except Exception as e: return f"Error reading file: {e}"

# --- NEW HELPER: GIT DIFF ---
def get_git_diff():
    """Gets the changes you made but haven't committed yet."""
    try:
        # Check unstaged changes
        result = subprocess.check_output(["git", "diff"], encoding="utf-8")
        if not result:
            # Check staged changes
            result = subprocess.check_output(["git", "diff", "--cached"], encoding="utf-8")
        return result
    except Exception as e:
        return f"Error running git diff: {e}"

# --- AI SETUP ---
llm = ChatOllama(model="llama3.2", temperature=0)
llm_with_tools = llm.bind_tools([create_jira_task, create_github_issue, read_file_content])

# ==========================================
# 3. UI LOGIC
# ==========================================

st.title("🤖 Local DevOps Agent")
if err: st.error(err)

if "messages" not in st.session_state:
    st.session_state.messages = [SystemMessage(content="You are Jarvis. Map 'me' to Sujay.")]

# --- SIDEBAR CONTROL PANEL ---
with st.sidebar:
    st.header("🎮 Controls")
    
    # 1. VOICE CONTROL
    st.subheader("🎤 Voice Command")
    audio = mic_recorder(start_prompt="⏺️ Record", stop_prompt="⏹️ Stop", key='recorder')
    
    st.divider()
    
    # 2. CODE REVIEW BUTTON (NEW FEATURE)
    st.subheader("🕵️ AI Code Review")
    if st.button("Review My Changes"):
        with st.spinner("Analyzing your code..."):
            # Get the changes from Git
            diff = get_git_diff()
            if not diff:
                st.warning("No changes detected. Did you save and edit a file?")
                review_prompt = None
            else:
                review_prompt = f"Please review this code change and look for bugs or security issues:\n\n{diff}"
                
                # We send this directly to the AI
                st.session_state.messages.append(HumanMessage(content=review_prompt))
                
                # Force AI generation
                with st.chat_message("assistant"):
                    ai_response = llm.invoke([HumanMessage(content=review_prompt)])
                    st.write(ai_response.content)
                    st.session_state.messages.append(ai_response)
    
    st.divider()
    st.caption(f"Repo: {GITHUB_REPO_NAME}")

# --- MAIN CHAT LOGIC ---
voice_text = None
if audio:
    with open("temp_audio.wav", "wb") as f: f.write(audio['bytes'])
    voice_text = whisper_model.transcribe("temp_audio.wav")["text"]

# Input Handling
user_prompt = None
if voice_text: user_prompt = voice_text
elif chat_input := st.chat_input("Type here..."): user_prompt = chat_input

# Display History
for msg in st.session_state.messages:
    if isinstance(msg, HumanMessage):
        with st.chat_message("user"): st.write(msg.content)
    elif isinstance(msg, AIMessage):
        with st.chat_message("assistant"): st.write(msg.content)

# Process New Message
if user_prompt:
    # Avoid duplicate voice processing
    last_msg = st.session_state.messages[-1]
    if not (isinstance(last_msg, HumanMessage) and last_msg.content == user_prompt):
        
        st.session_state.messages.append(HumanMessage(content=user_prompt))
        if voice_text:
            with st.chat_message("user"): st.write(user_prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                ai_response = llm_with_tools.invoke(st.session_state.messages)
                st.session_state.messages.append(ai_response)
                if ai_response.content: st.write(ai_response.content)

                if ai_response.tool_calls:
                    for tool_call in ai_response.tool_calls:
                        tool_name = tool_call["name"]
                        args = tool_call["args"]
                        with st.status(f"⚙️ Running {tool_name}...", expanded=True):
                            if tool_name == "create_jira_task": res = create_jira_task.invoke(args)
                            elif tool_name == "create_github_issue": res = create_github_issue.invoke(args)
                            elif tool_name == "read_file_content": res = read_file_content.invoke(args)
                            st.write(res)
                        st.session_state.messages.append(HumanMessage(content=f"Tool Output: {res}"))

def test_function():
    # I am dividing by zero to crash the app
    print(10 / 0)
