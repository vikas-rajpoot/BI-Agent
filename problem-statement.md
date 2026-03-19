Technical Assignment: Monday.com Business
Intelligence Agent
Problem Statement
Founders and executives need quick, accurate answers to business questions across multiple data
sources. Currently, this requires manually pulling data from monday.com boards, cleaning
inconsistent data formats, querying across multiple boards, and creating ad-hoc analyses for each
request. The Challenge: Business data is messy. A founder asks, “How's our pipeline looking for
the energy sector this quarter?” Someone must interpret the query, find relevant data, clean it, and
provide insights. Your Task: Build an AI agent that answers founder-level business intelligence
queries by integrating with monday.com boards containing Work Orders and Deals data.
Sample Data
• You will receive two CSV files: Work Orders and Deals.
• Import these as separate boards into monday.com.
• Configure appropriate column types and board structure.
• The data is intentionally messy — your agent must handle inconsistencies.
Core Features
1. Monday.com Integration (Live)
- Connect via API or MCP (MCP/tool-calling is a bonus).
- Every query must trigger live API calls at query time.
- Do NOT preload or cache data.
2. Data Resilience
- Handle missing/null values.
- Normalize inconsistent formats.
- Communicate data quality caveats.
3. Query Understanding
- Interpret founder-level questions.
- Ask clarifying questions when needed.
- Support follow-up context.
4. Business Intelligence
- Provide insights across revenue, pipeline health, sector performance.
- Query across both boards when required.
5. Agent Action Visibility
- Show visible API/tool-call traces when processing queries.
Deliverables
• Hosted prototype (live, no setup required by evaluator).
• Link to monday.com boards used.
• Visible action/tool-call trace.
• Decision Log (max 2 pages).
• Source code ZIP with README.
Technical Expectations
- Conversational interface.
- Live monday.com API/MCP integration.
- Graceful error handling.
- Tech stack of your choice (justify in Decision Log).
Timeline
6 hours
Good luck!