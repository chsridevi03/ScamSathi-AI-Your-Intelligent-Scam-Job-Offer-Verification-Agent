import express, { Request, Response } from 'express';
import path from 'path';
import { fileURLToPath } from 'url';
import dotenv from 'dotenv';
import { GoogleGenAI, Type } from '@google/genai';
import { exec } from 'child_process';
import { promisify } from 'util';

dotenv.config();

const execAsync = promisify(exec);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const app = express();
const PORT = process.env.PORT || 3000;

app.use(express.json({ limit: '5mb' }));

// Initialize Google Gemini Client with required aistudio-build telemetry header
const ai = new GoogleGenAI({
  apiKey: process.env.GEMINI_API_KEY || '',
  httpOptions: {
    headers: {
      'User-Agent': 'aistudio-build',
    },
  },
});

// Nebius and Tavily Configurations
const NEBIUS_API_KEY = process.env.NEBIUS_API_KEY || '';
const NEBIUS_BASE_URL = (process.env.NEBIUS_BASE_URL || 'https://api.studio.nebius.ai/v1').replace(/\/+$/, '');
const NEBIUS_MODEL_ID = process.env.NEBIUS_MODEL_ID || 'nvidia/nemotron-4-340b-instruct';
const TAVILY_API_KEY = process.env.TAVILY_API_KEY || '';

// Security: Private network destination blocking (SSRF prevention)
const PRIVATE_IP_REGEX = /^(https?:\/\/)?(localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d{1,3}\.\d{1,3}\.\d{1,3}|192\.168\.\d{1,3}\.\d{1,3}|172\.(1[6-9]|2\d|3[0-1])\.\d{1,3}\.\d{1,3}|169\.254\.\d{1,3}\.\d{1,3})(:\d+)?(\/.*)?$/i;

function isSafePublicUrl(url: string): boolean {
  if (!url || typeof url !== 'string') return false;
  try {
    const parsed = new URL(url);
    if (parsed.protocol !== 'http:' && parsed.protocol !== 'https:') return false;
    if (PRIVATE_IP_REGEX.test(url)) return false;
    return true;
  } catch {
    return false;
  }
}

const OFFICIAL_DOMAINS = [
  '.gov.in', '.nic.in', '.ac.in', '.edu.in', '.gov', '.edu',
  'careers.google.com', 'google.com', 'microsoft.com', 'amazon.jobs',
  'tcs.com', 'infosys.com', 'wipro.com', 'accenture.com', 'internshala.com',
  'scholarships.gov.in', 'cybercrime.gov.in'
];

function isOfficialEvidenceSource(url: string): boolean {
  if (!url) return false;
  try {
    const hostname = new URL(url).hostname.toLowerCase();
    return OFFICIAL_DOMAINS.some(domain => hostname === domain || hostname.endsWith(domain));
  } catch {
    return false;
  }
}

// Anti-prompt injection heuristics
const PROMPT_INJECTION_PATTERNS = [
  /ignore\s+(all\s+)?(previous|above|prior)\s+instructions/i,
  /you\s+are\s+now\s+(an\s+unrestricted|DAN|a\s+different)/i,
  /reveal\s+(your\s+)?(system\s+prompt|instructions|secret\s+key)/i,
  /print\s+API_KEY/i,
  /override\s+(safety|system)\s+rules/i,
];

function checkPromptInjection(text: string): boolean {
  return PROMPT_INJECTION_PATTERNS.some(pat => pat.test(text));
}

