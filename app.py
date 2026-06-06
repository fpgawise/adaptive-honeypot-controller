import json
import random
import re
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

try:
    import google.generativeai as genai
except ImportError:
    genai = None


PHASES = [
    "scanning",
    "brute_force",
    "exploit",
    "persistence",
    "data_exfiltration",
    "dormant",
]

PHASE_COLORS = {
    "scanning": "#FFD700",
    "brute_force": "#FF6B6B",
    "exploit": "#FF4444",
    "persistence": "#C1121F",
    "data_exfiltration": "#780000",
    "dormant": "#808080",
}

PHASE_ICONS = {
    "scanning": "🔍",
    "brute_force": "🔐",
    "exploit": "💥",
    "persistence": "🔧",
    "data_exfiltration": "📤",
    "dormant": "💤",
}


@dataclass
class Attacker:
    id: str
    ip: str
    method: str
    phase: str
    aggression: float
    skill: float
    persistence: float
    failed_attempts: int
    success_count: int
    risk: float
    phase_history: List[Dict]

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "ip": self.ip,
            "method": self.method,
            "phase": self.phase,
            "aggression": self.aggression,
            "skill": self.skill,
            "persistence": self.persistence,
            "failed_attempts": self.failed_attempts,
            "success_count": self.success_count,
            "risk": self.risk,
            "phase_history": self.phase_history,
        }


@dataclass
class Experience:
    state: str
    action: str
    outcome: str
    impact: float
    timestamp: str


class AgentMemory:
    def __init__(self, limit: int = 100):
        self.experiences = deque(maxlen=limit)
        self.results = defaultdict(list)
        self.impacts = defaultdict(list)

    def add(self, exp: Experience):
        self.experiences.append(exp)
        self.results[exp.action].append(exp.outcome)
        self.impacts[exp.action].append(exp.impact)

    def repeated_recently(self, action: str) -> bool:
        recent = list(self.experiences)[-3:]
        return any(exp.action == action for exp in recent)

    def should_avoid(self, action: str) -> bool:
        outcomes = self.results.get(action, [])
        if len(outcomes) < 3:
            return False
        failure_rate = outcomes.count("failed") / len(outcomes)
        recent_average = sum(self.impacts[action][-3:]) / min(3, len(self.impacts[action]))
        return failure_rate > 0.6 or recent_average < 5 or self.repeated_recently(action)

    def stats(self) -> pd.DataFrame:
        rows = []
        for action, outcomes in self.results.items():
            impacts = self.impacts[action]
            rows.append(
                {
                    "action": action,
                    "runs": len(outcomes),
                    "success rate": outcomes.count("success") / len(outcomes),
                    "average impact": sum(impacts) / len(impacts),
                    "avoid next": self.should_avoid(action),
                }
            )
        return pd.DataFrame(rows)


