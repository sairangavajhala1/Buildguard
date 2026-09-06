# BuildGuard 🛡️ — Autonomous Office of the CFO

> Autonomous treasury sentinel and programmatic escrow system for commercial construction finance. Built for **Track 2: Autonomous Office of the CFO**.

---

## 📌 Problem Statement

Commercial construction finance loses billions to manual three-way matching, invoice overbilling, and critical liability oversights (such as paying subcontractors whose liability insurance has expired). Traditional accounts payable workflows take weeks to cross-examine invoices, inspection certificates, and bank statements.

**BuildGuard** automates this lifecycle end-to-end:
1. Locks milestone capital in **programmatic escrow** before construction begins.
2. Intercepts incoming invoices with an **autonomous compliance audit engine**.
3. Quarantines non-compliant claims and flags edge cases for **CFO Human-in-the-Loop (HITL)** governance.

---

## 🚀 Key Features

* **Programmatic Escrow Custody (Dodo Payments):** Automated generation of verified checkout sessions using the Dodo Payments API to hold capital securely in escrow until milestones are satisfied.
* **Deterministic Risk Sentinel:** Multi-factor invoice audits that check:
  * **Budget Overrun Detection:** Flags claims exceeding the agreed milestone budget by >5%.
  * **Insurance Sentinel:** Verifies contractor Certificate of Insurance (COI) dates against billing dates to eliminate liability risks.
  * **Safety Inspection Verification:** Halts payout release if municipal engineer sign-offs are missing.
* **Human-in-the-Loop (HITL) Governance:** Compliant bills pass through clean paths, while anomalies enter a quarantined ledger requiring one-click CFO review and override.

---

## 🛠️ Tech Stack

* **Language & Runtime:** Python 3.13 (`uv` package manager)
* **Backend API:** FastAPI, Uvicorn, Pydantic v2
* **Payment Rails:** Dodo Payments API & Python SDK
* **Frontend:** Responsive HITL Dashboard (HTML5, Tailwind CSS)
* **Testing:** Pytest (100% test pass rate across audit and checkout pipelines)
* **Agent Architecture:** Agent Orchestrator (AO) multi-agent workstream isolation

---

## 🏗️ Multi-Agent Architecture

BuildGuard was engineered using **Agent Orchestrator** across isolated workstreams:

* **`dodo-backend`:** Integrates Dodo Payments checkout sessions and webhook settlement triggers.
* **`audit-agent`:** Encapsulates the deterministic three-way matching and risk quarantine logic.
* **`hitl-dashboard`:** Implements the web interface for milestone tracking and executive overrides.
* **`consolidate-main`:** Manages branch synchronization, conflict resolution, and integrated test validation.

---

## ⚡ Quickstart

### Prerequisites
* Python 3.12+ / 3.13
* [uv](https://docs.astral.sh/uv/)

### 1. Installation
```bash
git clone [https://github.com/sairangavajhala1/Buildguard.git](https://github.com/sairangavajhala1/Buildguard.git)
cd Buildguard
uv sync