// Rule-based heuristic extractors
function extractRuleBasedClaims(text: string) {
  const feeRegex = /(registration|processing|security|training|kit|laptop|courier|uniform|application)\s+(fee|deposit|charge|amount|cost)|(pay|send|transfer|deposit)\s+(rs\.?|inr|\$|₹)\s*\d+|refundable\s+(deposit|security)/gi;
  const urgencyRegex = /(urgent|hurry|immediate|only\s+\d+\s+slots?|today\s+only|offer\s+expires\s+in|immediate\s+joining|act\s+now|last\s+chance)/gi;
  const emailRegex = /[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+/g;
  const phoneRegex = /(?:\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}/g;
  const urlRegex = /https?:\/\/[^\s<>"']+/g;
  const telegramRegex = /(?:t\.me\/|telegram\s*:\s*@?)([a-zA-Z0-9_]{4,})/gi;

  let paymentDemanded: string | null = null;
  let feeMatch: RegExpExecArray | null;
  while ((feeMatch = feeRegex.exec(text)) !== null) {
    const startPos = Math.max(0, feeMatch.index - 30);
    const prefix = text.substring(startPos, feeMatch.index).toLowerCase();
    const isNegated = ['no ', 'never ', 'not ', 'zero ', 'without ', 'free of '].some(neg => prefix.includes(neg));
    if (!isNegated) {
      paymentDemanded = feeMatch[0];
      break;
    }
  }
  const urgencyMatches = text.match(urgencyRegex);
  const emails = text.match(emailRegex) || [];
  const phones = text.match(phoneRegex) || [];
  const urls = text.match(urlRegex) || [];
  const telegrams = Array.from(text.matchAll(telegramRegex), m => `@${m[1]}`);

  // Organization heuristic
  const compMatch = text.match(/(?:at|from|with|company:?|organization:?)\s+([A-Z][a-zA-Z0-9\s&]{2,25})/);
  const company = compMatch ? compMatch[1].trim() : null;

  // Title heuristic
  const roleMatch = text.match(/(?:role:?|position:?|hiring\s+for:?|internship\s+as:?|offer\s+for:?)\s+([a-zA-Z0-9\s-]{3,35})/i);
  const title = roleMatch ? roleMatch[1].trim() : null;

  const contactDetails = [
    ...emails.map(e => `Email: ${e}`),
    ...phones.map(p => `Phone: ${p}`),
    ...telegrams.map(t => `Telegram: ${t}`)
  ];

  return {
    company_or_org: company,
    opportunity_title: title,
    payment_demanded: paymentDemanded,
    urgency_tactics: urgencyMatches ? Array.from(new Set(urgencyMatches)).slice(0, 4) : [],
    contact_details: contactDetails.slice(0, 5),
    suspicious_urls: urls.filter(isSafePublicUrl).slice(0, 5)
  };
}

// Real-time Tavily search helper
async function queryTavilySearch(query: string, maxResults: number = 5) {
  if (!TAVILY_API_KEY) {
    return [
      {
        title: "Tavily Search API Key Configured Status",
        url: "https://tavily.com",
        content: "ScamSathi AI operates with Tavily Search API for real-time web verification. When TAVILY_API_KEY is supplied, live web evidence from recruitment databases and official portals is injected.",
        score: 0.0,
        is_official: false,
        published_date: null
      }
    ];
  }

  try {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 12000);

    const resp = await fetch('https://api.tavily.com/search', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        api_key: TAVILY_API_KEY,
        query,
        search_depth: 'advanced',
        include_answer: true,
        max_results: maxResults,
        include_raw_content: false
      }),
      signal: controller.signal
    });

    clearTimeout(timeout);

    if (!resp.ok) {
      return [{
        title: `Tavily Search Notice (HTTP ${resp.status})`,
        url: "https://tavily.com",
        content: `Search query returned status ${resp.status}`,
        score: 0.0,
        is_official: false,
        published_date: null
      }];
    }

    const data = await resp.json();
    const results = (data.results || []).filter((r: any) => isSafePublicUrl(r.url)).map((r: any) => ({
      title: r.title || 'Web Evidence Source',
      url: r.url,
      content: r.content || '',
      score: r.score || 0.0,
      is_official: isOfficialEvidenceSource(r.url),
      published_date: r.published_date || null
    }));

    return results;
  } catch (err: any) {
    return [{
      title: "Search Service Connectivity",
      url: "https://status.tavily.com",
      content: `Live search query attempted: ${err?.message || 'timeout'}`,
      score: 0.0,
      is_official: false,
      published_date: null
    }];
  }
}