class SimulatedHoneypot:
    def __init__(self):
        self.config = {
            "banner": "SSH-2.0-OpenSSH_7.4",
            "login_delay": 0.5,
            "strategy": "observe",
            "deception_artifacts": [],
        }
        self.attackers: Dict[str, Attacker] = {}
        self.logs: List[str] = []
        self.actions: List[Dict] = []
        self.score_history: List[Dict] = []
        self._add_initial_attackers()
        self.update_scores()

    def now(self) -> str:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def log(self, text: str):
        self.logs.append(f"[{datetime.now().strftime('%H:%M:%S')}] {text}")
        self.logs = self.logs[-300:]

    def _add_initial_attackers(self):
        starters = [
            ("192.168.1.100", "ssh", 0.9, 0.3, 0.8),
            ("10.0.0.45", "web", 0.6, 0.8, 0.7),
            ("172.16.2.88", "generic", 0.4, 0.5, 0.4),
        ]
        for ip, method, aggression, skill, persistence in starters:
            self.add_attacker(ip, method, aggression, skill, persistence)

    def add_attacker(
        self,
        ip: Optional[str] = None,
        method: Optional[str] = None,
        aggression: Optional[float] = None,
        skill: Optional[float] = None,
        persistence: Optional[float] = None,
    ):
        if ip is None:
            ip = f"10.{random.randint(1, 250)}.{random.randint(1, 250)}.{random.randint(1, 250)}"
        if method is None:
            method = random.choice(["ssh", "web", "generic", "api"])

        attacker = Attacker(
            id=str(uuid.uuid4())[:8],
            ip=ip,
            method=method,
            phase="scanning",
            aggression=round(aggression if aggression is not None else random.uniform(0.3, 0.9), 2),
            skill=round(skill if skill is not None else random.uniform(0.2, 0.9), 2),
            persistence=round(persistence if persistence is not None else random.uniform(0.2, 0.9), 2),
            failed_attempts=0,
            success_count=0,
            risk=0.0,
            phase_history=[{"phase": "scanning", "time": self.now()}],
        )
        self.attackers[attacker.id] = attacker
        self.log(f"New attacker detected: {attacker.ip}")

    def update_attackers(self):
        if random.random() < 0.12 and len(self.attackers) < 12:
            self.add_attacker()

        for attacker in self.attackers.values():
            old_phase = attacker.phase
            delay = self.config["login_delay"]
            has_fake_vuln = any(a["type"] == "fake_vuln" for a in self.config["deception_artifacts"])
            has_token = any(a["type"] == "honeytoken" for a in self.config["deception_artifacts"])

            if attacker.phase == "scanning":
                if random.random() < 0.35 * attacker.aggression:
                    attacker.phase = "brute_force"

            elif attacker.phase == "brute_force":
                if delay > 2.5 and random.random() < 0.35:
                    attacker.phase = "dormant"
                elif random.random() < 0.15 * attacker.skill:
                    attacker.success_count += 1
                    attacker.phase = "exploit"

            elif attacker.phase == "exploit":
                if has_fake_vuln:
                    attacker.success_count += 1
                if attacker.success_count >= 2 and random.random() < attacker.persistence:
                    attacker.phase = "persistence"

            elif attacker.phase == "persistence":
                if has_token and random.random() < 0.5:
                    attacker.phase = "data_exfiltration"

            elif attacker.phase == "data_exfiltration":
                if random.random() < 0.2:
                    attacker.phase = "dormant"

            elif attacker.phase == "dormant":
                if random.random() < 0.08 * attacker.persistence:
                    attacker.phase = "scanning"

            attacker.failed_attempts += random.randint(0, 2)
            attacker.risk = self.calculate_attacker_risk(attacker)

            if old_phase != attacker.phase:
                attacker.phase_history.append({"phase": attacker.phase, "time": self.now()})
                self.log(f"{attacker.ip}: {old_phase} -> {attacker.phase}")

        self.update_scores()

    def calculate_attacker_risk(self, attacker: Attacker) -> float:
        base = {
            "scanning": 10,
            "brute_force": 30,
            "exploit": 60,
            "persistence": 85,
            "data_exfiltration": 100,
            "dormant": 5,
        }.get(attacker.phase, 10)
        return round(base * (0.4 * attacker.skill + 0.3 * attacker.aggression + 0.3 * attacker.persistence), 1)

    def phase_counts(self) -> Dict[str, int]:
        counts = defaultdict(int)
        for attacker in self.attackers.values():
            counts[attacker.phase] += 1
        return dict(counts)

    def update_scores(self) -> Dict:
        attackers = list(self.attackers.values())
        active = [a for a in attackers if a.phase != "dormant"]
        risks = [a.risk for a in attackers]
        successful_actions = [a for a in self.actions[-10:] if a.get("result", {}).get("success")]

        scores = {
            "engagement": round(min(100, len(active) * 12), 1),
            "risk": round(sum(risks) / len(risks), 1) if risks else 0,
            "deception": round(max(0, 100 - len(self.config["deception_artifacts"]) * 2), 1),
            "agent": round(50 + (len(successful_actions) / 10) * 50, 1),
        }
        scores["time"] = datetime.now().strftime("%H:%M:%S")
        self.score_history.append(scores)
        self.score_history = self.score_history[-60:]
        return scores

    def deploy_artifact(self, artifact_type: str, content: str) -> Dict:
        artifact = {
            "id": str(uuid.uuid4())[:8],
            "type": artifact_type,
            "content": content,
            "created": self.now(),
            "triggered": False,
        }
        self.config["deception_artifacts"].append(artifact)
        self.log(f"Deployed {artifact_type}: {content[:40]}")
        return artifact

    def apply_action(self, action: Dict) -> Dict:
        action_name = action.get("action", "observe")
        params = action.get("params", {})
        result = {"success": True, "message": "", "impact": round(random.uniform(4, 18), 1)}

        if action_name == "increase_delay":
            amount = float(params.get("amount", 1.0))
            self.config["login_delay"] = round(min(5.0, self.config["login_delay"] + amount), 1)
            result["message"] = f"Login delay is now {self.config['login_delay']} seconds."

        elif action_name == "deploy_fake_vuln":
            endpoint = params.get("endpoint", "/cgi-bin/debug")
            self.deploy_artifact("fake_vuln", endpoint)
            result["message"] = f"Added fake endpoint {endpoint}."

        elif action_name == "deploy_honeytoken":
            token = params.get("token", "fake_api_key=AKIA_TEST_ONLY")
            self.deploy_artifact("honeytoken", token)
            result["message"] = "Added a honeytoken."

        elif action_name == "change_strategy":
            strategy = params.get("strategy", "observe")
            self.config["strategy"] = strategy
            result["message"] = f"Strategy changed to {strategy}."

        elif action_name == "observe":
            result["impact"] = 2.0
            result["message"] = "No change made this cycle."

        else:
            result = {"success": False, "message": f"Unknown action: {action_name}", "impact": 0}

        self.actions.append({"time": self.now(), "action": action_name, "params": params, "result": result})
        self.update_scores()
        return result

    def status(self) -> Dict:
        return {
            "attackers": [a.to_dict() for a in self.attackers.values()],
            "phase_counts": self.phase_counts(),
            "config": self.config,
            "logs": self.logs[-25:],
            "scores": self.score_history[-1] if self.score_history else self.update_scores(),
        }


