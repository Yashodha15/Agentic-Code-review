import os
import sys
import json
import requests
from typing import List, Dict, Any
from pydantic import BaseModel, Field
from langchain_anthropic import ChatAnthropic
from langgraph.graph import StateGraph, END, START

# =====================================================================
# 1. MODEL CONFIGURATION
# =====================================================================
MODEL_NAME = "claude-sonnet-5"

# =====================================================================
# 2. DATA MODELS & STATE SETUP
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
# 3. GITHUB CONTEXT UTILITIES
# =====================================================================

def get_pr_diff() -> str:
    """Reads the pre-downloaded local git diff text file."""
    if not os.path.exists("pr_diff.txt"):
        print("Error: pr_diff.txt not found locally!")
        sys.exit(1)
        
    with open("pr_diff.txt", "r", encoding="utf-8") as f:
        content = f.read()
    return content

# =====================================================================
# 4. SPECIALIZED SUB-AGENT NODES
# =====================================================================

def security_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model=MODEL_NAME).with_structured_output(AgentOutput)
    prompt = (
        "You are an expert Security Sentinel. Analyze this git diff for vulnerabilities, "
        "hardcoded secrets, injection flaws, or improper error handling that leaks data.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    return {"security_findings": [f.model_dump() for f in result.findings]}

def bug_hunter_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model=MODEL_NAME).with_structured_output(AgentOutput)
    prompt = (
        "You are an expert Bug Hunter. Analyze this git diff for logical flaws, "
        "race conditions, edge cases, null pointer exceptions, or off-by-one errors.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    return {"bug_findings": [f.model_dump() for f in result.findings]}

def style_agent(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model=MODEL_NAME).with_structured_output(AgentOutput)
    prompt = (
        "You are a Style and Pattern Architect. Analyze this git diff for readability, "
        "naming consistency, missing documentation, or violations of clean code standards.\n\n"
        f"Diff:\n{state['diff']}"
    )
    result = llm.invoke(prompt)
    # FIX: Corrected iteration loop variable naming mismatch (m -> f)
    return {"style_findings": [f.model_dump() for f in result.findings]}

# =====================================================================
# 5. SYNTHESIZER NODE & GITHUB OUTPUT
# =====================================================================

def synthesizer_node(state: ReviewState) -> Dict:
    llm = ChatAnthropic(model=MODEL_NAME)
    
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
    
    url = f"https://github.com{repo}/issues/{pr_num}/comments"
    print(f"Posting final comment to: {url}")
    
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json"
    }
    body = {"body": f"### 🤖 Multi-Agent AI Code Review Report\n\n{report}"}
    
    res = requests.post(url, headers=headers, json=body)
    if res.status_code == 201:
        print("Successfully posted multi-agent review to GitHub!")
    else:
        print(f"Failed to post comment to GitHub API (Status {res.status_code}): {res.text}")

# =====================================================================
# 6. ORCHESTRATION PIPELINE DEFINITION
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
    
    builder.add_edge(START, "security_agent")
    builder.add_edge(START, "bug_hunter_agent")
    builder.add_edge(START, "style_agent")
    
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
    
    print(f"Initiating execution using verified model: {MODEL_NAME}...")
    final_output = graph.invoke(initial_state)
    print("Publishing report findings...")
    post_github_comment(final_output["final_report"])

if __name__ == "__main__":
    main()