// Nebius Token Factory inference helper
async function queryNebiusNemotron(message: string, evidenceText: string, targetLanguage: string) {
  if (!NEBIUS_API_KEY) return null;

  const systemPrompt = `You are ScamSathi AI — an Intelligent Scam Verification Agent engineered for students and job seekers.
Analyze suspicious opportunity messages against retrieved public web evidence.
Strictly categorize risk as "High concern", "Moderate concern", "Low concern", or "Insufficient evidence".
Never output fake percentage scores.
Provide detailed explanations in English and Telugu.
Respond strictly in JSON matching the defined schema.`;

  const userContent = `MESSAGE TO VERIFY:
"""
${message}
"""

PUBLIC SEARCH EVIDENCE:
${evidenceText}

TARGET LANGUAGE: ${targetLanguage}

Return JSON with keys:
- summary (English string)
- summary_telugu (Telugu string)
- extracted_entities: { company_or_org, opportunity_title, payment_demanded, urgency_tactics: [], contact_details: [], suspicious_urls: [] }
- risk_assessment: { category ("High concern"|"Moderate concern"|"Low concern"|"Insufficient evidence"), rationale, rationale_telugu, limitations }
- warning_signs: [ { indicator, severity ("critical"|"elevated"|"medium"|"informational"), explanation, explanation_telugu } ]
- evidence_comparison: [ { claim, status ("verified"|"contradicted"|"unverified"), evidence_snippet, source_url } ]
- recommendations: [ { step, step_telugu, priority ("immediate"|"standard") } ]
- model_used: "NVIDIA Nemotron via Nebius Token Factory"`;

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 25000);

  const res = await fetch(`${NEBIUS_BASE_URL}/chat/completions`, {
    method: 'POST',
    headers: {
      'Authorization': `Bearer ${NEBIUS_API_KEY}`,
      'Content-Type': 'application/json'
    },
    body: JSON.stringify({
      model: NEBIUS_MODEL_ID,
      messages: [
        { role: 'system', content: systemPrompt },
        { role: 'user', content: userContent }
      ],
      temperature: 0.1,
      response_format: { type: 'json_object' }
    }),
    signal: controller.signal
  });

  clearTimeout(timeout);

  if (!res.ok) {
    throw new Error(`Nebius Token Factory returned ${res.status}: ${await res.text()}`);
  }

  const data = await res.json();
  const content = data.choices?.[0]?.message?.content;
  if (!content) throw new Error('Empty choices from Nebius');

  const clean = content.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim();
  return JSON.parse(clean);
}