class HoneypotAgent:
    def __init__(self, honeypot: SimulatedHoneypot, api_key: str = ""):
        self.honeypot = honeypot
        self.memory = AgentMemory()
        self.trace: List[Dict] = []
        self.model = None

        if api_key and genai is not None:
            try:
                genai.configure(api_key=api_key)
                self.model = genai.GenerativeModel("gemini-3.5-flash")
            except Exception as exc:
                self.honeypot.log(f"Gemini setup failed: {exc}")

    def choose_action(self, state: Dict) -> Dict:
        if self.model is not None:
            decision = self.ask_gemini(state)
            if decision:
                return decision
        return self.rule_based_action(state)

    def ask_gemini(self, state: Dict) -> Optional[Dict]:
        prompt = f"""
You are helping control a simulated honeypot for a class project.

Current state:
{json.dumps(state, indent=2)[:1000]}

Choose one action from this list:
- increase_delay: params {{"amount": 1.0}}
- deploy_fake_vuln: params {{"endpoint": "/cgi-bin/debug"}}
- deploy_honeytoken: params {{"token": "fake_api_key=TEST_ONLY"}}
- change_strategy: params {{"strategy": "observe" or "delay" or "deceive"}}
- observe: params {{}}

Return only JSON in this format:
{{"reasoning": "short reason", "action": "action_name", "params": {{}}}}
"""
        try:
            response = self.model.generate_content(prompt)
            match = re.search(r"\{.*\}", response.text, re.DOTALL)
            if match:
                decision = json.loads(match.group())
                if "action" in decision and "params" in decision:
                    return decision
        except Exception as exc:
            self.honeypot.log(f"Gemini call failed: {exc}")
        return None

    def rule_based_action(self, state: Dict) -> Dict:
        phases = state["phase_counts"]

        if phases.get("data_exfiltration", 0) or phases.get("persistence", 0):
            action = "deploy_honeytoken"
            if not self.memory.should_avoid(action):
                return {
                    "reasoning": "Later-stage activity is present, so a honeytoken may help track it.",
                    "action": action,
                    "params": {"token": "fake_cloud_key=TEST_ONLY"},
                }

        if phases.get("exploit", 0):
            action = "deploy_fake_vuln"
            if not self.memory.should_avoid(action):
                return {
                    "reasoning": "Exploit behavior is present, so a fake endpoint may keep the attacker engaged.",
                    "action": action,
                    "params": {"endpoint": "/api/debug"},
                }

        if phases.get("brute_force", 0):
            action = "increase_delay"
            if not self.memory.should_avoid(action):
                return {
                    "reasoning": "Brute force attempts are active, so slowing login responses is reasonable.",
                    "action": action,
                    "params": {"amount": 1.0},
                }

        return {
            "reasoning": "No major escalation is visible, so the agent will observe for one cycle.",
            "action": "observe",
            "params": {},
        }

    def run_cycle(self) -> Dict:
        cycle_number = len(self.trace) + 1
        state = self.honeypot.status()
        decision = self.choose_action(state)
        result = self.honeypot.apply_action(decision)
        self.honeypot.update_attackers()

        impact = float(result.get("impact", 0))
        if result.get("success") and impact >= 10:
            outcome = "success"
        elif result.get("success"):
            outcome = "partial"
        else:
            outcome = "failed"

        self.memory.add(
            Experience(
                state=str(state.get("phase_counts", {})),
                action=decision.get("action", "observe"),
                outcome=outcome,
                impact=impact,
                timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            )
        )

        record = {
            "cycle": cycle_number,
            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "state": state,
            "decision": decision,
            "result": result,
            "outcome": outcome,
        }
        self.trace.append(record)
        return record


