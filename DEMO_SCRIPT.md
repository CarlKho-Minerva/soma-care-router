# Soma Care Router — 3-Minute Demo Script

> **Track:** MongoDB | **Hackathon:** Google Cloud Rapid Agent Hackathon
> **Deadline:** June 11, 2026 @ 2pm PDT
> **Repo:** https://github.com/CarlKho-Minerva/soma-care-router
> **Live:** https://care-router.somach.life (or Cloud Run URL)

---

## SCENE 1 — The Problem (0:00 – 0:25)

**[SCREEN: HTML deck slide 1 — title]**

> "300 million people worldwide have their health records locked in siloed systems. When a lab result comes back abnormal, most patients don't know what to do next — they Google, they panic, they wait."

**[SCREEN: Slide 2 — the gap]**

> "AI can read your labs. But today, patients face a choice: upload everything to the cloud for AI help, or keep data private and stay stuck. We solved both."

---

## SCENE 2 — Health Passport Local Vault (0:25 – 0:55)

**[SCREEN: Health Passport app / web UI showing vault files]**

> "This is Health Passport — a local-first health record vault. Everything lives on your device. Your labs, medications, conditions, biometrics — all structured, all private."

**[CLICK through vault tabs: medications.md, lab_baselines.md, conditions.md]**

> "Carl has ADHD and depression, managed with Escitalopram and Ritalin. His latest fasting glucose is 81, but his A1C just came back elevated at 7.2%. The local LLM flags this."

---

## SCENE 3 — The Privacy Bridge (0:55 – 1:25)

**[SCREEN: Web UI — Care Router panel]**

> "Watch what happens. The local device strips all PII — name, date of birth, insurance ID — and sends only the anonymized clinical intent to our Google Cloud Agent."

**[CLICK: "Find me a specialist" button]**

> "The payload says: 'elevated A1C, current medications: escitalopram, methylphenidate. Location: San Francisco. Find endocrinologists.' No identity. No cloud storage."

**[SCREEN: Agent reasoning trace visible in UI]**

> "Our Gemini-powered agent receives this, reasons through the request, and reaches into MongoDB Atlas via MCP."

---

## SCENE 4 — MongoDB in Action (1:25 – 2:05)

**[SCREEN: Agent results card — 3 matched providers]**

> "MongoDB Atlas stores 10,000 providers with vector embeddings of their specialties, availability, and patient reviews. The agent runs a vector search for 'endocrinology, diabetes management, SSRI-aware' and gets instant matches."

**[SCREEN: Provider cards with ratings, distance, next available]**

> "Dr. Sarah Chen — UCSF Endocrine Clinic — 0.8 miles away — next available Thursday. The agent even checked that none of these providers' common prescriptions conflict with Carl's current escitalopram."

**[CLICK: "Draft referral request"]**

> "One tap, and the agent drafts a referral request letter with the anonymized clinical summary. The patient's identity is only added back on-device, right before sending."

---

## SCENE 5 — Architecture & Impact (2:05 – 2:40)

**[SCREEN: Slide — Privacy Bridge architecture diagram]**

> "Here's the architecture. Health Passport is the brain's memory — local, encrypted, yours. The Google Cloud Agent is the hands — reaching into the world via MongoDB MCP to find doctors, match trials, and check drug conflicts. PII never touches the cloud."

**[SCREEN: Slide — numbers]**

> "This matters. 40% of patients delay care because they don't know which specialist to see. Clinical trial enrollment is 85% under target because patients can't find them. We fix both — without asking anyone to give up their privacy."

---

## SCENE 6 — Close (2:40 – 3:00)

**[SCREEN: Slide — closing]**

> "Soma Care Router. Built with Gemini 3, Google Cloud Agent Builder, and MongoDB Atlas. Your data stays local. Actions happen in the cloud. Thank you."

---

## Recording Checklist

- [ ] Clean browser, no bookmarks bar
- [ ] Screen: 1920×1080, dark mode
- [ ] Mic: check levels, no background
- [ ] Run `node server.js` locally
- [ ] Have MongoDB Atlas dashboard open in tab
- [ ] Agent trace panel enabled
- [ ] Record with OBS or Loom
- [ ] Aim for 2:50 — leave 10s buffer
