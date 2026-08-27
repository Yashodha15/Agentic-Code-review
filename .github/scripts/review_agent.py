import os
import sys
import json
import requests
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END

# =====================================================================
# 1. DATA MODELS & STATE SETUP
# =====================================================================

class ReviewFinding(BaseModel):
    line: int = Field(description="The specific line number in the diff where the issue occurs.")
    category: str = Field(description="Category of the finding: 'Security', 'Bug', or 'Style'")
    comment: str = Field(description="Actionable, direct feedback explaining the issue and fix.")

class AgentOutput(BaseModel):
    findings: List[ReviewFinding] = Field(default_factory=list)

class ReviewState(Dict[str, Any]):
    diff: str
    security_findings: List[Dict]
    bug_findings: List[Dict]
    style_findings: List[Dict]
    final_report: str

# =====================================================================
# 2. GITHUB CONTEXT UTILITIES (FIXED URL PATHS)
# =====================================================================

def get_pr_diff() -> str:
    """Fetches the raw git diff text for the target pull request."""
    repo = os.getenv("REPO_NAME")
    pr_num = os.getenv("PR_NUMBER")
    token = os.getenv("GITHUB_TOKEN")
    
    if not all([repo, pr_num, token]):
        print("Missing required environment variables.")
        sys.exit(1)
        
    # FIX: Explicit full API base domain path
    url = f"https://github.com{repo}/pulls/{pr_num}"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3.diff"
    }
    
    response = requests.get(url, headers=headers)
    if response.status_code != 200:
        print(f"Failed to fetch diff from GitHub API: {response.text}")
        sys.exit(1)
    return response.text

# =====================================================================
# 3. SPECIALIZED SUB-AGENT NODES
# =====================================================================

def security_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0).with_structured_output(AgentOutput)
    prompt = (
        "You are an expert Security Sentinel. Analyze this git diff for vulnerabilities, "
        "hardcoded secrets, injection flaws, or improper error handling that leaks data.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    return {"security_findings": [f.model_dump() for f in result.findings]}

def bug_hunter_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0).with_structured_output(AgentOutput)
    prompt = (
        "You are an expert Bug Hunter. Analyze this git diff for logical flaws, "
        "race conditions, edge cases, null pointer exceptions, or off-by-one errors.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    return {"bug_findings": [f.model_dump() for f in result.findings]}

def style_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0).with_structured_output(AgentOutput)
    prompt = (
        "You are a Style and Pattern Architect. Analyze this git diff for readability, "
        "naming consistency, missing documentation, or violations of clean code standards.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    return {"style_findings": [f.model_dump() for f in result.findings]}

# =====================================================================
# 4. SYNTHESIZER NODE & GITHUB OUTPUT
# =====================================================================

def synthesizer_node(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model="claude-3-5-sonnet-latest", temperature=0.2)
    
    all_findings = {
        "Security": state.get("security_findings", []),
        "Bugs": state.get("bug_findings", []),
        "Style": state.get("style_findings", [])
    }
    
    prompt = (
        "You are the Lead Engineer Synthesizer. Review the findings gathered by your specialized sub-agents. "
        "Deduplicate any overlapping issues, remove minor false positives, and compile them into a unified, "
        "highly readable markdown review report. Organize your output by file/line if apparent, or provide clear structural recommendations.\n\n"
        f"Sub-Agent Raw Findings:\n{json.dumps(all_findings, indent=2)}"
    )
    
    response = llm.invoke(prompt)
    return {"final_report": response.content}

def post_github_comment(report: str):
    """Sends the consolidated review dashboard back to the active pull request pipeline."""
    repo = os.getenv("REPO_NAME")
    pr_num = os.getenv("PR_NUMBER")
    token = os.getenv("GITHUB_TOKEN")
    
    # FIX: Explicit full API base domain path
    url = f"https://github.com{repo}/issues/{pr_num}/comments"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    body = {"body": f"### 🤖 Multi-Agent AI Code Review Report (Claude)\n\n{report}"}
    
    res = requests.post(url, headers=headers, json=body)
    if res.status_code == 201:
        print("Successfully posted multi-agent review to GitHub!")
    else:
        print(f"Failed to post comment to GitHub API: {res.text}")

# =====================================================================
# 5. ORCHESTRATION PIPELINE DEFINITION
# =====================================================================

def main():
    diff_content = get_pr_diff()
    if not diff_content.strip():
        print("Diff content is empty. Skipping review processing loop.")
        return

    builder = StateGraph(ReviewState)
    builder.add_node("security_agent", security_agent)
    builder.add_node("bug_hunter_agent", bug_hunter_agent)
    builder.add_node("style_agent", style_agent)
    builder.add_node("synthesizer", synthesizer_node)
    
    builder.set_entry_point(["security_agent", "bug_hunter_agent", "style_agent"])
    builder.add_edge("security_agent", "synthesizer")
    builder.add_edge("bug_hunter_agent", "synthesizer")
    builder.add_edge("style_agent", "synthesizer")
    builder.add_edge("synthesizer", END)
    
    graph = builder.compile()
    initial_state = {
        "diff": diff_content,
        "security_findings": [],
        "bug_findings": [],
        "style_findings": [],
        "final_report": ""
    }
    
    print("Initiating execution...")
    final_output = graph.invoke(initial_state)
    print("Publishing report findings...")
    post_github_comment(final_output["final_report"])

if __name__ == "__main__":
    main()