// Fallback Gemini Analysis
async function queryGeminiAnalysis(message: string, evidenceText: string, targetLanguage: string) {
  const prompt = `You are ScamSathi AI — an Intelligent Scam Verification Agent engineered for students and job seekers (NVIDIA x Nebius Hackathon specification).
Analyze this suspicious opportunity message and ground your findings in the provided evidence.

SUBMITTED MESSAGE:
"""
${message}
"""

RETRIEVED WEB EVIDENCE:
${evidenceText}

TARGET LANGUAGE: ${targetLanguage}

Directives:
1. Ground every red flag in real recruitment guidelines.
2. High concern: demands advance fee/deposit/Aadhaar OTP, impersonates well-known company using free email or Telegram, or impossible payouts.
3. Moderate concern: unverified entity, vague duties, artificial urgency, or personal chat interviews.
4. Low concern: official domains, standard corporate hiring, zero fee requests.
5. Insufficient evidence: too short to substantiate.
6. Provide Telugu translations for summary, rationale, warning explanations, and recommendations.
7. Return strictly valid JSON adhering to schema.`;

  const response = await ai.models.generateContent({
    model: 'gemini-3.8-flash',
    contents: prompt,
    config: {
      responseMimeType: 'application/json',
      responseSchema: {
        type: Type.OBJECT,
        properties: {
          summary: { type: Type.STRING },
          summary_telugu: { type: Type.STRING },
          extracted_entities: {
            type: Type.OBJECT,
            properties: {
              company_or_org: { type: Type.STRING, nullable: true },
              opportunity_title: { type: Type.STRING, nullable: true },
              payment_demanded: { type: Type.STRING, nullable: true },
              urgency_tactics: { type: Type.ARRAY, items: { type: Type.STRING } },
              contact_details: { type: Type.ARRAY, items: { type: Type.STRING } },
              suspicious_urls: { type: Type.ARRAY, items: { type: Type.STRING } }
            },
            required: ['urgency_tactics', 'contact_details', 'suspicious_urls']
          },
          risk_assessment: {
            type: Type.OBJECT,
            properties: {
              category: { type: Type.STRING },
              rationale: { type: Type.STRING },
              rationale_telugu: { type: Type.STRING },
              limitations: { type: Type.STRING }
            },
            required: ['category', 'rationale', 'limitations']
          },
          warning_signs: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                indicator: { type: Type.STRING },
                severity: { type: Type.STRING },
                explanation: { type: Type.STRING },
                explanation_telugu: { type: Type.STRING }
              },
              required: ['indicator', 'severity', 'explanation']
            }
          },
          evidence_comparison: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                claim: { type: Type.STRING },
                status: { type: Type.STRING },
                evidence_snippet: { type: Type.STRING },
                source_url: { type: Type.STRING, nullable: true }
              },
              required: ['claim', 'status', 'evidence_snippet']
            }
          },
          recommendations: {
            type: Type.ARRAY,
            items: {
              type: Type.OBJECT,
              properties: {
                step: { type: Type.STRING },
                step_telugu: { type: Type.STRING },
                priority: { type: Type.STRING }
              },
              required: ['step', 'priority']
            }
          },
          model_used: { type: Type.STRING }
        },
        required: ['summary', 'extracted_entities', 'risk_assessment', 'warning_signs', 'evidence_comparison', 'recommendations', 'model_used']
      }
    }
  });

  const text = response.text || '{}';
  return JSON.parse(text);
}

// API Endpoints

// 1. Health and Configuration Status
app.get('/api/status', (_req: Request, res: Response) => {
  res.json({
    status: 'healthy',
    nebius: {
      configured: Boolean(NEBIUS_API_KEY && NEBIUS_API_KEY.length > 5),
      model: NEBIUS_MODEL_ID,
      endpoint: NEBIUS_BASE_URL
    },
    tavily: {
      configured: Boolean(TAVILY_API_KEY && TAVILY_API_KEY.length > 5)
    },
    gemini: {
      configured: Boolean(process.env.GEMINI_API_KEY && process.env.GEMINI_API_KEY.length > 5)
    }
  });
});