def build_report(honeypot: SimulatedHoneypot, agent: HoneypotAgent) -> Path:
    output_dir = Path("reports")
    output_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"honeypot_report_{stamp}.txt"
    logs_path = output_dir / f"honeypot_logs_{stamp}.json"

    stats = agent.memory.stats()
    stats_text = "No action history yet."
    if not stats.empty:
        stats_text = stats.to_string(index=False)

    report = f"""
Adaptive Honeypot Controller Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Project goal
This project simulates a small honeypot and uses an agent loop to decide how to respond to attacker
behavior. The simulation does not connect to real systems.

What the program did
- Tracked {len(honeypot.attackers)} simulated attackers.
- Ran {len(agent.trace)} decision cycles.
- Stored {len(agent.memory.experiences)} memory records.
- Deployed {len(honeypot.config['deception_artifacts'])} deception artifacts.

Agent loop
1. Observe the current attacker phases.
2. Choose a response with Gemini API when available, otherwise use rule-based logic.
3. Apply the response to the honeypot configuration.
4. Update attacker behavior and save the result.

What worked well
- The agent adjusted the honeypot based on attacker phase.
- Brute force behavior usually led to longer login delays.
- Exploit and later-stage behavior led to fake endpoints or honeytokens.
- The dashboard made the decisions and score changes easier to review.

What did not work well
- This is still a simulation, so the attacker behavior is simplified.
- The scoring system is approximate and not based on real logs.
- Gemini API failures fall back to rules, so not every run uses the API.
- The memory does not persist after restarting the app.

Action summary
{stats_text}
"""

    report_path.write_text(report)
    logs_path.write_text(json.dumps({"trace": agent.trace, "status": honeypot.status()}, indent=2))
    return report_path


def reset_app(api_key: str = ""):
    st.session_state.honeypot = SimulatedHoneypot()
    st.session_state.agent = HoneypotAgent(st.session_state.honeypot, api_key)


def init_app():
    if "api_key" not in st.session_state:
        st.session_state.api_key = ""
    if "honeypot" not in st.session_state:
        reset_app("")


def attacker_table(attackers: List[Dict]) -> pd.DataFrame:
    rows = []
    for attacker in attackers:
        rows.append(
            {
                "IP": attacker["ip"],
                "Method": attacker["method"],
                "Phase": attacker["phase"],
                "Risk": attacker["risk"],
                "Aggression": attacker["aggression"],
                "Skill": attacker["skill"],
                "Failures": attacker["failed_attempts"],
                "Successes": attacker["success_count"],
            }
        )
    return pd.DataFrame(rows)


def draw_phase_chart(phase_counts: Dict[str, int]):
    labels = list(phase_counts.keys())
    values = list(phase_counts.values())
    colors = [PHASE_COLORS.get(label, "#999999") for label in labels]
    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.45,
                marker=dict(colors=colors),
                textinfo="label+percent",
            )
        ]
    )
    fig.update_layout(height=360, margin=dict(l=10, r=10, t=20, b=20))
    st.plotly_chart(fig, width="stretch")


def draw_score_chart(history: List[Dict]):
    if not history:
        st.info("Run a cycle to collect scores.")
        return

    df = pd.DataFrame(history)
    fig = go.Figure()
    for column in ["engagement", "risk", "deception", "agent"]:
        if column in df.columns:
            fig.add_trace(go.Scatter(y=df[column], mode="lines+markers", name=column.title()))
    fig.update_layout(height=360, yaxis=dict(range=[0, 100]), margin=dict(l=10, r=10, t=20, b=20))
    st.plotly_chart(fig, width="stretch")


