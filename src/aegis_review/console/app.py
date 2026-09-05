"""Streamlit engineering console for Code Review.

The Angular application remains the product dashboard. This console is a
Python-native operations surface for inspecting agent runs, findings, traces,
and review policy without adding maintenance concerns to the product UI.
"""

from __future__ import annotations

import html
import json
import os
from collections import Counter
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

import streamlit as st

from aegis_review.console.presentation import agent_lanes, badge


API_URL = os.getenv("AEGIS_API_URL", "http://127.0.0.1:8000").rstrip("/")


def api_request(path: str, *, method: str = "GET", payload: dict[str, Any] | None = None) -> Any:
    """Call the private API and return decoded JSON with a useful UI error."""

    body = json.dumps(payload).encode() if payload is not None else None
    request = Request(
        f"{API_URL}{path}",
        data=body,
        method=method,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urlopen(request, timeout=15) as response:  # noqa: S310 - configured internal URL
            return json.load(response)
    except (HTTPError, URLError, TimeoutError) as error:
        raise RuntimeError(f"API request failed: {error}") from error


def apply_theme() -> None:
    """Apply the console's intentionally compact, dark operations theme."""

    st.markdown(
        """
        <style>
        .stApp { background: #090d16; color: #e8edf7; }
        [data-testid="stSidebar"] { background: #0d1320; border-right: 1px solid #202b3d; }
        [data-testid="stHeader"] { background: rgba(9, 13, 22, .82); }
        .block-container { max-width: 1440px; padding-top: 2.2rem; }
        h1, h2, h3 { letter-spacing: -.025em; }
        .eyebrow { color: #7296d8; font-size: .72rem; font-weight: 700; letter-spacing: .13em; text-transform: uppercase; }
        .muted { color: #8d9ab0; }
        .card, .agent-card { background: linear-gradient(145deg, #121927, #0f1521); border: 1px solid #263247; border-radius: 14px; padding: 1rem; }
        .agent-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: .8rem; margin: 1rem 0; }
        .agent-card h4 { margin: .2rem 0 .6rem; text-transform: capitalize; }
        .subagent { border-left: 2px solid #2f6feb; color: #b9c5d9; margin: .45rem 0; padding-left: .65rem; }
        .badge { background: #202a3a; border-radius: 999px; color: #aab7cb; display: inline-block; font-size: .68rem; font-weight: 700; padding: .22rem .55rem; text-transform: uppercase; }
        .completed, .verified, .low { background: #123724; color: #70dfa1; }
        .running, .medium { background: #143250; color: #7bbbf7; }
        .high { background: #4c2d12; color: #ffbd68; }
        .critical, .failed { background: #4a1925; color: #ff849d; }
        .queued { background: #172d50; color: #8bb8ff; }
        .metric-row { color: #8d9ab0; font-size: .82rem; margin-top: .75rem; }
        div[data-testid="stExpander"] { background: #101722; border-color: #263247; border-radius: 12px; }
        code { color: #a9c7ff !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_overview(reviews: list[dict[str, Any]]) -> None:
    """Render fleet-level review health and the recent review table."""

    st.markdown('<div class="eyebrow">Engineering console</div>', unsafe_allow_html=True)
    st.title("Review operations")
    st.caption("Monitor GitHub reviews, agent execution, and policy from one place.")

    statuses = Counter(review["status"] for review in reviews)
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Total reviews", len(reviews))
    col2.metric("Running", statuses["running"] + statuses["queued"])
    col3.metric("Completed", statuses["completed"])
    col4.metric("Findings", sum(review.get("finding_count", 0) for review in reviews))

    st.subheader("Recent reviews")
    if not reviews:
        st.info("No reviews have been received yet.")
        return
    st.dataframe(
        [
            {
                "Repository / PR": f'{review["repository"]} #{review["pull_request_number"]}',
                "Status": review["status"],
                "Findings": review.get("finding_count", 0),
                "Agents": len(review.get("completed_agents", [])),
                "Updated": review["updated_at"],
                "Review ID": review["id"],
            }
            for review in reviews
        ],
        use_container_width=True,
        hide_index=True,
    )


def render_review(review: dict[str, Any]) -> None:
    """Render one review, including its graph, findings, and raw event trace."""

    review_id = review["id"]
    traces = api_request(f"/api/v1/reviews/{review_id}/traces")
    findings = api_request(f"/api/v1/reviews/{review_id}/findings")
    lanes = agent_lanes(traces, findings)

    st.markdown('<div class="eyebrow">Agent execution</div>', unsafe_allow_html=True)
    st.title(f'{review["repository"]} #{review["pull_request_number"]}')
    st.caption(f'Commit {review["head_sha"][:10]} · Review {review_id}')

    cols = st.columns(4)
    cols[0].metric("Status", review["status"].title())
    cols[1].metric("Lead agents", len(lanes))
    cols[2].metric("Subagents", sum(len(lane["subagents"]) for lane in lanes))
    cols[3].metric("Findings", len(findings))

    st.subheader("Parallel agent graph")
    cards = []
    for lane in lanes:
        children = "".join(
            f'<div class="subagent">↳ {html.escape(child["stage"].split(".", 1)[-1])} {badge(child["status"])}</div>'
            for child in lane["subagents"]
        ) or '<div class="muted">No subagents spawned</div>'
        cards.append(
            f'<div class="agent-card"><div class="eyebrow">Lead agent</div>'
            f'<h4>{html.escape(lane["name"])}</h4>{badge(lane["status"])}'
            f'<div class="metric-row">{len(lane["subagents"])} spawned · {lane["finding_count"]} findings</div>'
            f'<hr style="border-color:#263247;border-width:1px 0 0;margin:.8rem 0">{children}</div>'
        )
    st.markdown(
        '<div class="card" style="text-align:center">Webhook → Queue → Worker → Planning → '
        '<strong style="color:#8ab4ff">Parallel fan-out</strong></div>'
        f'<div class="agent-grid">{"".join(cards)}</div>'
        '<div class="card" style="text-align:center"><strong>Join + validation</strong> → Publish</div>',
        unsafe_allow_html=True,
    )

    st.subheader("Verified findings")
    if not findings:
        st.success("No verified findings were published.")
    for index, finding in enumerate(findings):
        label = f'{finding["severity"].upper()} · {finding["title"]} · {finding["path"]}:{finding["line"]}'
        with st.expander(label, expanded=index == 0):
            st.markdown(
                f'{badge(finding["severity"])} &nbsp; {badge(finding["status"])} &nbsp; '
                f'**{html.escape(finding["category"])}** · confidence {finding["confidence"]:.0%}',
                unsafe_allow_html=True,
            )
            st.write(finding["comment"])
            if finding.get("evidence"):
                st.markdown("**Evidence**")
                for evidence in finding["evidence"]:
                    st.code(evidence)
            if finding.get("suggested_fix"):
                st.markdown("**Suggested fix**")
                st.write(finding["suggested_fix"])

    with st.expander(f"Execution timeline ({len(traces)} events)"):
        st.dataframe(traces, use_container_width=True, hide_index=True)
    if review.get("errors"):
        st.error("\n".join(review["errors"]))


def render_policy() -> None:
    """Render an editable policy form backed by the platform API."""

    policy = api_request("/api/v1/policy")
    st.markdown('<div class="eyebrow">Configuration</div>', unsafe_allow_html=True)
    st.title("Review policy")
    st.caption("Changes take effect for newly queued reviews.")

    severities = ["low", "medium", "high", "critical"]
    with st.form("policy"):
        minimum = st.selectbox(
            "Minimum severity",
            severities,
            index=severities.index(policy["minimum_severity"]),
        )
        verified = st.toggle("Require verified findings", policy["require_verified_findings"])
        block = st.toggle("Block on critical findings", policy["block_on_critical_findings"])
        reproduce = st.toggle("Allow reproduction tests", policy["allow_reproduction_tests"])
        ignored = st.text_area("Ignored paths (one per line)", "\n".join(policy["ignored_paths"]))
        limits = policy["limits"]
        col1, col2, col3 = st.columns(3)
        specialists = col1.number_input("Max specialists", 1, 20, limits["maximum_specialist_agents"])
        subagents = col2.number_input("Max subagents", 1, 50, limits["maximum_subagents"])
        runtime = col3.number_input("Runtime seconds", 30, 3600, limits["maximum_runtime_seconds"])
        col4, col5, col6 = st.columns(3)
        depth = col4.number_input("Delegation depth", 1, 4, limits["maximum_delegation_depth"])
        comments = col5.number_input("Max comments", 1, 50, limits["maximum_comments"])
        cost = col6.number_input(
            "Estimated cost ceiling (USD)",
            min_value=0.01,
            max_value=100.0,
            value=float(limits["maximum_cost_usd"]),
            step=0.25,
        )
        submitted = st.form_submit_button("Save policy", type="primary")
    if submitted:
        policy.update(
            minimum_severity=minimum,
            require_verified_findings=verified,
            block_on_critical_findings=block,
            allow_reproduction_tests=reproduce,
            ignored_paths=[line.strip() for line in ignored.splitlines() if line.strip()],
        )
        policy["limits"].update(
            maximum_specialist_agents=int(specialists),
            maximum_subagents=int(subagents),
            maximum_runtime_seconds=int(runtime),
            maximum_delegation_depth=int(depth),
            maximum_comments=int(comments),
            maximum_cost_usd=float(cost),
        )
        api_request("/api/v1/policy", method="PUT", payload=policy)
        st.success("Policy saved.")


def main() -> None:
    """Start the console and route between its operational views."""

    st.set_page_config(page_title="Code Review Operations", page_icon="◈", layout="wide")
    apply_theme()
    st.sidebar.title("◈ Code Review")
    st.sidebar.caption("Engineering operations")
    # Streamlit is a separate application, so Angular's router cannot provide
    # an automatic in-app back action. This explicit link always returns home.
    st.sidebar.link_button(
        "← Back to Angular dashboard",
        "/",
        use_container_width=True,
    )
    page = st.sidebar.radio("Workspace", ["Overview", "Review inspector", "Policy"])
    if st.sidebar.button("Refresh data", use_container_width=True):
        st.rerun()

    try:
        reviews = api_request("/api/v1/reviews?limit=100")
        if page == "Overview":
            render_overview(reviews)
        elif page == "Policy":
            render_policy()
        elif not reviews:
            st.info("No reviews are available to inspect.")
        else:
            options = {
                f'{item["repository"]} #{item["pull_request_number"]} · {item["head_sha"][:8]}': item
                for item in reviews
            }
            selected = st.sidebar.selectbox("Review", list(options))
            render_review(options[selected])
    except RuntimeError as error:
        st.error(str(error))
        st.info(f"Expected API: {API_URL}")


if __name__ == "__main__":
    main()