// 2. Preset Benchmark Opportunity Messages
app.get('/api/presets', (_req: Request, res: Response) => {
  const presets = [
    {
      id: 'telegram_task_scam',
      title: 'Telegram Part-time Video Review Job (Demand ₹2,500 Deposit)',
      category: 'High concern',
      tag: 'Task Fraud',
      message: `Congratulations! Your profile has been shortlisted by Global Marketing Ltd for Part-Time Social Media Evaluator. Earn ₹3,500 - ₹5,000 daily by rating travel listings and watching YouTube videos. Work 1-2 hours from phone. Daily payouts via UPI/Paytm. To activate your employee portal and receive task tokens, an advance security deposit of ₹2,500 is required (100% refundable with first payout). Hurry! Only 4 positions remaining today. Contact Manager Priya on Telegram: https://t.me/global_hr_priya immediately.`
    },
    {
      id: 'scholarship_aadhaar_scam',
      title: 'Fraudulent PM Higher Education Scholarship (Aadhaar OTP + ₹500 Fee)',
      category: 'High concern',
      tag: 'Scholarship Fraud',
      message: `NATIONAL SCHOLARSHIP PORTAL ALERT: You have been selected for Pradhan Mantri National Merit Scholarship 2026. Sanctioned grant: ₹60,000. To transfer the funds directly to your bank account, send your Aadhaar OTP and remit an application processing fee of ₹500 via Google Pay to treasury-agent@okaxis. Offer valid for 4 hours only. Do not miss this official government award.`
    },
    {
      id: 'vague_gmail_internship',
      title: 'Remote Data Entry Internship (Unverified LLC & Free Gmail Recruiter)',
      category: 'Moderate concern',
      tag: 'Recruiter Spoofing',
      message: `Apex Tech Solutions LLC is looking for Remote Virtual Assistants and Data Entry Interns. Stipend: ₹25,000 per month. Flexible hours. No prior experience needed. Please send your resume, photo ID card copy, and contact number to hr.apextechsolutions2026@gmail.com. Immediate onboarding starts this Monday.`
    },
    {
      id: 'google_step_legitimate',
      title: 'Legitimate Google STEP Internship Announcement (Official Portal, Zero Fee)',
      category: 'Low concern',
      tag: 'Legitimate Corporate',
      message: `Google is accepting applications for the Student Training in Engineering Program (STEP) Internship 2026. The 12-week summer program is open to first and second-year undergraduate students pursuing a Bachelor's degree in Computer Science or related STEM fields. Google never charges any application fees, registration fees, or equipment security deposits at any stage of the recruitment process. Submit your application and transcripts exclusively via the official portal at https://careers.google.com/jobs.`
    },
    {
      id: 'fragmented_sms',
      title: 'Fragmented SMS / WhatsApp Forward (Insufficient Information)',
      category: 'Insufficient evidence',
      tag: 'Ambiguous Payload',
      message: `Earn money sitting at home! Good opportunity. Click link: http://bit.ly/job-online-today`
    }
  ];

  res.json({ presets });
});

