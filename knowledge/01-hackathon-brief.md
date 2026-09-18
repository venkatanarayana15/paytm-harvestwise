# 01 — Hackathon Brief (verified facts)

## Event
- Paytm Build for India AI Hackathon — Bengaluru Edition
- Organized by Paytm (One97 Communications) in collaboration with: n8n, Sarvam AI, Cognee (per official track document; earlier edition also listed NAMESPACE / HackCulture / Logitech / Sarvam as partners)
- Format: multi-round; Round 1 = PPT/PDF submission; finale = curated in-person build sprint in Bengaluru
- Prior edition (Luma, 21 Mar 2026): in-person build day 10:00-17:00, demos 18:00-20:00, prize pool Rs 1,00,000, teams of up to 3, pitch direct to Paytm leadership, hiring opportunities
- Scale signal: a 2026 edition shortlist note mentioned "from 4,767 teams" — Round 1 deck must stand out fast
- Contact: community@paytm.com (from official Luma page)

## Round 1 required sections (verbatim from organizers)
1. Title Slide
2. Problem Statement
3. Proposed Solution
4. Technology/Tech Stack Used
5. USP (Unique Selling Proposition)
6. Impact & Benefits
7. Business Model
Upload: "Round 1 / Rounds" section of the portal, before deadline. Portal unlock can lag 2-3 hours ("You have not reached this round" message = wait and retry).

## Track briefs (verbatim essence)
- Track 1 Merchant Growth AI: "Build the AI business partner for every Paytm merchant... Think beyond payments... trusted business copilot for millions of merchants." Example given: AI copilot that increases sales by understanding the merchant's business, identifying growth opportunities, recommending or executing actions.
- Track 2 AI-Powered Financial Journeys: simplify Insurance/Lending/Fintech journeys (example: health-insurance claims).
- Track 3 Autonomous AI Teammates: AI that delivers measurable outcomes end-to-end in sales/customer service, escalating to humans only when needed.

## What judges reward (hackathon playbook)
1. Real, painful problem with a named persona — not "SMBs need analytics"
2. Working leverage of the partners' stack (n8n + Sarvam + Cognee) — organizers love their own tools used well
3. Defensible math (labeled assumptions beat fake precision)
4. Paytm-native business model (GMV/retention/lending flywheel, Soundbox bundling)
5. Demo-ability in 5 minutes for the finale

## PDF export commands (Windows)
PowerShell (Edge headless):
  $edge = "C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"   # verify path
  & $edge --headless=new --disable-gpu --no-pdf-header-footer --print-to-pdf="D:\paytm\deck\out.pdf" "file:///D:/paytm/deck/deck.html"
Or open deck.html in Edge -> Ctrl+P -> Save as PDF (margins: None, background graphics: ON; @page CSS enforces 1280x720).
