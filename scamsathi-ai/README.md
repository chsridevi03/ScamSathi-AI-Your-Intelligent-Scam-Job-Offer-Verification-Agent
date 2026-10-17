# ScamSathi AI — Intelligent Scam Verification Agent 🛡️
> **Target Track:** Best Apps and Agents Track  
> **NVIDIA × Nebius Global AI Hackathon**

[![License: MIT](https://img.shields.io/badge/License-MIT-teal.svg)](LICENSE)
[![NVIDIA Nemotron](https://img.shields.io/badge/AI%20Model-NVIDIA%20Nemotron-76B900?logo=nvidia)](https://build.nvidia.com)
[![Nebius Token Factory](https://img.shields.io/badge/Inference-Nebius%20Token%20Factory-0284C7)](https://nebius.ai)
[![Tavily Search](https://img.shields.io/badge/Web%20Research-Tavily%20API-FF6F00)](https://tavily.com)
[![Language Support](https://img.shields.io/badge/Bilingual-English%20%7C%20Telugu-10B981)](#bilingual-support)

---

## 1. Executive Summary & Problem Statement

Every year, millions of college students, fresh graduates, and vulnerable job seekers fall victim to predatory online employment scams, fake internship offers, and fraudulent scholarship announcements. In developing regions like India, scammers prey on students' desperation by sending unsolicited WhatsApp and Telegram messages impersonating reputable companies (e.g., Google, Amazon, TCS, Infosys) or fake government schemes (e.g., PM Scholarship Portal). Victims are manipulated into paying "refundable registration fees," purchasing "training kits," or handing over identity documents and bank OTPs.

Existing anti-spam filters often fail because these offers are sent over encrypted personal channels (Telegram, WhatsApp, SMS). Students lack an objective, real-time cyber-investigation assistant to verify whether an opportunity is authentic before parting with money or sensitive personal information.

**ScamSathi AI** bridges this critical defense gap. It operates as an evidence-grounded AI agent that:
1. Deconstructs opportunity messages into actionable claims (organization names, payment requests, urgency triggers, domains).
2. Performs live public web research using **Tavily Search API** to fetch official registries and recruitment advisories.
3. Submits claims and evidence to **NVIDIA Nemotron-4-340B-Instruct** (or **Llama-3.1-Nemotron-70B**) through **Nebius Token Factory** for structured fraud synthesis.
4. Produces transparent, evidence-backed risk ratings (`High concern`, `Moderate concern`, `Low concern`, `Insufficient evidence`), with zero hallucinations or fake percentages.
5. Provides bilingual explanations in **English** and **Telugu (తెలుగు)** to protect regional language speakers.
6. Generates an on-screen investigation dossier and downloadable official PDF report.

---

## 2. Technical Architecture & Agent Workflow

```
                                      ┌────────────────────────┐
                                      │  Student / Job Seeker  │
                                      │  Pastes Suspicious Text│
                                      └───────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌────────────────────────┐
                                      │    Input Validation    │
                                      │  • Size constraints    │
                                      │  • Anti-Prompt Inject  │
                                      └───────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌────────────────────────┐
                                      │   Claim Extraction     │
                                      │  • Company / Title     │
                                      │  • Payment Demands     │
                                      │  • Contact & URLs      │
                                      └───────────┬────────────┘
                                                  │
                                                  ▼
                                      ┌────────────────────────┐
                                      │  Tavily Web Research   │
                                      │  • Official careers    │
                                      │  • Gov scholarships   │
                                      │  • Scam alert reports  │
                                      └───────────┬────────────┘
                                                  │
                                                  ▼
                        ┌──────────────────────────────────────────────────┐
                        │   NVIDIA Nemotron Inference (Nebius Token Factory)│
                        │   • Model: nvidia/nemotron-4-340b-instruct       │
                        │   • Grounding claims vs retrieved evidence       │
                        │   • Explaining why each red flag matters         │
                        │   • Structured JSON schema enforcement           │
                        └─────────────────────────┬────────────────────────┘
                                                  │
                                                  ▼
                                      ┌────────────────────────┐
                                      │   Output Validation    │
                                      │  • Pydantic Schemas    │
                                      │  • SSRF & URL Guard    │
                                      └───────────┬────────────┘
                                                  │
                                                  ▼
                        ┌──────────────────────────────────────────────────┐
                        │              Investigation Dossier               │
                        │  • Categorical Risk Assessment                   │
                        │  • Clickable Official Evidence Cards             │
                        │  • Bilingual View (English / Telugu)             │
                        │  • Downloadable PDF Report                       │
                        └──────────────────────────────────────────────────┘
```

---

## 3. Technology Stack

| Layer | Technology | Role in ScamSathi AI |
|---|---|---|
| **AI Model** | **NVIDIA Nemotron-4-340B-Instruct** / **Llama-3.1-Nemotron-70B** | Advanced reasoning, red-flag extraction, evidence-claim reconciliation |
| **Model Hosting** | **Nebius Token Factory / Nebius AI Cloud** | High-throughput, OpenAI-compatible serverless inference endpoint |
| **Web Research** | **Tavily Search API** | Real-time web retrieval of official careers pages, fraud advisories, and registries |
| **Data Validation** | **Pydantic v2** | Enforcing strict JSON output schemas, URL validation, and sanitization |
| **Testing** | **pytest** | Automated test suite validating security, bilingual output, and fraud categories |
| **Python Frontend** | **Streamlit** | Rapid deployment for Python-centric workflows and Streamlit Community Cloud |
| **Web Dashboard** | **React + Tailwind CSS + Express (TypeScript)** | Production-grade dark navy & teal cybersecurity command center |
| **PDF Generation** | **ReportLab / jsPDF** | Generates verifiable student investigation dossiers for legal & family reporting |

---

## 4. Security & Privacy Safeguards

- **Zero-Storage Privacy Policy**: ScamSathi AI analyzes opportunity messages purely in memory. No user-submitted texts or contact details are persisted to disks or databases.
- **Anti-Prompt-Injection Defense**: Pre-execution filters intercept jailbreaks (`"ignore previous instructions"`, `"reveal system prompt"`, DAN persona hijacks) and isolate the text into an adversarial quarantine state.
- **SSRF & Private Network Defense**: The search and URL validator strictly blocks loopback (`127.0.0.1`, `localhost`), link-local (`169.254.*`), and RFC-1918 private subnets (`10.*`, `192.168.*`, `172.16.*`).
- **No Hallucinated Scores**: ScamSathi rejects fake percentages (e.g. `"94.2% scam"`). All risks are strictly qualitative and evidence-grounded.
- **Credential Protection**: API keys are accessed solely via server-side environment variables (`.env`). Never exposed to client bundles or logs.

---

## 5. Local Setup Instructions (Windows VS Code & macOS/Linux)

### Prerequisites
- Python 3.10 or higher
- Git
- VS Code

### Step-by-Step Setup in VS Code

```powershell
# 1. Clone repository
git clone https://github.com/your-username/scamsathi-ai.git
cd scamsathi-ai

# 2. Create virtual environment
python -m venv venv

# 3. Activate virtual environment
# On Windows (PowerShell):
.\venv\Scripts\Activate.ps1
# On macOS / Linux:
source venv/bin/activate

# 4. Install dependencies
pip install -r requirements.txt

# 5. Configure environment variables
copy .env.example .env
# Edit .env and enter your NEBIUS_API_KEY and TAVILY_API_KEY

# 6. Run automated test suite
pytest -v

# 7. Launch the Streamlit application
streamlit run app.py
```

---

## 6. Automated Testing & Evaluation

Run the automated test suite using:
```bash
pytest tests/ -v
```

The test suite covers:
1. `test_suspicious_payment_demand_triggers_high_concern`: Upfront fee and deposit requests are correctly identified and categorized as `High concern`.
2. `test_legitimate_internship_categorization`: Standard corporate programs (e.g., Google STEP) without fee demands are categorized appropriately as `Low concern`.
3. `test_telugu_support_generation`: Confirms Telugu translations preserve URLs and technical details.
4. `test_private_network_urls_blocked`: Confirms SSRF protections against internal IP ranges.
5. `test_prompt_injection_containment`: Verifies adversarial payload containment.
6. `test_report_service_text_and_pdf_generation`: Verifies byte integrity of generated PDF reports.

---

## 7. 3-Minute YouTube Demo Video Script

**Title:** *ScamSathi AI — Investigating Recruitment & Scholarship Scams with NVIDIA Nemotron on Nebius*  
**Duration:** 2 minutes 50 seconds  

- **[0:00 - 0:25] The Problem (Hook):**
  > *"Every day, college students and fresh graduates receive WhatsApp and Telegram messages offering 'work from home' jobs or scholarship grants, only to be tricked into paying a 'refundable deposit' of ₹2,500. This is advance-fee recruitment fraud. Meet ScamSathi AI — your intelligent verification agent powered by NVIDIA Nemotron on Nebius Token Factory."*
- **[0:25 - 0:55] Architecture & Input:**
  > *"Here is the ScamSathi AI dashboard. Let's load a real-world benchmark message: an unsolicited Telegram offer claiming to be from a marketing firm paying ₹4,500/day for rating videos, but demanding a ₹2,500 security deposit. When we click 'Investigate with ScamSathi', our agent initiates a 4-step pipeline: Input validation, entity extraction, Tavily live web research, and NVIDIA Nemotron inference."*
- **[0:55 - 1:40] Evidence & Nemotron Analysis:**
  > *"Watch how Tavily immediately pulls public recruitment advisories and checks official employer registries. Next, NVIDIA Nemotron-4-340B reconciles the claims against the live evidence. Nemotron flags the advance payment demand as a Critical red flag, notes that legitimate recruiters never conduct hiring exclusively over Telegram, and marks the risk category as 'High concern' with an explicit explanation of the financial risk."*
- **[1:40 - 2:10] Bilingual Telugu Support & Contrasting Legitimate Offer:**
  > *"With one toggle, students can switch the entire analysis into Telugu (తెలుగు) — making cybersecurity accessible to regional language speakers while strictly preserving official URLs. Next, let's load a legitimate Google STEP internship. Nemotron correctly notes zero fee demands, verifies the careers.google.com portal, and categorizes it as Low concern."*
- **[2:10 - 2:40] PDF Report & Safety Checklist:**
  > *"Students can immediately download an official, formatted PDF Investigation Dossier to share with their college placement cell or parents, along with actionable next steps like filing a report on the National Cyber Crime Reporting Portal (cybercrime.gov.in)."*
- **[2:40 - 2:50] Conclusion:**
  > *"Built with NVIDIA Nemotron, Nebius Token Factory, Tavily Search, and Pydantic for the NVIDIA × Nebius Global AI Hackathon. Protecting the next generation of job seekers."*

---

## 8. Hackathon Submission Details

- **Track:** Best Apps and Agents Track
- **Real-World Impact:** Protects first-generation college students and job seekers from catastrophic financial loss and identity fraud.
- **NVIDIA Model:** NVIDIA Nemotron-4-340B-Instruct & Llama-3.1-Nemotron-70B.
- **Nebius Integration:** High-performance OpenAI-compatible REST inference via Nebius Token Factory (`https://api.studio.nebius.ai/v1`).
- **Web Grounding:** Real-time search powered by Tavily Search API.
- **License:** Open-source under the permissive MIT License.