// 3. Core Opportunity Verification Engine
app.post('/api/analyze', async (req: Request, res: Response) => {
  try {
    const { message, language = 'en' } = req.body;

    if (!message || typeof message !== 'string' || message.trim().length < 15) {
      res.status(400).json({ error: 'Opportunity message must be at least 15 characters long.' });
      return;
    }

    if (message.length > 10000) {
      res.status(400).json({ error: 'Opportunity message exceeds maximum allowable size of 10,000 characters.' });
      return;
    }

    // Anti-prompt injection quarantine
    if (checkPromptInjection(message)) {
      res.json({
        summary: "The submitted message contains adversarial instructions or prompt-injection keywords. ScamSathi AI quarantined the payload to protect analytical integrity.",
        summary_telugu: "సమర్పించిన సందేశంలో అడ్వర్సరియల్ ఆదేశాలు లేదా ప్రాంప్ట్ ఇంజెక్షన్ పదాలు ఉన్నాయి. ScamSathi AI దీనిని నిర్బంధంలో ఉంచింది.",
        extracted_entities: {
          company_or_org: "Adversarial Input",
          opportunity_title: null,
          payment_demanded: null,
          urgency_tactics: ["Prompt override detected"],
          contact_details: [],
          suspicious_urls: []
        },
        risk_assessment: {
          category: "High concern",
          rationale: "Adversarial instructions attempting to bypass security boundaries or extract API keys are indicative of malicious deceptive activity.",
          rationale_telugu: "సిస్టమ్ భద్రతను దాటవేయడానికి ప్రయత్నించే మోసపూరిత సూచనలు గుర్తించబడ్డాయి.",
          limitations: "This assessment is a preliminary investigative analysis and does not constitute definitive proof or legal determination of fraud."
        },
        warning_signs: [
          {
            indicator: "Hostile / Adversarial Instruction Injection",
            severity: "critical",
            explanation: "Opportunity announcements that contain code directives or attempts to override AI filters are high-risk deceptive payloads.",
            explanation_telugu: "AI ఫిల్టర్లను దాటవేయడానికి ప్రయత్నించే అనుమానాస్పద సందేశం."
          }
        ],
        evidence_comparison: [
          {
            claim: "Message integrity verification",
            status: "contradicted",
            evidence_snippet: "Payload violated input safety heuristics for cybersecurity verification.",
            source_url: null
          }
        ],
        recommendations: [
          {
            step: "Do not execute any instructions, visit URLs, or download attachments associated with this payload.",
            step_telugu: "ఈ సందేశంలోని లింక్‌లను సందర్శించవద్దు లేదా డౌన్‌లోడ్ చేయవద్దు.",
            priority: "immediate"
          }
        ],
        model_used: "ScamSathi AI Safety Shield",
        raw_evidence: []
      });
      return;
    }

    // Step A: Extract claims heuristically
    const extracted = extractRuleBasedClaims(message);

    // Step B: Live Web Search via Tavily
    let searchQuery = '';
    if (extracted.company_or_org) {
      searchQuery = `${extracted.company_or_org} recruitment scam job verification`;
    } else if (extracted.opportunity_title) {
      searchQuery = `${extracted.opportunity_title} hiring scam recruitment fraud`;
    } else {
      searchQuery = `${message.slice(0, 50)} recruitment scam`;
    }

    const evidence = await queryTavilySearch(searchQuery, 5);

    // Format evidence text
    const evidenceText = evidence.map((ev: any, i: number) =>
      `[Source ${i + 1} - ${ev.is_official ? 'OFFICIAL REGISTRY' : 'WEB RECORD'}]: ${ev.title}\nURL: ${ev.url}\nExcerpt: ${ev.content}`
    ).join('\n\n');

    // Step C: Inference with NVIDIA Nemotron via Nebius (or Gemini fallback)
    let analysisResult: any = null;

    if (NEBIUS_API_KEY) {
      try {
        analysisResult = await queryNebiusNemotron(message, evidenceText, language);
      } catch (err: any) {
        console.warn('Nebius inference error, falling back to Gemini:', err.message);
      }
    }

    if (!analysisResult) {
      analysisResult = await queryGeminiAnalysis(message, evidenceText, language);
      if (!NEBIUS_API_KEY) {
        analysisResult.model_used = 'NVIDIA Nemotron Schema (Gemini Cloud Fallback Engine)';
      }
    }

    // Normalize risk category strictly
    const catLower = (analysisResult.risk_assessment?.category || '').toLowerCase();
    let validatedCategory = 'Insufficient evidence';
    if (catLower.includes('high')) validatedCategory = 'High concern';
    else if (catLower.includes('mod')) validatedCategory = 'Moderate concern';
    else if (catLower.includes('low')) validatedCategory = 'Low concern';
    analysisResult.risk_assessment.category = validatedCategory;

    // Attach raw evidence sources for user clickability
    analysisResult.raw_evidence = evidence;

    res.json(analysisResult);
  } catch (error: any) {
    console.error('Analysis error:', error);
    res.status(500).json({ error: error?.message || 'Internal analysis failure' });
  }
});

// 4. Automated Python Test Suite Runner
app.post('/api/run-tests', async (_req: Request, res: Response) => {
  try {
    const { stdout, stderr } = await execAsync('PYTHONPATH=scamsathi-ai pytest scamsathi-ai/tests/ -v', {
      cwd: __dirname,
      timeout: 30000
    });

    const passedMatches = stdout.match(/(\d+) passed/);
    const passedCount = passedMatches ? parseInt(passedMatches[1], 10) : 0;

    res.json({
      success: true,
      passedCount,
      output: stdout,
      stderr: stderr || null
    });
  } catch (err: any) {
    // If pytest exited with test failure code, capture stdout
    res.json({
      success: false,
      output: err.stdout || err.message,
      stderr: err.stderr || null
    });
  }
});

// Mount Vite or serve static assets
async function startServer() {
  if (process.env.NODE_ENV !== 'production') {
    const { createServer: createViteServer } = await import('vite');
    const vite = await createViteServer({
      server: { middlewareMode: true },
      appType: 'spa',
    });
    app.use(vite.middlewares);
  } else {
    app.use(express.static(path.join(__dirname, 'dist')));
    app.get('*', (_req, res) => {
      res.sendFile(path.join(__dirname, 'dist', 'index.html'));
    });
  }

  app.listen(PORT, () => {
    console.log(`ScamSathi AI full-stack server running on http://0.0.0.0:${PORT}`);
  });
}

startServer();
