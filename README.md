# AI handyman
Bridge AI intelligence with AR interactivity on Spectacles.

The AI Handyman Backend powers an augmented reality assistant built for Snap AR’s Lens Studio and Spectacles hardware. It integrates real-time AI inference with low-latency AR rendering to deliver visual and auditory assistance directly through the headset.

🚀 Overview

This backend acts as the integration layer between cloud-based AI services and the AR environment. It supports bi‑directional data flow, real‑time voice interaction, and context-aware responses, ensuring seamless communication between AI logic and Spectacles’ AR interface.

🧩 Core Features

Asynchronous AI Streaming: Handles text, image, and audio outputs through modular rendering components.

Spectacles Connectivity: Provides low-level networking via SpectaclesWSClient and native hardware interaction through the Spectacles Interaction Kit.

Backend ↔ Frontend Bridge: HandyBackendBridge.ts keeps AR state synchronized with backend responses.

Real-time Voice Support: Captures voice input (MicStreamer.js) and plays back generated speech (TTSPlayer.js).

Event Handling & UI Logic: Stream and interaction management through StreamingActions.ts and HandymanUIButtonActions.ts.

⚙️ Tech Stack

| Category | Technology | Purpose |
|----------|-----------|----------|
| Client-Side AR Scripts |	JavaScript / TypeScript	| Real-time AR logic (migrating to TS) |
| Backend Service | Python |	AI orchestration, APIs |
| Cloud Deployment | Render |	Automated deployment |
| AR Engine	Snap | AR Lens Studio	Spectacles | environment |



🔄 AI ↔ AR Workflow

Capture: Audio from Spectacles microphone via MicStreamer.js.

Orchestrate: Data managed by HandyBackendBridge.ts and StreamingActions.ts.

Synthesize: AI models generate text, visual, or audio responses.

Render: Output displayed through AIOutputPanel.ts, ImagePanel.js, and TTSPlayer.js.

Interact: User gestures and actions processed via HandymanUIButtonActions.ts.



🧰 Installation

Backend Setup
bash
python -m venv venv
source venv/bin/activate     # Or .\venv\Scripts\activate on Windows
pip install -r requirements.txt
Lens Studio Configuration
Open Handyman AI 2.esproj in Lens Studio.

Make sure .lspkg assets are linked in the Resources panel.

Deploy and test on Spectacles hardware.



☁️ Deploy on Render
Includes a render.yaml for one-click deployment using Render’s Blueprint feature—ideal for replicating cloud environments and testing AI inference endpoints.



🤝 Contribution & Licensing
Maintained by two core contributors.
License terms pending—contact maintainers for participation or usage permissions.