def show_cards(attackers: List[Dict]):
    cols = st.columns(min(3, len(attackers)))
    for index, attacker in enumerate(attackers[:6]):
        phase = attacker["phase"]
        with cols[index % len(cols)]:
            st.markdown(
                f"""
                <div style="border: 1px solid {PHASE_COLORS.get(phase, '#777')}; border-radius: 8px; padding: 12px; margin-bottom: 10px;">
                    <b>{PHASE_ICONS.get(phase, '')} {attacker['ip']}</b><br>
                    Phase: {phase}<br>
                    Method: {attacker['method']}<br>
                    Risk: {attacker['risk']}<br>
                    Failed attempts: {attacker['failed_attempts']}
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_dashboard():
    st.set_page_config(page_title="Honeypot Dashboard", page_icon="🛡️", layout="wide")
    init_app()

    st.title("Honeypot Controller")
    st.caption("Simulated environment for testing an observe, decide, act, evaluate loop.")

    with st.sidebar:
        st.header("Controls")
        api_key = st.text_input("Gemini API key", value=st.session_state.api_key, type="password")
        if api_key != st.session_state.api_key:
            st.session_state.api_key = api_key

        if st.button("Apply API key / reset", width="stretch"):
            reset_app(st.session_state.api_key)
            st.rerun()

        st.divider()

        if st.button("Run 1 cycle", width="stretch"):
            st.session_state.agent.run_cycle()
            st.rerun()

        if st.button("Run 5 cycles", width="stretch"):
            for _ in range(5):
                st.session_state.agent.run_cycle()
            st.rerun()

        if st.button("Update attackers only", width="stretch"):
            st.session_state.honeypot.update_attackers()
            st.rerun()

        if st.button("Add random attacker", width="stretch"):
            st.session_state.honeypot.add_attacker()
            st.session_state.honeypot.update_scores()
            st.rerun()

        if st.button("Generate report", width="stretch"):
            path = build_report(st.session_state.honeypot, st.session_state.agent)
            st.success(f"Saved: {path}")

    honeypot = st.session_state.honeypot
    agent = st.session_state.agent
    state = honeypot.status()
    scores = state["scores"]

    metric_cols = st.columns(5)
    metric_cols[0].metric("Attackers", len(state["attackers"]))
    metric_cols[1].metric("Risk", scores["risk"])
    metric_cols[2].metric("Engagement", scores["engagement"])
    metric_cols[3].metric("Deception", scores["deception"])
    metric_cols[4].metric("Agent", scores["agent"])

    tab_dashboard, tab_cycles, tab_memory, tab_deception, tab_export = st.tabs(
        ["Dashboard", "Cycles", "Memory", "Deception", "Export"]
    )

    with tab_dashboard:
        left, right = st.columns(2)
        with left:
            st.subheader("Attacker phases")
            draw_phase_chart(state["phase_counts"])
        with right:
            st.subheader("Scores")
            draw_score_chart(honeypot.score_history)

        st.subheader("Attackers")
        show_cards(state["attackers"])
        with st.expander("Show attacker table"):
            st.dataframe(attacker_table(state["attackers"]), width="stretch")

        st.subheader("Event log")
        st.code("\n".join(state["logs"]) or "No events yet.", language="text")

    with tab_cycles:
        st.subheader("Recent cycles")
        if not agent.trace:
            st.info("Run a cycle to see decisions here.")
        for cycle in reversed(agent.trace[-10:]):
            with st.expander(f"Cycle {cycle['cycle']} - {cycle['time']}"):
                st.write("Reason:", cycle["decision"].get("reasoning", ""))
                st.json({"action": cycle["decision"].get("action"), "params": cycle["decision"].get("params", {})})
                st.write("Result:", cycle["result"].get("message", ""))
                st.write("Outcome:", cycle["outcome"])

    with tab_memory:
        st.subheader("Action results")
        stats = agent.memory.stats()
        if stats.empty:
            st.info("No memory records yet.")
        else:
            st.dataframe(stats, width="stretch")

        st.subheader("Recent memory records")
        for exp in list(agent.memory.experiences)[-8:]:
            st.write(f"{exp.timestamp}: {exp.action} -> {exp.outcome}, impact {exp.impact}")

    with tab_deception:
        st.subheader("Add deception artifact")
        col1, col2 = st.columns(2)
        with col1:
            artifact_type = st.selectbox("Type", ["fake_vuln", "honeytoken", "breadcrumb", "fake_file"])
        with col2:
            content = st.text_input("Content", "/api/debug")
        if st.button("Deploy", width="stretch"):
            honeypot.deploy_artifact(artifact_type, content)
            honeypot.update_scores()
            st.rerun()

        artifacts = honeypot.config["deception_artifacts"]
        if artifacts:
            st.dataframe(pd.DataFrame(artifacts), width="stretch")
        else:
            st.info("No deception artifacts deployed yet.")

    with tab_export:
        st.subheader("Download data")
        st.download_button(
            "Download cycle trace",
            json.dumps(agent.trace, indent=2),
            file_name="cycle_trace.json",
            mime="application/json",
        )
        st.download_button(
            "Download current status",
            json.dumps(state, indent=2),
            file_name="honeypot_status.json",
            mime="application/json",
        )


if __name__ == "__main__":
    render_dashboard()
