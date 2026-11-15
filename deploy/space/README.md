---
title: EU AI Act RAG Screener Demo
emoji: ⚖️
colorFrom: blue
colorTo: yellow
sdk: docker
app_port: 7860
pinned: false
license: mit
short_description: Screen an AI system against the EU AI Act, with sources
thumbnail: https://raw.githubusercontent.com/KaanGoker/EU-AI-Act-RAG-Screener/main/assets/social_preview.png
---

# EU AI Act Screener

Describe an AI system and get a draft screening under the EU AI Act (Regulation (EU) 2024/1689, consolidated text of 27 July 2026 with the Digital Omnibus amendments). The screener walks six checks in the order of the Act's provisions, quotes the articles it relies on and checks each quote against the cited provision.

## How to use it

1. Describe what the system does, who uses it and what it decides or produces, or pick an example.
2. Choose whether you build it (provider) or use it (deployer), then click **Screen the system**.
3. Open any quote to read it in the full text of the Act, answer the open questions to screen again, or download the report.

Source code, documentation and the evaluation set: [github.com/KaanGoker/EU-AI-Act-RAG-Screener](https://github.com/KaanGoker/EU-AI-Act-RAG-Screener)

## Disclaimer

This is a draft screening for orientation, not legal advice, and the result can be wrong. You must be 18 or older, and your text is sent to the Google Gemini API, so do not paste personal or confidential data. The full terms are in [DISCLAIMER.md](https://huggingface.co/spaces/KaanGoker/eu-ai-act-rag-screener-demo/blob/main/DISCLAIMER.md).
