# MeetingIQ — AI-Powered Meeting Intelligence & Analytics

**Turn conversations into structured insights, actionable decisions, and measurable outcomes.**

MeetingIQ is an AI-powered meeting assistant designed to transform meeting conversations into structured, searchable information. It aims to help teams move beyond transcripts by extracting key discussion points, decisions, action items, and unresolved questions, while enabling users to query meeting content and analyze collaboration patterns.

The project combines backend engineering, language-model workflows, structured data processing, and analytics to explore how unstructured conversational data can be converted into useful business intelligence.

## Problem Statement

Meetings generate large amounts of unstructured information, but important decisions, responsibilities, and follow-up tasks can easily get lost in lengthy transcripts.

Traditional meeting notes often require manual effort and provide limited visibility into recurring discussion patterns or task completion.

MeetingIQ addresses this problem by building a workflow that transforms conversational data into structured outputs that are easier to search, review, and analyze.

## Key Capabilities

### 1. Meeting Capture and Transcription
- Capture meeting conversations within a controlled meeting environment.
- Convert audio into text using a speech-to-text integration.
- Preserve speaker information where supported by the transcription pipeline.
- Organize transcripts for downstream processing and retrieval.

### 2. AI-Generated Meeting Summaries
- Generate concise summaries of meeting discussions.
- Extract key topics, decisions, and important takeaways.
- Identify unresolved questions and follow-up requirements where supported by the underlying conversation.
- Structure generated outputs for easier review rather than returning only free-form text.

### 3. Action Item Extraction
- Identify tasks and commitments expressed during discussions.
- Extract associated owners and deadlines when they are explicitly available.
- Organize follow-up items into a structured format.
- Support clearer tracking of responsibilities after meetings.

### 4. Context-Aware Meeting Q&A
- Allow users to ask questions about meeting discussions.
- Retrieve relevant transcript context to ground answers in the available meeting data.
- Provide supporting excerpts or references where implemented.
- Reduce reliance on unsupported assumptions by distinguishing available evidence from missing information.

### 5. Meeting Analytics
The structured outputs create opportunities to analyze meeting effectiveness beyond individual summaries.

Potential analytical dimensions include:
- Meeting duration and frequency.
- Distribution of discussion topics.
- Number of decisions and action items generated.
- Action-item completion rates, when task status data is available.
- Recurring unresolved topics across meetings.

These metrics can help explore patterns in team collaboration and follow-up effectiveness. Analytics should be presented only when the required underlying data is available.

## Technology Stack

| Component | Technology |
|---|---|
| Backend API | Python, FastAPI | 
| AI orchestration | LangGraph | 
| Language models | Local LLM Model through Ollama - qwen2.5:7b-instruct-q4_0 | 
| Speech Model | Deepgram STT and TTS | 
| Database | Supabase | 
| Frontend | React.js |
