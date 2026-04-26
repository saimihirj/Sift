"""Sector knowledge modules for SaaS and D2C, plus India VC context and VC evaluation frameworks."""

SAAS_KNOWLEDGE = {
    "key_metrics": [
        "ARR (Annual Recurring Revenue)",
        "MRR (Monthly Recurring Revenue)",
        "Net Revenue Retention (NRR)",
        "Gross Revenue Retention (GRR)",
        "CAC (Customer Acquisition Cost)",
        "LTV (Lifetime Value)",
        "LTV/CAC ratio",
        "Payback period",
        "Churn rate (logo and revenue)",
        "NDR (Net Dollar Retention)",
        "ACV (Annual Contract Value)",
        "ARPU (Average Revenue Per User)",
        "Gross margin",
        "Burn multiple",
        "Rule of 40 (growth rate + profit margin)",
    ],
    "benchmarks": {
        "good_nrr": "120%+ for enterprise SaaS, 100%+ for SMB SaaS",
        "good_ltv_cac": "3:1 or higher",
        "good_payback": "Under 12 months for SMB, under 18 months for enterprise",
        "good_gross_margin": "70-85%",
        "good_churn": "Under 2% monthly for SMB, under 1% for enterprise",
        "good_burn_multiple": "Under 2x at scale",
    },
    "probing_questions": [
        "What's your current MRR and how has it trended over the last 6 months?",
        "What does your cohort retention look like at 3, 6, and 12 months?",
        "What's your average contract value and has it been expanding?",
        "How are you acquiring customers — inbound vs outbound split?",
        "What's your fully-loaded CAC including sales team costs?",
        "Do you have any net negative churn — are existing customers expanding?",
        "What's your gross margin after hosting and infrastructure costs?",
        "What does your sales cycle look like — from lead to close?",
        "How sticky is your product — what's your DAU/MAU ratio?",
        "What does your competitive moat look like — switching costs, network effects, data advantages?",
    ],
    "red_flags": [
        "Logo churn above 5% monthly",
        "LTV/CAC below 1.5x",
        "No cohort analysis available",
        "Revenue concentration — top customer > 30%",
        "Negative gross margins",
        "Payback period over 24 months",
        "No clear expansion revenue path",
    ],
}

D2C_KNOWLEDGE = {
    "key_metrics": [
        "Gross margin per unit",
        "Contribution margin (after fulfillment)",
        "CAC by channel (Meta, Google, influencer, organic)",
        "Repeat purchase rate",
        "AOV (Average Order Value)",
        "Orders per customer per year",
        "Return rate",
        "Channel mix (own website vs marketplace vs quick-commerce)",
        "Inventory turnover",
        "Working capital cycle",
        "Brand search volume trends",
        "NPS (Net Promoter Score)",
    ],
    "benchmarks": {
        "good_gross_margin": "60-70% for premium D2C, 40-50% for mass-market",
        "good_contribution_margin": "20-30% after fulfillment and returns",
        "good_repeat_rate": "30%+ within 6 months for consumables, 15%+ for durables",
        "good_cac": "Under 1/3 of first-order AOV for sustainable growth",
        "marketplace_margin_hit": "30-45% on Amazon/Flipkart, 20-35% on quick-commerce",
        "good_return_rate": "Under 5% for most categories, under 15% for fashion",
    },
    "probing_questions": [
        "What are your unit economics — walk me through cost to contribution margin?",
        "What's your channel mix — own site vs marketplaces vs quick-commerce?",
        "How much are you spending per customer acquisition on each channel?",
        "What does your repeat purchase cohort data look like?",
        "What's your return rate and how do you handle reverse logistics?",
        "How are you building brand beyond just performance marketing?",
        "What's your supply chain setup — own manufacturing vs contract?",
        "What does your working capital cycle look like?",
        "How defensible is your product — can a large player replicate this easily?",
        "What's your offline strategy — or are you purely digital?",
    ],
    "red_flags": [
        "90%+ revenue from marketplaces with no owned-channel growth",
        "CAC exceeding first-order AOV",
        "No repeat purchase data or very low repeat rates",
        "Return rates above 25%",
        "Negative contribution margins after fulfillment",
        "Single-channel dependency for acquisition",
        "No brand moat — purely commodity product",
    ],
}

FINTECH_KNOWLEDGE = {
    "key_metrics": [
        "GMV/TPV (Total Payment Volume)",
        "Take rate (net revenue ÷ GMV)",
        "MAU and DAU",
        "Transaction success rate",
        "CAC by acquisition channel",
        "ARPU (Average Revenue Per User)",
        "KYC completion rate",
        "NPA rate (for lending products)",
        "Net interest margin",
        "Monthly burn vs revenue",
        "Regulatory capital adequacy",
    ],
    "benchmarks": {
        "good_take_rate": "0.1–0.3% for payments infrastructure; 2–5% for lending; 0.5–1.5% for insurance distribution",
        "good_ltv_cac": "5:1 or higher — fintech compliance and trust costs mean CAC needs to be earned back slowly",
        "good_npa": "Under 3% for secured lending, under 6% for unsecured consumer lending",
        "good_transaction_success": "99.5%+ — failure rates above 0.5% destroy trust and volume",
        "good_cac_mass_market": "Under ₹500 for mass-market UPI/payment products; ₹2000–10000 for wealth/credit",
        "good_repeat_transaction": "Weekly active users for payments is the gold standard; monthly for lending/insurance",
    },
    "probing_questions": [
        "What is your take rate today and how does it change as you scale?",
        "Walk me through the unit economics of a single transaction — from GMV to net revenue to contribution margin.",
        "What's your regulatory path? Do you have an RBI license, are you operating as a partner bank model, or is there another structure?",
        "How are you handling KYC and compliance cost — is it automated or manual?",
        "What's your NPA rate today and how does it move with customer vintage?",
        "What's your biggest acquisition channel and what does payback look like on that cohort?",
        "What happens to your model when UPI pricing changes or NPCI tightens rules?",
        "How are you building trust with users beyond just a low-friction onboarding?",
        "What's your lock-in mechanism — why won't users switch to PhonePe/Paytm/Google Pay?",
        "Walk me through what happens when a fraud event occurs — what's your exposure and response?",
    ],
    "red_flags": [
        "No regulatory clarity or RBI license path — can be shut down overnight",
        "NPA rates above 8% without a clear improvement trajectory",
        "90%+ revenue dependent on one banking/NBFC partner",
        "Take rate too low to build a sustainable margin structure",
        "CAC growing faster than ARPU or LTV",
        "No fraud and risk infrastructure — fatal for any payment or lending product",
        "Regulatory capital shortfall — undercapitalized NBFCs are ticking time bombs",
    ],
}

MARKETPLACE_KNOWLEDGE = {
    "key_metrics": [
        "GMV (Gross Merchandise Value)",
        "Net revenue (take rate × GMV)",
        "Take rate",
        "Supply density (active listings per geography/category)",
        "Demand fill rate (searches that result in transactions)",
        "Repeat rate for buyers and sellers",
        "NPS measured separately for buyers and sellers",
        "CAC for supply side vs demand side",
        "Contribution margin per transaction",
        "Liquidity — the percentage of supply that transacts in a period",
    ],
    "benchmarks": {
        "good_take_rate": "5–15% for horizontal marketplaces; up to 25–30% for high-trust verticals (freelance, real estate)",
        "good_repeat_buyer_rate": "40%+ repeat purchases within 6 months is strong",
        "good_supply_utilization": "30%+ of listed supply transacting monthly indicates real liquidity",
        "good_fill_rate": "70%+ of buyer searches resulting in a transaction",
        "cac_ratio": "Demand-side CAC should be 2–3x lower than supply-side CAC in early stage",
        "liquidity_threshold": "Most marketplaces need 50–100 active sellers in a geography before buyers feel the market is 'full'",
    },
    "probing_questions": [
        "Which side of the marketplace is harder to acquire — supply or demand — and why?",
        "What's your take rate and have you tested pricing sensitivity with sellers?",
        "Walk me through a typical transaction — from discovery to completion to payment — what are the drop-off points?",
        "How do you prevent disintermediation — sellers and buyers going off-platform after the first transaction?",
        "What does supply density look like in your best market vs your newest market?",
        "How does your marketplace get better with more supply — is there a network effect, or does more supply just create noise?",
        "What's the repeat rate on both sides and are they trending up or down over time?",
        "Who is your most direct competitor and can you show me a geography where you're winning?",
        "What is your liquidity in your best geography — what percentage of listed supply actually transacts monthly?",
        "What happens when a large well-funded platform (Flipkart, Zomato, Urban Company) decides to enter your category?",
    ],
    "red_flags": [
        "Seller concentration: top 5 sellers account for 50%+ of GMV — fragile and negotiating leverage flips",
        "Take rate above 20% at early stage — drives sellers to disintermediate or go direct",
        "No evidence of organic supply growth — if supply only comes from paid acquisition, the marketplace won't scale",
        "Fill rate below 40% — buyers aren't finding what they need, the market isn't liquid",
        "Geographic spread without depth — thin presence everywhere is worse than dense presence somewhere",
        "No trust or safety layer — essential for marketplaces with high-value or personal transactions",
        "No repeat data — single-transaction marketplaces rarely build venture-scale value",
    ],
}

INDIA_VC_CONTEXT = {
    "key_vcs": {
        "Blume Ventures": "Seed/pre-seed focus. Loves founder-market fit, strong opinions on India-specific models. Check size: $500K-$2M.",
        "Kalaari Capital": "Seed to Series A. Consumer tech, SaaS, deep tech. Looks for large TAM in India. Check size: $1-5M.",
        "Elevation Capital": "Seed to Series B. Sector-agnostic but strong in consumer, fintech, SaaS. Check size: $1-10M.",
        "Chiratae Ventures": "Series A-B. Enterprise tech, healthcare, consumer. Likes proven unit economics. Check size: $2-10M.",
        "Peak XV (Sequoia India)": "Seed to growth. All sectors. Largest India-focused fund. Check size: $1M-$100M+.",
        "Accel India": "Seed to Series B. SaaS, fintech, consumer. Values product thinking. Check size: $1-15M.",
        "Matrix Partners India (Z47)": "Seed to Series A. Fintech, SaaS, consumer. Check size: $1-5M.",
    },
    "india_dynamics": [
        "UPI has transformed payments — 12B+ transactions/month. Any fintech or commerce play must account for UPI.",
        "Tier 2/3 city expansion is the growth frontier — but unit economics often differ significantly from metros.",
        "Quick-commerce (Blinkit, Zepto, Instamart) is reshaping D2C distribution — important to have a strategy.",
        "DPIIT recognition and Startup India benefits — tax holidays, easier compliance.",
        "India SaaS companies can build for global from India — labor cost advantage is real.",
        "Regulatory environment matters — RBI for fintech, FSSAI for food, DPDPA for data.",
        "Jio effect — 700M+ smartphone users, data costs near-zero. Mobile-first is non-negotiable.",
    ],
    "what_vcs_look_for": [
        "Founder-market fit: Why are YOU the right person to solve this?",
        "India-specific insight: What do you understand about India that outsiders miss?",
        "Unit economics path: Even if not profitable, is there a clear path to positive unit economics?",
        "Large addressable market: $1B+ TAM for venture-scale outcomes.",
        "Capital efficiency: How much can you achieve per dollar of funding?",
        "Defensibility: What gets stronger over time — network effects, data moats, brand, switching costs?",
        "Team: Technical depth, domain expertise, complementary co-founders.",
    ],
}


VC_EVALUATION_FRAMEWORK = {
    "return_math": {
        "early_stage_target": "10x+ return on each investment (most will fail, so winners must compensate)",
        "portfolio_math": "A $100M fund needs 1-2 companies returning $300M+ to deliver a strong fund return",
        "ownership_target": "VCs typically target 10-20% ownership post-investment to matter at exit",
        "exit_multiple_logic": "If targeting $1B exit and wanting 15% ownership, max entry valuation = $1B × 15% / 10x = $15M pre-money",
    },
    "investment_criteria_checklist": [
        "Market: Is the TAM $1B+? Is it growing? Why will it be much bigger in 5 years?",
        "Team: Founder-market fit — why this team, why now? Technical depth + domain expertise?",
        "Product: What is the unique insight competitors have missed? Is there a secret?",
        "Traction: Early evidence of product-market fit — retention, NPS, organic growth?",
        "Business model: Is there a clear path to profitable unit economics at scale?",
        "Competition: Why won't the big players copy this in 12 months?",
        "Timing: Why is NOW the right time? What has changed to make this possible?",
        "Defensibility: What gets stronger over time — network effects, switching costs, data, brand?",
    ],
    "market_sizing_approach": {
        "top_down": "Start with total market, apply realistic penetration rates — often too optimistic",
        "bottom_up": "Build from unit economics up — price × realistic customer base. VCs prefer this.",
        "serviceable_addressable": "SAM (who you can actually serve) > TAM (everyone). Focus on SAM first.",
        "growth_rate_matters": "A $500M market growing 40% YoY is more interesting than a $2B market growing 5%",
    },
    "founder_evaluation": {
        "coachability": "Can they update their view when evidence contradicts their assumptions?",
        "founder_market_fit": "Have they lived the problem? Do they have unfair access to customers or insights?",
        "first_principles_thinking": "Can they reason from fundamentals or do they just cite what others have done?",
        "storytelling": "Can they recruit talent, raise capital, and close customers through narrative?",
        "resilience_signals": "Have they already pushed through significant obstacles to get here?",
        "team_composition": "Complementary skill sets — usually technical + commercial at minimum",
    },
    "product_market_fit_signals": [
        "Users come back without being pushed — strong retention curves",
        "Word of mouth growing without paid acquisition",
        "Customers upset at the thought of losing the product (NPS 50+)",
        "Revenue or usage growing faster than the team can handle",
        "Clear use case with a repeatable customer archetype",
        "Expansion revenue: customers want more over time",
    ],
    "red_flags_for_vcs": [
        "Founder can't clearly explain who the customer is and why they pay",
        "TAM built entirely top-down with no bottom-up validation",
        "No competition mentioned — almost never true, signals poor market awareness",
        "Revenue concentration above 30% in one customer",
        "Team with no domain expertise trying to solve highly specialized problem",
        "Burn rate inconsistent with stated milestones",
        "Vague on current traction: 'we have lots of conversations' without metrics",
        "Fundraising without clarity on what milestone the capital unlocks",
    ],
}

COMPETITIVE_MOATS = {
    "seven_powers": {
        "scale_economies": "Unit costs fall as volume grows. Example: Amazon's logistics network.",
        "network_effects": "Product gets more valuable as more people use it. Example: WhatsApp, Slack.",
        "counter_positioning": "New business model incumbents can't copy without self-disrupting. Example: Netflix vs Blockbuster.",
        "switching_costs": "Customers incur cost (time, money, risk) to switch. Example: Salesforce CRM, ERP systems.",
        "branding": "Durable mental attachment that commands price premium. Example: Apple, luxury goods.",
        "cornered_resource": "Exclusive access to a scarce resource. Example: A patent, exclusive data, key hire.",
        "process_power": "Embedded operational excellence competitors can't replicate. Example: Toyota Production System.",
    },
    "moat_probing_questions": [
        "What would a well-funded competitor have to do to replicate what you've built?",
        "How does your moat get stronger as you scale — not weaker?",
        "What data or relationships do you uniquely have access to that improve the product over time?",
        "If Amazon/Google entered your market tomorrow, what stops them from winning?",
        "Are your switching costs real (technical lock-in, data portability issues) or just assumed?",
        "What does Year 3 of your moat look like vs Year 1?",
    ],
    "thiel_zero_to_one": {
        "secret": "Every great company is built on a secret — something most people believe is false or don't know.",
        "monopoly": "Aim to be the last mover in a category, not the first. Build something so good competition is irrelevant.",
        "power_law": "A small number of investments return most VC returns. VCs look for outlier potential, not average outcomes.",
        "contrarian_question": "What important truth do very few people agree with you on? Strong founders have a clear answer.",
    },
}

ANTI_PORTFOLIO_LESSONS = {
    "bessemer_misses": [
        {
            "company": "Airbnb",
            "valuation_at_miss": "$40M",
            "reason_passed": "Valuation deemed 'crazy'; partner believed air mattresses and renting your home couldn't be a business",
            "lesson": "Don't dismiss business models that sound absurd — network-effect marketplaces that solve real pain often explode",
            "exit_outcome": "$47B IPO (2020)",
        },
        {
            "company": "Google",
            "valuation_at_miss": "Pre-IPO",
            "reason_passed": "Partner actively avoided meeting founders; dismissed search as a commodity category",
            "lesson": "Distribution and user trust can be durable moats even in 'commodity' markets. Never dismiss search quality",
            "exit_outcome": "~$2T+ market cap",
        },
        {
            "company": "Tesla",
            "valuation_at_miss": "Early stage",
            "reason_passed": "Negative gross margins on hardware; model deemed unviable",
            "lesson": "Hardware gross margins at launch don't reflect mature economics. Ask: what do margins look like at 10x scale?",
            "exit_outcome": "$30B+ by 2014",
        },
        {
            "company": "Zoom",
            "valuation_at_miss": "Series B",
            "reason_passed": "Video conferencing market deemed too crowded with Skype, WebEx, Hangouts incumbents",
            "lesson": "Execution quality and UX can win 'crowded' markets. Ask whether incumbents are truly solving the problem.",
            "exit_outcome": "$9B IPO; peak ~$160B",
        },
        {
            "company": "PayPal",
            "valuation_at_miss": "Series A",
            "reason_passed": "'Rookie team' and regulatory concerns around payments",
            "lesson": "First-time founders with deep technical insight in regulated markets can succeed. Execution matters more than pedigree.",
            "exit_outcome": "$1.5B eBay acquisition (2002)",
        },
        {
            "company": "Instacart",
            "valuation_at_miss": "Early stage (passed twice)",
            "reason_passed": "Negative gross margins on grocery delivery deterred investment",
            "lesson": "Marketplace gross margins improve with density and volume. Don't extrapolate Day 1 economics to maturity.",
            "exit_outcome": "$10B IPO (2023)",
        },
        {
            "company": "Atlassian",
            "valuation_at_miss": "$400M (2010)",
            "reason_passed": "Valuation considered 'rich'; skepticism about bottoms-up SaaS sales model",
            "lesson": "Product-led growth can build massive enterprises without traditional sales. Don't penalize capital-efficient models.",
            "exit_outcome": "$14B+ Australian IPO (2015)",
        },
        {
            "company": "FedEx",
            "valuation_at_miss": "Passed 7 separate times",
            "reason_passed": "Capital intensity and logistics complexity of overnight delivery",
            "lesson": "Capital-intensive infrastructure businesses with network effects can be durable. Don't let asset-heaviness alone disqualify.",
            "exit_outcome": "Multi-billion logistics giant",
        },
    ],
    "meta_lessons": [
        "Valuation discipline can be the enemy of great investing — missing Airbnb at $40M to avoid it at $47B was a $47B mistake",
        "Incumbents in a market don't guarantee it's closed — execution quality often matters more than incumbency",
        "Negative unit economics at launch aren't inherently disqualifying — ask what they look like at scale",
        "Crowded markets can be won with genuinely better products (Zoom vs WebEx, Google vs AltaVista)",
        "First-time founders in regulated markets aren't automatically disqualified — PayPal, Stripe, Robinhood prove this",
        "Product-led, bottom-up growth models (Atlassian, Slack, Figma) deserve respect even without traditional sales motions",
        "Hardware businesses can be great if the software moat is strong enough — Tesla, Apple",
    ],
}

VC_DEAL_TERMS = {
    "key_terms": {
        "pre_money_valuation": "Company value before new investment. Post-money = pre-money + investment raised.",
        "liquidation_preference": "VCs get paid back before founders in an exit. 1x non-participating is founder-friendly; 2x participating is not.",
        "anti_dilution": "Protects VCs if future round is at lower valuation (down round). Full ratchet = most aggressive; broad-based weighted avg = reasonable.",
        "pro_rata_rights": "Right to maintain ownership % in future rounds. Important for VCs to double down on winners.",
        "board_composition": "Who controls board matters for future decisions. Founders should understand control implications.",
        "vesting_schedule": "Standard 4-year vest, 1-year cliff. Investors want founders economically aligned for duration.",
        "safe_vs_priced_round": "SAFEs (Simple Agreements for Future Equity) are faster/simpler for early rounds. Priced rounds establish valuation but require more legal work.",
        "convertible_note": "Debt that converts to equity at next round, often with discount and valuation cap.",
    },
    "founder_red_flags_in_terms": [
        "Liquidation preferences above 1x participating — investors get paid multiple times before founders see anything",
        "Full ratchet anti-dilution — severely punishes founders in down rounds",
        "Blocking rights on day-to-day decisions — can paralyze the company",
        "Drag-along provisions without founder protection — can force sale founders don't want",
        "Very low valuation cap on SAFEs relative to traction — dilutes founders heavily at Series A",
    ],
    "questions_founders_should_ask_vcs": [
        "What's your typical check size and follow-on strategy — will you lead our next round?",
        "What does your reserve ratio look like — how much capital do you hold back for follow-ons?",
        "What are the conditions under which you'd pass on the next round even if we're on track?",
        "Can you share 2-3 references from founders you've worked with — especially ones where things got hard?",
        "What's your fund size and how many investments do you still make? How concentrated is your portfolio?",
        "What's your decision-making process — how long from first meeting to term sheet?",
        "How do you define success for this investment at a 5-year horizon?",
    ],
}

PITCH_NARRATIVE_FRAMEWORKS = {
    "classic_vc_pitch_structure": [
        "1. Hook: The single most compelling fact or problem statement (1 slide, 30 seconds)",
        "2. Problem: Specific pain, who feels it, why it matters at scale",
        "3. Solution: What you've built — lead with outcome, not features",
        "4. Why Now: What has changed (regulatory, technical, behavioral) to make this possible today",
        "5. Market: Bottom-up TAM, who is the beachhead customer, path to expand",
        "6. Business Model: How you make money, unit economics at maturity",
        "7. Traction: The most honest and compelling early signals of PMF",
        "8. Competition: Positioning vs alternatives — honest map, not 'no competition'",
        "9. Team: Why you, why now — unfair advantages",
        "10. Ask: Amount, use of proceeds, milestones it funds",
    ],
    "storytelling_principles": [
        "Lead with the world before your solution, not with your product features",
        "Show a real user in real pain — specific beats general every time",
        "The 'why now' slide is underrated — most pitches skip it; VCs always think about it",
        "Traction should show momentum, not just a snapshot — slope matters more than level",
        "Competition slides that show only a 2x2 matrix are a red flag — explain your positioning in words",
        "The ask should explain what milestone the capital unlocks, not just how you'll spend it",
        "Avoid projections without assumptions — show the math behind the hockey stick",
    ],
    "investor_readiness_checklist": [
        "Can you explain your business in one sentence to a non-expert?",
        "Do you know your CAC, LTV, and payback period by acquisition channel?",
        "Can you defend your market size with a bottom-up model?",
        "Do you have 2-3 data points proving customers actually want this (not just that they said so)?",
        "Do you know which VCs invest at your stage and sector and why your deal fits their thesis?",
        "Can you articulate the one thing that, if proven in the next 12 months, de-risks the business substantially?",
        "Do you have a clear milestone plan for the raise — what does the money unlock?",
    ],
    "common_founder_pitch_mistakes": [
        "Starting with the product instead of the problem — VCs care about problems first",
        "Citing only top-down TAM without bottom-up validation — 'this is a $50B market' without explanation",
        "Claiming no competition — signals either poor research or lack of market awareness",
        "Projections with no supporting assumptions — VCs don't believe the numbers, they test the logic",
        "Asking for an NDA before sharing information — signals inexperience with VC norms",
        "Over-engineering the deck — 40 slides signals inability to prioritize",
        "Vague use of funds: 'sales and marketing, product development, hiring' without specifics",
        "Not knowing what milestone the raise achieves — 'we want 18 months of runway' isn't a milestone",
        "Underplaying competitive threats — pretending incumbents can't respond destroys credibility",
        "Not researching the specific VC — generic pitches feel like spam",
    ],
}


# ─────────────────────────────────────────────────────────────────────────────
# STREBULAEV VC 101 — Stanford GSB Professor Ilya Strebulaev's frameworks
# Source: VC 101 series (ilyastrebulaev.substack.com), Stanford GSB course
# ─────────────────────────────────────────────────────────────────────────────
STREBULAEV_VC101 = {
    "preferred_stock_mechanics": {
        "why_preferred": "99%+ of VC contracts use convertible preferred stock — it gives investors a choice between two payoff paths.",
        "two_choices": {
            "conversion": "Convert preferred shares into common equity — share proportionally in exit proceeds with founders.",
            "liquidation_preference": "Receive a fixed lump-sum payout first, before any common shareholders (founders, employees) get anything.",
        },
        "when_each_wins": {
            "high_exit": "At high exit valuations, conversion wins — preferred converts to share in the upside.",
            "low_exit": "At low exit valuations, liquidation preference wins — investors recover capital even if founders get nothing.",
        },
        "oip": "Original Issue Price (OIP) = Investment Amount ÷ Shares Issued. E.g., $10M ÷ 2.5M shares = $4/share. This determines ownership stakes.",
        "par_value_trap": "Par value is arbitrary and economically meaningless. Do not confuse with OIP or actual value per share.",
    },
    "liquidation_preference_types": {
        "1x_non_participating": "Investor gets 1× investment back OR converts. They choose the better outcome. Founder-friendly.",
        "1x_participating": "Investor gets 1× back PLUS participates in remaining proceeds alongside common shareholders. Less founder-friendly.",
        "2x_participating": "Investor gets 2× back AND participates in remaining proceeds. Heavily investor-favored.",
        "full_ratchet": "Most aggressive anti-dilution: if next round is lower, investor gets shares repriced to new lower price. Severely punishes founders.",
        "weighted_average_anti_dilution": "Moderate protection: adjusts investor conversion price based on how many shares are issued at lower price. Reasonable.",
    },
    "post_money_valuation": "Post-money = Pre-money + Investment. If a VC invests $10M at $40M post-money, pre-money is $30M and investor owns 25%.",
    "key_warning": "Governance rights matter as much as cash flow terms. Founders can lose board control even while retaining majority equity. Once lost, control is rarely recovered.",
    "safe_vs_convertible_note": {
        "safe": "Simple Agreement for Future Equity. No debt. Converts to equity at next priced round. Has valuation cap and/or discount. Faster, simpler for early rounds.",
        "convertible_note": "Debt instrument with interest rate. Converts to equity at next round with discount (usually 15-25%) and valuation cap. More legal complexity than SAFE.",
        "series_naming": "Series A, A-1, A-2 reflect minor variations or subsequent closings. Series Seed indicates simpler early-stage terms.",
    },
    "dilution_math": {
        "example": "$10M at $40M post-money → VC owns 25% (2.5M shares of 10M total). Founders retain 75% (7.5M shares).",
        "option_pool": "Option pools for employees typically dilute founders pre-investment — VCs often require 10-20% pool be created pre-close (pre-money dilution).",
        "multiple_rounds": "Each subsequent round dilutes all prior shareholders proportionally unless pro-rata rights are exercised.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# YC & TOP ACCELERATOR FRAMEWORKS
# ─────────────────────────────────────────────────────────────────────────────
YC_FRAMEWORKS = {
    "paul_graham_principles": {
        "make_something_people_want": "The only real goal. Everything else is noise. Build something people actually want, not what you think they want.",
        "do_things_that_dont_scale": "Serve early users manually, unscalably, obsessively. Airbnb photographed apartments. Stripe personally onboarded customers. This is how PMF is found.",
        "talk_to_users": "The #1 mistake founders make: not talking to enough users. 10 user calls > 100 slides. The answer to most product questions is in a user conversation.",
        "growth_rate_is_everything": "A startup is a company designed to grow fast. If you're not growing 5-10% weekly, you're probably not finding PMF.",
        "ramen_profitable": "Can you get to a point where you're not dying? Ramen profitability buys optionality and negotiating leverage.",
        "founder_market_fit": "Why are you the right person? Ideally: you are or were the customer, or have worked in the problem for years.",
        "unscalable_start": "The paradox: the best companies start by doing things no rational scaling business would do.",
    },
    "sam_altman_criteria": {
        "idea_evaluation": "The idea needs to be hard to execute but not so hard it's impossible. Easy ideas attract competition; hard ideas reduce it.",
        "product_market_fit_urgency": "Is there at least one segment of users who desperately need this? Not 'nice to have' but 'can't live without'?",
        "market_size": "Markets that seem small often become large. Uber's market looked small in 2009. Always ask: what does this look like if it works?",
        "team_above_all": "A great team with a mediocre idea beats a mediocre team with a great idea. VCs can't give a bad team a good idea.",
        "momentum": "Investors want to feel momentum. A company with 20% month-over-month growth is fundable almost regardless of other metrics.",
        "mission": "The best founders are solving a problem they're personally obsessed with. Altman: 'I'd rather fund a missionary than a mercenary.'",
    },
    "michael_seibel_insights": {
        "simplicity_test": "Can you explain your startup in one sentence to a non-expert? If not, you don't understand it yourself.",
        "early_metrics": "Before PMF, track retention above everything. Growth without retention is a leaky bucket.",
        "founder_psychology": "Founders who succeed aren't smarter; they persist longer. Resilience > brilliance.",
        "customer_archetype": "You need one very specific type of customer who LOVES your product. Not many types who kinda like it.",
        "speed_principle": "In the early days, nothing matters except speed of iteration. The faster you can learn, the faster you find PMF.",
    },
    "yc_application_red_flags": [
        "Founders haven't talked to users / built anything",
        "Market size is not clearly defensible (vague 'this is huge' without backing)",
        "No clear competitive insight — why will you win?",
        "Team lacks technical depth for a technical product",
        "Founders disagree on fundamental direction in the application",
        "Pivot fatigue — multiple pivots without learning signal",
        "No evidence of personal obsession with the problem",
    ],
    "yc_growth_benchmarks": {
        "exceptional": "10%+ week-over-week for 8+ consecutive weeks",
        "good": "5-7% week-over-week",
        "worrying": "Below 3% weekly without a clear reason",
        "annual_equivalent": "5% weekly = 12.6x/year; 10% weekly = 142x/year",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# TOP FIRM & INVESTOR FRAMEWORKS
# ─────────────────────────────────────────────────────────────────────────────
FIRM_FRAMEWORKS = {
    "sequoia": {
        "why_now": "Every great company needs a 'Why Now' answer: what has changed in the world that makes this possible TODAY that wasn't 3 years ago?",
        "why_now_sentence": "Three years ago this wouldn't have worked because ___. Today it works because ___. And it will only get better because ___.",
        "why_you": "What unfair advantages does this specific team have? Domain expertise, distribution access, technical depth, or unique insight competitors lack.",
        "pitch_structure": [
            "Hook: One compelling fact or stat (30 seconds)",
            "Problem: Specific pain, who feels it, why it matters at scale",
            "Solution: Lead with outcome, not features",
            "Why Now: What has changed to make this possible today",
            "Market: Bottom-up TAM, beachhead customer, expansion path",
            "Product: What you've built — with traction signals",
            "Team: Why you, why now — unfair advantages",
            "Financials: Projections with assumptions, not guesses",
            "Ask: Amount, use of funds, key milestone it funds",
        ],
        "founder_eval": [
            "Can they clearly articulate the insight at the heart of the business?",
            "Do they show coachability — does evidence change their beliefs?",
            "Do they have pattern recognition — spotting what others miss?",
        ],
    },
    "a16z": {
        "software_eating_world": "Bet on technological paradigm shifts (mobile, cloud, AI), not incremental improvements within existing paradigms.",
        "power_law_investing": "10% of portfolio companies will return 90%+ of fund returns. Concentrate capital and conviction on the best bets.",
        "tam_expansion": "Ask not just what the market is today, but why it will be 10x larger in 10 years. a16z looks for markets about to expand.",
        "regulatory_tailwinds": "Find companies benefiting from regulatory clarity or incumbents being forced to comply (Stripe + payment rails, Robinhood + brokerage).",
        "distribution_leverage": "How do you reach customers cheaper than competitors? Product-led growth compounds over time.",
        "network_effects_taxonomy": {
            "direct": "Product gets more valuable as more users join same side (WhatsApp, Zoom).",
            "indirect": "Two sides grow each other (marketplace: more sellers → better prices → more buyers → more sellers).",
            "data": "More usage → better ML/algorithms → better product → more usage (Google Search, Spotify).",
            "platform": "Third-party developers build on top, increasing value for users (iOS, Salesforce AppExchange).",
            "social": "Identity and status effects — being where your peers are (LinkedIn, Twitter/X).",
        },
    },
    "peter_thiel_7_questions": {
        "description": "From Zero to One — every startup must honestly answer all 7.",
        "questions": {
            "engineering": "Can you create breakthrough technology? Aim for 10x better, not 10% better.",
            "timing": "Is it the right time? Perfect product at wrong time = failure (Google Glass was real tech, wrong timing).",
            "monopoly": "Are you starting with a large share of a small market — path to monopoly-like position?",
            "team": "Do you have the right team? Mostly technical + commercial at minimum.",
            "distribution": "Do you have a plan to reach customers that isn't just 'advertising'?",
            "durability": "Will your position still be defensible 10-20 years from now?",
            "secret": "Have you identified a unique opportunity others have missed — something you believe that most don't?",
        },
        "contrarian_question": "What important truth do very few people agree with you on? Strong founders have a clear, specific answer.",
        "last_mover": "Don't aim to be the first mover; aim to be the last mover in a category — so dominant that competition becomes irrelevant.",
    },
    "bill_gurley": {
        "venture_scale_test": "A business must realistically reach $100M+ revenue to be venture-scale. If unit economics are positive at smaller scale but the market can't support $100M+, it's a lifestyle business.",
        "blitzscaling_check": "Sometimes burning cash fast to capture market is value-creating (Uber). Sometimes it destroys value (WeWork). The difference: do unit economics improve with scale?",
        "market_timing": "Macro trends create opportunities. Smartphones + GPS + trust = Uber. Recession + smartphones = Airbnb. Identify the convergence.",
    },
    "keith_rabois": {
        "strategy_map": "Map the competitive landscape: who's winning, why, who can win. Position yourself in white space with structural advantages.",
        "optimization_clarity": "Every company must know what metric it's optimizing for. Growth, profitability, market share, defensibility — confusion here ruins companies.",
        "operational_cadence": "Set a weekly/monthly/quarterly operating rhythm. Discipline in cadence = discipline in thinking = discipline in execution.",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# WHY NOW FRAMEWORK (detailed)
# ─────────────────────────────────────────────────────────────────────────────
WHY_NOW_FRAMEWORK = {
    "four_categories": {
        "regulatory_shifts": "New laws or regulatory clarity create/destroy opportunities overnight. GDPR created compliance startups. RBI's UPI rails enabled fintech explosion in India.",
        "technological_discontinuities": "New platforms or capabilities make previously impossible solutions practical. LLMs enabled AI copilots. Smartphones enabled location services. AWS made SaaS economics possible.",
        "economic_demographic_shifts": "Recessions, generational shifts, or cost changes alter customer willingness to buy. Post-2008 recession enabled gig economy. Inflation drove demand for alternatives.",
        "competitive_openings": "Incumbents miss a shift, can't move fast, or have business model conflicts. Cable companies couldn't cannibalize themselves with streaming. Taxis couldn't reinvent around smartphones.",
    },
    "historical_examples": {
        "uber_2009": "Smartphones + GPS (tech) + recession enabling gig work (economic) + Airbnb proving trust economy (social proof) + App Store distribution (platform)",
        "stripe_2010": "AWS commoditized servers (cost) + developer communities on GitHub (distribution) + e-commerce exploding (market) + APIs still terrible (opportunity)",
        "figma_2016": "WebGL matured (tech) + design became strategic (culture) + remote work rising (work shift) + designers needed collaboration tools (user pain)",
        "airbnb_2008": "Recession made people need income (economic) + smartphones for trust/reviews (tech) + early-adopter culture open to sharing economy (social)",
    },
    "test_questions": [
        "What existed 3 years ago that makes this impossible then but possible now?",
        "What regulatory, technological, or demographic shift is your tailwind?",
        "Who is creating the problem your customers now face, that didn't exist before?",
        "If you launched this in 2020, would it have worked? Why not? What changed?",
        "What will be even truer in 5 years that makes your position stronger over time?",
    ],
    "bad_why_now_signals": [
        "'Everyone needs this now' — doesn't identify what changed",
        "'The market is big and growing' — market size ≠ timing insight",
        "'The technology exists' — but technology may have existed for years",
        "No timing answer at all — most founders skip this slide and VCs always notice",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# STAGE-SPECIFIC METRICS & THRESHOLDS
# ─────────────────────────────────────────────────────────────────────────────
STAGE_METRICS = {
    "pre_seed_seed": {
        "funding_range": "$50K–$2M (angels, pre-seed VCs, YC-type programs)",
        "what_vcs_look_for": [
            "Founder credibility: previous exits, deep domain expertise, or relentless execution",
            "Problem validation: 10–20 conversations with users who would pay",
            "MVP or prototype: something working, not just slides",
            "Early signals: 10–100 users, $0–$10K MRR or equivalent engagement",
            "Why you: unfair advantage in this specific market",
        ],
        "red_flags": [
            "No user conversations at all — building in a vacuum",
            "Idea-stage with no prototype and no clear build plan",
            "No domain expertise in a specialized or regulated market",
            "Single founder with no co-founder plan",
        ],
    },
    "series_a": {
        "funding_range": "$2M–$15M",
        "what_vcs_look_for": [
            "MRR: $10K–$300K with 10%+ month-over-month growth",
            "Retention: 60%+ at 3 months for B2B; 30%+ for B2C",
            "CAC Payback: under 12 months (SMB), under 18 months (enterprise)",
            "NPS: 30+ (minimum), 50+ (strong)",
            "Monthly churn: under 2% for SaaS",
            "Unit economics: positive contribution margin with visible CAC trends",
            "Clear go-to-market: inbound vs outbound vs product-led growth",
            "Repeatable customer archetype: one segment that clearly loves the product",
        ],
        "growth_target": "10% MRR growth month-over-month = ~3.1x ARR year-over-year",
        "red_flags": [
            "Revenue plateau for 2+ quarters without explanation",
            "All growth from one channel or one customer",
            "CAC growing faster than LTV",
            "No cohort data — can't show retention",
        ],
    },
    "series_b": {
        "funding_range": "$10M–$50M",
        "what_vcs_look_for": [
            "ARR: $1M–$10M with 30–50% YoY growth",
            "NRR: 110%+ for expansion-revenue model",
            "Monthly churn: under 1% (enterprise), under 3% (SMB)",
            "CAC Payback: under 12 months, ideally under 9",
            "Gross margin: 70%+ (SaaS), 50%+ (marketplace)",
            "No customer concentration above 20% of revenue",
            "Functional leadership: VP Sales, VP Product, strong engineering org",
            "Evidence of moat: switching costs, data advantages, network effects, or brand",
        ],
        "growth_target": "25–50% YoY ARR growth",
    },
    "series_c_plus": {
        "funding_range": "$30M–$200M+",
        "what_vcs_look_for": [
            "ARR: $10M–$100M+ with 20–35% YoY growth",
            "Rule of 40: growth rate + FCF margin ≥ 40",
            "Burn multiple: under 2x",
            "Clear path to profitability (18–36 months)",
            "Market position: defensible #1 or #2 in segment",
            "IPO-readiness metrics: public comp benchmarks (Datadog, Snowflake, etc.)",
        ],
        "growth_target": "20–30% YoY (growth decelerates at scale)",
    },
}

# ─────────────────────────────────────────────────────────────────────────────
# CAPITAL EFFICIENCY METRICS
# ─────────────────────────────────────────────────────────────────────────────
CAPITAL_EFFICIENCY = {
    "burn_multiple": {
        "formula": "Quarterly Cash Burn ÷ Quarterly Net New ARR",
        "benchmarks": {
            "under_1": "Burning less than you earn in new ARR — exceptional, effectively self-funding growth",
            "1_to_1.5": "Efficient growth — ideal for Series A/B",
            "1.5_to_2": "Acceptable if growth rate is 30%+ QoQ",
            "above_2": "Wasteful unless in hypergrowth blitzscaling phase",
            "above_3": "Red flag — capital is not converting to growth efficiently",
        },
        "why_it_matters": "Burn multiple separates companies burning cash on growth vs burning cash on waste.",
    },
    "rule_of_40": {
        "formula": "YoY Revenue Growth Rate (%) + Free Cash Flow Margin (%)",
        "target": "≥40 is the benchmark for healthy SaaS businesses",
        "examples": [
            "Growing 35% YoY + 5% FCF margin = 40 ✓",
            "Growing 50% YoY – 10% FCF margin = 40 ✓ (growth-stage acceptable)",
            "Growing 10% YoY + 5% FCF margin = 15 ✗ (mature but not healthy)",
        ],
        "implication": "As companies mature, growth expectations decline and profitability expectations rise. Both count.",
    },
    "magic_number": {
        "formula": "(New ARR gained this quarter) ÷ (S&M spend last quarter)",
        "target": ">0.75 is acceptable; >1.0 is strong",
        "interpretation": "Every $1 of sales & marketing spend that returns $1+ of new ARR compounds favorably.",
        "caveat": "Can be gamed by timing deals; look at trailing 4-quarter average.",
    },
    "ltv_cac_calc": {
        "ltv_formula": "(Monthly Revenue per Customer × Gross Margin %) ÷ Monthly Churn %",
        "cac_formula": "Total S&M Spend in Period ÷ New Customers Acquired in Period",
        "ratio_target": "3:1 minimum, 5:1+ ideal",
        "example": "$100/month, 70% margin, 2% churn → LTV = $3,500. Spend $500 to acquire → 7:1 ratio. Exceptional.",
    },
    "cac_payback": {
        "formula": "CAC ÷ (Monthly Revenue per Customer × Gross Margin %)",
        "targets": {
            "smb_saas": "Under 12 months",
            "enterprise_saas": "Under 18 months",
            "marketplace": "Under 9 months (lower margins need faster payback)",
        },
    },
    "unit_economics_chain": [
        "1. Gross Margin = Revenue – Direct COGS (hosting, support, etc.)",
        "2. Contribution Margin = Gross Margin – Fully Loaded S&M",
        "3. CAC Payback = Months until contribution margin recovers acquisition cost",
        "4. LTV = Discounted value of all future contribution margin from a customer",
        "5. Magic Number = New ARR / Prior S&M spend — cash-on-cash marketing return",
        "6. Burn Multiple = Burn Rate / New ARR — how efficiently is cash converting to growth",
        "7. Rule of 40 = Growth % + FCF Margin % — overall health of the business",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# MISSIONARY VS MERCENARY FRAMEWORK
# ─────────────────────────────────────────────────────────────────────────────
MISSIONARY_VS_MERCENARY = {
    "missionary_traits": [
        "Can articulate the change they want to make in the world in one sentence",
        "Has lived the problem — emotionally invested, not intellectually interested",
        "Would keep building for 10 years even without a guaranteed exit",
        "Doesn't take the first acqui-hire offer — outcome matters less than mission",
        "Resilience is built-in: setbacks are expected, not demoralizing",
        "Attracts talent willing to take below-market pay for equity and mission",
        "Examples: Elon Musk (sustainable energy), Brian Chesky (belonging), Jack Dorsey (decentralization)",
    ],
    "mercenary_traits": [
        "Primarily financially motivated — watching valuations, exit multiples",
        "Opportunistic — will pivot to better market if one emerges",
        "Exit-focused from day 1 — 'what's the acquisition thesis?'",
        "Risk-averse — takes calculated bets to minimize downside",
        "Less resilience in downturns — harder to persist without financial reward",
    ],
    "why_missionaries_win": [
        "Talent attraction: mission drives recruiting above salary",
        "Persistence: missionaries outlast mercenaries through market downturns",
        "User evangelism: mission-driven users are more vocal advocates",
        "Team cohesion: shared mission reduces internal political friction",
        "Acquisition premium: buyers pay more for cultural alignment",
    ],
    "red_flag": "Missionary talk about a problem the founder has never personally experienced. This is the most dangerous combination — passion without insight.",
    "vc_preference": "Most elite VCs strongly prefer missionaries. Altman: 'I'd rather fund a missionary than a mercenary.' The best founders are often both — deeply mission-aligned AND financially motivated.",
}

# ─────────────────────────────────────────────────────────────────────────────
# COMMON VC PASS REASONS
# ─────────────────────────────────────────────────────────────────────────────
VC_PASS_REASONS = {
    "founder_doubts": [
        "Founder can't clearly articulate the core insight of the business",
        "Overconfident about non-core areas (ignoring competition, regulatory risk, etc.)",
        "Unwilling to update beliefs when shown contradicting evidence — uncoachable",
        "Weak co-founder dynamics — tension visible in meeting, misaligned on direction",
        "No domain expertise in a specialized market (fintech, health, deep tech)",
        "Serial pivot without demonstrated learning — chasing ideas not insight",
        "Single founder with no plan — many VCs won't invest without 2+ founders",
    ],
    "market_doubts": [
        "TAM not realistically $1B+ — either the market is small or penetration assumptions are unrealistic",
        "Market isn't growing or is structurally declining",
        "Timing feels wrong — 'this would have been great 5 years ago' or 'this is 5 years too early'",
        "Beachhead is not defensible — first market segment will be competed away before expansion",
        "Geographic TAM overstated — global TAM cited but model only works in one country",
    ],
    "pmf_unproven": [
        "Retention below 30% at 3 months — customers not coming back",
        "NPS below 20 — users don't love the product enough to recommend",
        "Churn above 5% monthly — bucket is leaking faster than filling",
        "No organic growth — 100% of growth from paid acquisition",
        "Growth is channel-dependent — stops when ad spend stops",
        "No clear customer archetype — everyone is the customer = no one is",
    ],
    "competitive_pressure": [
        "Well-funded, competent competitor already in space with 12+ months head start",
        "Incumbent can copy this in 6-12 months without significant cost",
        "Moat is not articulated — 'we'll win on execution' without structural advantage",
        "Customer acquisition war with a better-funded player drives CAC up",
    ],
    "unit_economics": [
        "CAC > LTV — each customer acquired is a guaranteed loss",
        "Gross margin below 50% for SaaS — no room for operating leverage",
        "Path to positive unit economics not visible in any reasonable scenario",
        "Burn multiple above 3x for non-hypergrowth company",
        "Hardware business with negative gross margins and no software moat plan",
    ],
    "team_gaps": [
        "No technical expertise for a deeply technical product",
        "No domain knowledge in a specialized problem space",
        "Missing commercial acumen — can build but can't sell",
        "Weak storytelling — can't recruit or raise beyond this check",
        "Single founder in a high-execution market",
    ],
    "deal_structural": [
        "Valuation too high relative to traction — return math doesn't work",
        "Previous investors have terms that create cap table problems",
        "Revenue concentration above 30% in one customer",
        "Regulatory risk is unquantified or unaddressed",
        "Fundraising with no clear milestone — 'we want 18 months of runway' without what it proves",
        "Founders seeking NDA before sharing basic information — signals VC inexperience",
    ],
}

# ─────────────────────────────────────────────────────────────────────────────
# TOP FOUNDER MENTAL MODELS
# ─────────────────────────────────────────────────────────────────────────────
FOUNDER_MENTAL_MODELS = {
    "bezos_amazon": {
        "customer_obsession": "Every decision flows from: what does the customer want? Not what do we want to build, not what do competitors do.",
        "long_term": "Accept short-term losses for long-term gains. Willingness to be misunderstood for years.",
        "day_1_mentality": "Treat your company like it launched yesterday, every day. Complacency kills innovation faster than competition.",
        "bias_to_action": "Decide with 70% of information needed. Waiting for 90% is too slow. Reversible decisions especially should be made fast.",
        "written_narratives": "Amazon bans slides. Decisions are made by writing 6-page narratives. Forces clarity of thought.",
    },
    "jobs_apple": {
        "simplicity": "Every feature is a tradeoff. What's the one thing you're optimizing for? Remove everything else.",
        "intersection": "Technology alone doesn't win. Technology + design + storytelling + distribution does.",
        "premium_positioning": "Never compete on price. Compete on perceived value. Willing to lose market share to maintain brand integrity.",
        "vertical_integration": "Control hardware + software + distribution. Integrated experience can't be replicated by component players.",
    },
    "zuckerberg_meta": {
        "move_fast": "Speed of iteration > perfection. Culture of continuous improvement through shipping.",
        "growth_is_everything": "Focus on one growth metric. Secondary metrics follow.",
        "mission_clarity": "Build something you believe in for 10+ years. Mission sustains you through the hard years.",
    },
    "musk_spacex_tesla": {
        "first_principles": "Question every assumption. Why do rockets cost what they cost? Don't accept industry orthodoxy.",
        "vertical_integration": "Control your supply chain when defensibility requires it. Tesla makes batteries. SpaceX makes rockets.",
        "mission_attraction": "People join for the mission (sustainable energy, multiplanetary civilization), not the equity.",
        "constraint_as_catalyst": "Tight timelines and cost constraints breed innovation. Impossibly ambitious goals force creative solutions.",
    },
    "chesky_airbnb": {
        "design_thinking": "Obsess over experience at every touchpoint — not just the product, but the photos, descriptions, communication.",
        "community_first": "Airbnb is a community company that uses technology, not a tech company. Culture IS the product.",
        "unscalable_start": "Flew to NYC to photograph early hosts' apartments. This unscalable act built trust that made the marketplace work.",
    },
    "graham_yc": {
        "live_in_future": "The best startup ideas come from living in the future. Build something you wish existed.",
        "contrarian_insight": "Most great startup ideas look bad initially. If it looked obviously good, someone else would have done it.",
        "users_over_metrics": "It is better to have 100 users who love you than 10,000 who sort of like you.",
    },
}


def get_sector_context(sector: str) -> str:
    """Return formatted sector knowledge for injection into prompts."""
    if sector == "saas":
        data = SAAS_KNOWLEDGE
        label = "SaaS"
    elif sector == "d2c":
        data = D2C_KNOWLEDGE
        label = "D2C"
    elif sector == "fintech":
        data = FINTECH_KNOWLEDGE
        label = "Fintech"
    elif sector == "marketplace":
        data = MARKETPLACE_KNOWLEDGE
        label = "Marketplace"
    else:
        return ""

    lines = [f"## {label} Sector Knowledge\n"]
    lines.append("### Key Metrics to Probe")
    for m in data["key_metrics"]:
        lines.append(f"- {m}")

    lines.append("\n### Benchmarks")
    for k, v in data["benchmarks"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines.append("\n### Strong Probing Questions")
    for q in data["probing_questions"]:
        lines.append(f"- {q}")

    lines.append("\n### Red Flags to Watch For")
    for r in data["red_flags"]:
        lines.append(f"- {r}")

    return "\n".join(lines)


def get_india_vc_context() -> str:
    """Return formatted India VC context for injection into prompts."""
    lines = ["## India VC Landscape Context\n"]

    lines.append("### Key VCs and What They Look For")
    for vc, desc in INDIA_VC_CONTEXT["key_vcs"].items():
        lines.append(f"- **{vc}**: {desc}")

    lines.append("\n### India Market Dynamics")
    for d in INDIA_VC_CONTEXT["india_dynamics"]:
        lines.append(f"- {d}")

    lines.append("\n### What Indian VCs Evaluate")
    for w in INDIA_VC_CONTEXT["what_vcs_look_for"]:
        lines.append(f"- {w}")

    return "\n".join(lines)


def get_vc_evaluation_context() -> str:
    """Return formatted VC evaluation framework for injection into prompts."""
    lines = ["## How VCs Evaluate Investments\n"]

    lines.append("### Return Math")
    for k, v in VC_EVALUATION_FRAMEWORK["return_math"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines.append("\n### Investment Criteria Checklist")
    for c in VC_EVALUATION_FRAMEWORK["investment_criteria_checklist"]:
        lines.append(f"- {c}")

    lines.append("\n### Product-Market Fit Signals")
    for s in VC_EVALUATION_FRAMEWORK["product_market_fit_signals"]:
        lines.append(f"- {s}")

    lines.append("\n### Red Flags VCs Watch For")
    for r in VC_EVALUATION_FRAMEWORK["red_flags_for_vcs"]:
        lines.append(f"- {r}")

    lines.append("\n### Founder Evaluation Lens")
    for k, v in VC_EVALUATION_FRAMEWORK["founder_evaluation"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    return "\n".join(lines)


def get_competitive_moats_context() -> str:
    """Return formatted competitive moats framework."""
    lines = ["## Competitive Moats Framework (7 Powers)\n"]

    for power, desc in COMPETITIVE_MOATS["seven_powers"].items():
        lines.append(f"- **{power.replace('_', ' ').title()}**: {desc}")

    lines.append("\n### Moat Probing Questions")
    for q in COMPETITIVE_MOATS["moat_probing_questions"]:
        lines.append(f"- {q}")

    lines.append("\n### Zero to One Principles")
    for k, v in COMPETITIVE_MOATS["thiel_zero_to_one"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    return "\n".join(lines)


def get_anti_portfolio_lessons() -> str:
    """Return formatted anti-portfolio lessons from BVP and others."""
    lines = ["## Anti-Portfolio Lessons (Why Great VCs Missed Great Companies)\n"]

    for miss in ANTI_PORTFOLIO_LESSONS["bessemer_misses"]:
        lines.append(f"**{miss['company']}** (missed at {miss['valuation_at_miss']} → {miss['exit_outcome']})")
        lines.append(f"  Why passed: {miss['reason_passed']}")
        lines.append(f"  Lesson: {miss['lesson']}\n")

    lines.append("### Meta-Lessons from Missed Investments")
    for lesson in ANTI_PORTFOLIO_LESSONS["meta_lessons"]:
        lines.append(f"- {lesson}")

    return "\n".join(lines)


def get_pitch_framework_context() -> str:
    """Return formatted pitch narrative frameworks."""
    lines = ["## Pitch Narrative Frameworks\n"]

    lines.append("### Classic VC Pitch Structure")
    for slide in PITCH_NARRATIVE_FRAMEWORKS["classic_vc_pitch_structure"]:
        lines.append(f"- {slide}")

    lines.append("\n### Storytelling Principles")
    for p in PITCH_NARRATIVE_FRAMEWORKS["storytelling_principles"]:
        lines.append(f"- {p}")

    lines.append("\n### Common Founder Pitch Mistakes")
    for m in PITCH_NARRATIVE_FRAMEWORKS["common_founder_pitch_mistakes"]:
        lines.append(f"- {m}")

    lines.append("\n### Investor Readiness Checklist")
    for c in PITCH_NARRATIVE_FRAMEWORKS["investor_readiness_checklist"]:
        lines.append(f"- {c}")

    return "\n".join(lines)


def get_deal_terms_context() -> str:
    """Return formatted VC deal terms knowledge."""
    lines = ["## VC Deal Terms Founders Should Understand\n"]

    lines.append("### Key Terms")
    for term, desc in VC_DEAL_TERMS["key_terms"].items():
        lines.append(f"- **{term.replace('_', ' ').title()}**: {desc}")

    lines.append("\n### Questions Founders Should Ask VCs")
    for q in VC_DEAL_TERMS["questions_founders_should_ask_vcs"]:
        lines.append(f"- {q}")

    lines.append("\n### Founder-Unfriendly Term Red Flags")
    for r in VC_DEAL_TERMS["founder_red_flags_in_terms"]:
        lines.append(f"- {r}")

    return "\n".join(lines)


def get_strebulaev_vc101_context() -> str:
    """Return Strebulaev VC 101 mechanics: preferred stock, liquidation preferences, dilution math."""
    lines = ["## VC Financing Mechanics (Strebulaev VC 101 — Stanford GSB)\n"]

    lines.append("### Preferred Stock Mechanics")
    pm = STREBULAEV_VC101["preferred_stock_mechanics"]
    lines.append(f"- Why VCs use preferred: {pm['why_preferred']}")
    lines.append(f"- Conversion option: {pm['two_choices']['conversion']}")
    lines.append(f"- Liquidation preference option: {pm['two_choices']['liquidation_preference']}")
    lines.append(f"- OIP formula: {pm['oip']}")
    lines.append(f"- Warning: {STREBULAEV_VC101['key_warning']}")

    lines.append("\n### Liquidation Preference Types")
    for k, v in STREBULAEV_VC101["liquidation_preference_types"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines.append("\n### Dilution Math")
    for k, v in STREBULAEV_VC101["dilution_math"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines.append("\n### SAFE vs Convertible Note")
    for k, v in STREBULAEV_VC101["safe_vs_convertible_note"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    return "\n".join(lines)


def get_yc_frameworks_context() -> str:
    """Return YC / Paul Graham / Sam Altman evaluation frameworks."""
    lines = ["## Y Combinator & Accelerator Frameworks\n"]

    lines.append("### Paul Graham Principles")
    for k, v in YC_FRAMEWORKS["paul_graham_principles"].items():
        lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")

    lines.append("\n### Sam Altman Criteria")
    for k, v in YC_FRAMEWORKS["sam_altman_criteria"].items():
        lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")

    lines.append("\n### Growth Rate Benchmarks (YC Standard)")
    for k, v in YC_FRAMEWORKS["yc_growth_benchmarks"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    lines.append("\n### YC Application Red Flags")
    for r in YC_FRAMEWORKS["yc_application_red_flags"]:
        lines.append(f"- {r}")

    return "\n".join(lines)


def get_firm_frameworks_context() -> str:
    """Return Sequoia / a16z / Peter Thiel / Benchmark / Gurley frameworks."""
    lines = ["## Top VC Firm Frameworks\n"]

    lines.append("### Sequoia Capital")
    seq = FIRM_FRAMEWORKS["sequoia"]
    lines.append(f"- Why Now: {seq['why_now']}")
    lines.append(f"- Why Now sentence: \"{seq['why_now_sentence']}\"")
    lines.append(f"- Why You: {seq['why_you']}")
    lines.append("\nSequoia Pitch Structure:")
    for s in seq["pitch_structure"]:
        lines.append(f"  - {s}")

    lines.append("\n### a16z (Andreessen Horowitz)")
    a16z = FIRM_FRAMEWORKS["a16z"]
    lines.append(f"- Software Eating World: {a16z['software_eating_world']}")
    lines.append(f"- Power Law: {a16z['power_law_investing']}")
    lines.append(f"- TAM Expansion: {a16z['tam_expansion']}")
    lines.append("\nNetwork Effects Taxonomy:")
    for k, v in a16z["network_effects_taxonomy"].items():
        lines.append(f"  - {k.title()}: {v}")

    lines.append("\n### Peter Thiel's 7 Questions")
    for k, v in FIRM_FRAMEWORKS["peter_thiel_7_questions"]["questions"].items():
        lines.append(f"- {k.title()}: {v}")
    lines.append(f"- Contrarian Test: {FIRM_FRAMEWORKS['peter_thiel_7_questions']['contrarian_question']}")

    lines.append("\n### Bill Gurley (Benchmark)")
    for k, v in FIRM_FRAMEWORKS["bill_gurley"].items():
        lines.append(f"- {k.replace('_', ' ').title()}: {v}")

    return "\n".join(lines)


def get_why_now_context() -> str:
    """Return the Why Now framework with categories, examples, and test questions."""
    lines = ["## The 'Why Now' Framework\n"]

    lines.append("### Four Categories of Why Now Forces")
    for k, v in WHY_NOW_FRAMEWORK["four_categories"].items():
        lines.append(f"- **{k.replace('_', ' ').title()}**: {v}")

    lines.append("\n### Historical Why Now Examples")
    for company, reason in WHY_NOW_FRAMEWORK["historical_examples"].items():
        lines.append(f"- {company.replace('_', ' ').title()}: {reason}")

    lines.append("\n### Why Now Probing Questions")
    for q in WHY_NOW_FRAMEWORK["test_questions"]:
        lines.append(f"- {q}")

    lines.append("\n### Bad Why Now Signals")
    for s in WHY_NOW_FRAMEWORK["bad_why_now_signals"]:
        lines.append(f"- {s}")

    return "\n".join(lines)


def get_stage_metrics_context(stage: str = "") -> str:
    """Return stage-specific metrics thresholds. Pass stage string or get all."""
    lines = ["## Stage-Specific Metrics & VC Expectations\n"]

    stage_map = {
        "idea": "pre_seed_seed",
        "pre-revenue": "pre_seed_seed",
        "early-revenue": "series_a",
        "growth": "series_b",
    }
    target_key = stage_map.get(stage, None)

    for key, label in [
        ("pre_seed_seed", "Pre-Seed / Seed"),
        ("series_a", "Series A"),
        ("series_b", "Series B"),
        ("series_c_plus", "Series C+"),
    ]:
        if target_key and key != target_key:
            continue
        data = STAGE_METRICS[key]
        lines.append(f"### {label} ({data.get('funding_range', '')})")
        if "what_vcs_look_for" in data:
            for item in data["what_vcs_look_for"]:
                lines.append(f"- {item}")
        if "growth_target" in data:
            lines.append(f"- Growth target: {data['growth_target']}")
        if "red_flags" in data:
            lines.append("Red flags:")
            for r in data["red_flags"]:
                lines.append(f"  - {r}")
        lines.append("")

    return "\n".join(lines)


def get_capital_efficiency_context() -> str:
    """Return capital efficiency metrics: burn multiple, Rule of 40, magic number, LTV/CAC."""
    lines = ["## Capital Efficiency Metrics\n"]

    for key, label in [
        ("burn_multiple", "Burn Multiple"),
        ("rule_of_40", "Rule of 40"),
        ("magic_number", "Magic Number (S&M Efficiency)"),
        ("ltv_cac_calc", "LTV:CAC Calculation"),
        ("cac_payback", "CAC Payback Period"),
    ]:
        data = CAPITAL_EFFICIENCY[key]
        lines.append(f"### {label}")
        lines.append(f"- Formula: {data.get('formula', data.get('ltv_formula', ''))}")
        if "benchmarks" in data:
            for k, v in data["benchmarks"].items():
                lines.append(f"  - {k.replace('_', ' ')}: {v}")
        if "target" in data:
            lines.append(f"- Target: {data['target']}")
        if "targets" in data:
            for k, v in data["targets"].items():
                lines.append(f"  - {k.replace('_', ' ')}: {v}")
        if "examples" in data:
            for e in data["examples"]:
                lines.append(f"  - {e}")
        if "why_it_matters" in data:
            lines.append(f"- Why it matters: {data['why_it_matters']}")
        lines.append("")

    lines.append("### Unit Economics Chain")
    for step in CAPITAL_EFFICIENCY["unit_economics_chain"]:
        lines.append(f"- {step}")

    return "\n".join(lines)


def get_vc_pass_reasons_context() -> str:
    """Return common reasons VCs pass on deals — organized by category."""
    lines = ["## Why VCs Pass — Common Reasons by Category\n"]

    category_labels = {
        "founder_doubts": "Founder Concerns",
        "market_doubts": "Market Concerns",
        "pmf_unproven": "Product-Market Fit Not Proven",
        "competitive_pressure": "Competitive Concerns",
        "unit_economics": "Unit Economics Concerns",
        "team_gaps": "Team Gaps",
        "deal_structural": "Deal & Structural Issues",
    }

    for key, label in category_labels.items():
        lines.append(f"### {label}")
        for r in VC_PASS_REASONS[key]:
            lines.append(f"- {r}")
        lines.append("")

    return "\n".join(lines)


def get_founder_mental_models_context() -> str:
    """Return top founder mental models from Bezos, Jobs, Zuckerberg, Musk, Chesky, Graham."""
    lines = ["## Top Founder Mental Models\n"]

    founder_labels = {
        "bezos_amazon": "Jeff Bezos (Amazon)",
        "jobs_apple": "Steve Jobs (Apple)",
        "zuckerberg_meta": "Mark Zuckerberg (Meta)",
        "musk_spacex_tesla": "Elon Musk (SpaceX / Tesla)",
        "chesky_airbnb": "Brian Chesky (Airbnb)",
        "graham_yc": "Paul Graham (Y Combinator)",
    }

    for key, label in founder_labels.items():
        lines.append(f"### {label}")
        for principle, desc in FOUNDER_MENTAL_MODELS[key].items():
            lines.append(f"- **{principle.replace('_', ' ').title()}**: {desc}")
        lines.append("")

    return "\n".join(lines)


def get_missionary_mercenary_context() -> str:
    """Return missionary vs mercenary founder distinction."""
    lines = ["## Missionary vs Mercenary Founders\n"]

    lines.append("### Missionary Traits (What VCs Prefer)")
    for t in MISSIONARY_VS_MERCENARY["missionary_traits"]:
        lines.append(f"- {t}")

    lines.append("\n### Why Missionaries Win")
    for r in MISSIONARY_VS_MERCENARY["why_missionaries_win"]:
        lines.append(f"- {r}")

    lines.append(f"\n### Red Flag: {MISSIONARY_VS_MERCENARY['red_flag']}")
    lines.append(f"\n### VC View: {MISSIONARY_VS_MERCENARY['vc_preference']}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# VC FIRM INTELLIGENCE — Top 50 firms by portfolio size
# Source: Investor.xlsx + Investor Firm.xlsx (knowledge_base/inbox), enriched from
# public firm websites, press releases, and fund disclosures (Aug 2025)
# ─────────────────────────────────────────────────────────────────────────────
VC_FIRMS_INTEL = {
    "Sequoia Capital": {
        "website": "https://www.sequoiacap.com",
        "focus_sectors": ["Consumer", "Enterprise", "AI/ML", "SaaS", "Fintech", "Healthcare", "Crypto/Web3", "Developer Tools", "Semiconductors"],
        "stage": "Seed (Arc program) through Growth; evergreen model",
        "geography": "Global — US, Europe, India, Southeast Asia (Sequoia China now HongShan, separate entity)",
        "thesis": "Back the daring — partner with founders at every stage from idea to IPO and beyond. Operates as an open-ended evergreen fund (The Sequoia Fund, ~$45B+ AUM) with no forced distributions post-IPO.",
        "check_size": "Seed $100K–$1M (Arc); Series A/B $10M–$100M; Growth $100M+",
        "notable_portfolio": ["Apple", "Google", "Oracle", "LinkedIn", "YouTube", "Instagram", "WhatsApp", "Airbnb", "Stripe", "DoorDash", "Zoom", "Nubank", "Snowflake", "OpenAI"],
        "differentiator": "Pioneer of evergreen fund structure (2021). Sequoia Arc (scout/seed program), Sequoia Scouts, and Sequoia Spark community. Scouts program gives reach into very early deals.",
        "portfolio_count": 2515,
    },
    "500 Global": {
        "website": "https://www.500.co",
        "focus_sectors": ["Consumer Internet", "Fintech", "Healthcare", "SaaS", "E-commerce", "AI", "Deep Tech"],
        "stage": "Pre-Seed and Seed (accelerator model)",
        "geography": "Global — 80+ countries; particularly strong in Southeast Asia, MENA, Latin America",
        "thesis": "The next billion-dollar companies will come from unexpected places — emerging markets, underrepresented founders, and overlooked geographies. Batch accelerator model with global and emerging market focus.",
        "check_size": "$100K–$250K (accelerator batch); $1M–$5M (direct seed)",
        "notable_portfolio": ["Canva", "Twilio", "Credit Karma", "Grab", "Talkdesk", "Bukalapak", "Careem", "SendGrid", "Udemy", "Intercom"],
        "differentiator": "Most geographically diverse major accelerator — invested in 80+ countries. Regional funds (500 SEA, 500 MENA, 500 Latam). High diversity of founder backgrounds vs industry benchmark.",
        "portfolio_count": 1478,
    },
    "Accel": {
        "website": "https://www.accel.com",
        "focus_sectors": ["Enterprise SaaS", "Security/Cybersecurity", "Developer Infrastructure", "Consumer", "Fintech", "AI/ML", "Cloud"],
        "stage": "Seed through Series B (primarily early stage); select growth",
        "geography": "Global — US (Silicon Valley + NYC), Europe (London), India, Israel",
        "thesis": "'Prepared mind' investing — deep sector research before meeting companies, building conviction before the company emerges. Invests early and supports companies through full lifecycle. Strong in security and infrastructure.",
        "check_size": "Seed/Early $1M–$15M; Series A/B $15M–$75M",
        "notable_portfolio": ["Facebook", "Dropbox", "Slack", "Spotify", "Atlassian", "Crowdstrike", "Qualtrics", "UiPath", "Braintree", "Flipkart", "Freshworks", "Wiz", "1Password"],
        "differentiator": "Deep cybersecurity expertise (Crowdstrike, Tenable, Cybereason). Truly global independent funds in US, Europe, India, Israel. Accel Atoms for pre-seed/seed.",
        "portfolio_count": 1329,
    },
    "Tiger Global Management": {
        "website": "https://www.tigerglobal.com",
        "focus_sectors": ["Internet", "SaaS/Software", "Fintech", "Consumer Tech", "E-commerce", "EdTech", "HealthTech"],
        "stage": "Series B through Pre-IPO and Public Markets (hedge fund + VC hybrid)",
        "geography": "Global — US, China, India, Southeast Asia, Latin America, Europe",
        "thesis": "Internet/software businesses are still in early innings globally. Applies quantitative, high-velocity approach to both private venture and public equity. Known for fast 24-hour term sheets and minimal board involvement.",
        "check_size": "$20M–$500M+ (growth to pre-IPO)",
        "notable_portfolio": ["Stripe", "Roblox", "Flipkart", "ByteDance", "Chime", "Revolut", "Nubank", "Brex", "Figma", "Checkout.com", "Rippling"],
        "differentiator": "Hybrid hedge fund / private equity model. Fastest-moving major investor — 24-hour term sheets. No board seats required. Deployed ~$50B in 2021; significant markdowns in 2022 led to restructuring.",
        "portfolio_count": 1150,
    },
    "New Enterprise Associates (NEA)": {
        "website": "https://www.nea.com",
        "focus_sectors": ["Technology", "Healthcare/Life Sciences", "Biopharma", "Medical Devices", "Enterprise Software", "Consumer Internet", "Fintech", "AI/ML"],
        "stage": "Seed through Growth/Late Stage",
        "geography": "US (primary), India, China (selective)",
        "thesis": "Backs founders in technology and healthcare across 45+ years. Rare dual-track at scale: genuine equal depth in life sciences alongside technology. 225+ IPOs and 130+ acquisitions historically.",
        "check_size": "Early $5M–$20M; Growth $20M–$150M+",
        "notable_portfolio": ["Salesforce", "Robinhood", "Tempus", "Coursera", "Workday", "Cloudflare", "MasterClass", "Plaid", "Duolingo", "Databricks", "23andMe", "Revolut"],
        "differentiator": "One of the oldest VC firms (1977). Unique for sustained dual-track in tech + healthcare at scale. Was one of the first top-tier VCs with an India investment practice.",
        "portfolio_count": 1135,
    },
    "Intel Capital": {
        "website": "https://www.intelcapital.com",
        "focus_sectors": ["AI/ML", "Autonomous Systems", "Connectivity (5G, networking)", "Cloud/Data Center Infrastructure", "Silicon Photonics/Semiconductors", "Cybersecurity", "Edge Computing/IoT"],
        "stage": "Series A through late-stage; strategic fit guides entry",
        "geography": "Global — US, Europe, Israel, China, India, Southeast Asia",
        "thesis": "Strategic CVC arm of Intel. Invests in companies advancing computing, connectivity, and data processing that support Intel's strategic roadmap. Portfolio gets access to Intel's technical expertise, manufacturing, and enterprise customers.",
        "check_size": "$5M–$50M per deal",
        "notable_portfolio": ["Cloudera", "Zoom (early)", "Slack (early)", "Mobileye (acquired)", "VMware (early)", "SiFive", "IonQ", "Nervana Systems (acquired)"],
        "differentiator": "One of the largest and oldest CVC programs (since 1991, $20B+ deployed). Unmatched access to Intel IP portfolio, fab relationships, chip roadmap. Strong Israel tech pipeline via Intel R&D presence.",
        "portfolio_count": 1095,
    },
    "Insight Partners": {
        "website": "https://www.insightpartners.com",
        "focus_sectors": ["Software/SaaS", "Security", "HealthTech", "AI/ML", "FinTech", "DevOps/Infrastructure", "E-commerce Tech"],
        "stage": "Series A through Growth/Pre-IPO (sweet spot: Series B–D)",
        "geography": "Global — US (New York primary), Europe, Israel, India",
        "thesis": "Coined the term 'ScaleUp' — investing in proven software companies accelerating from product-market fit to category leadership. Insight Onsite: dedicated operating team of 100+ professionals embedded in portfolio companies.",
        "check_size": "Series A $10M–$30M; Growth/ScaleUp $30M–$500M+",
        "notable_portfolio": ["Twitter", "Shopify", "Qualtrics", "Wix", "HelloFresh", "Monday.com", "Calm", "SentinelOne", "Veeam", "Recorded Future", "Mimecast"],
        "differentiator": "Largest software-focused growth equity firm by AUM (~$90B+). Insight Onsite is a 100+ operator team working inside portfolio companies. ScaleUp methodology — codified B2B software go-to-market playbook.",
        "portfolio_count": 996,
    },
    "Andreessen Horowitz (a16z)": {
        "website": "https://a16z.com",
        "focus_sectors": ["AI/ML", "Bio/Life Sciences", "Consumer Tech", "Crypto/Web3", "Enterprise SaaS", "Fintech", "Games", "Infrastructure", "American Dynamism (Defense, Aerospace, Manufacturing)", "Healthcare"],
        "stage": "Seed through Growth/Late Stage",
        "geography": "Primarily US; specific fund for American Dynamism",
        "thesis": "Software is eating the world — technology transforms every industry. Full-stack support platform (marketing, recruiting, finance, legal) beyond capital. Crypto as a new computing platform. 'American Dynamism' — companies advancing US national interests.",
        "check_size": "Seed $500K–$3M; Series A $10M–$50M; Growth $50M–$500M+",
        "notable_portfolio": ["Facebook (early)", "Twitter", "Airbnb", "Coinbase", "GitHub", "Slack", "Okta", "Robinhood", "Roblox", "Figma", "OpenAI", "Instacart", "Databricks", "Stripe"],
        "differentiator": "Pioneered 'full-stack VC' model with dedicated operating teams. Media/content arm. Registered as RIA to invest in public markets. $4.5B+ crypto fund. American Dynamism fund — first major VC explicitly investing in defense tech.",
        "portfolio_count": 995,
    },
    "Kleiner Perkins": {
        "website": "https://www.kleinerperkins.com",
        "focus_sectors": ["AI/ML", "Consumer", "Enterprise/SaaS", "Fintech", "Healthcare", "Deep Tech", "Climate/Energy", "Developer Infrastructure"],
        "stage": "Seed through Series B (primarily early stage)",
        "geography": "US (Silicon Valley primary)",
        "thesis": "Partner with founders at earliest stages to build transformative companies. Reinvented toward smaller, more focused early-stage model after growth struggles in 2010s. Invests at the start of secular technology waves.",
        "check_size": "Seed $1M–$5M; Series A $10M–$30M",
        "notable_portfolio": ["Amazon", "Google", "Genentech", "Twitter", "Square", "Snap", "Slack", "DoorDash", "Figma", "Rippling", "Calendly", "Scale AI"],
        "differentiator": "Founded 1972 — one of Silicon Valley's most historic firms. Famous for backing Amazon and Google at Series A. Reinvented itself in 2018–2019 to focus on early-stage only. KP Fellows program for student/recent graduate founders.",
        "portfolio_count": 976,
    },
    "Bessemer Venture Partners": {
        "website": "https://www.bvp.com",
        "focus_sectors": ["Cloud/SaaS", "Cybersecurity", "Healthcare/HealthTech", "Consumer", "Fintech", "Developer Tools", "AI", "Deep Tech"],
        "stage": "Seed through Growth",
        "geography": "US, Israel, India, Europe (global)",
        "thesis": "Pioneered 'cloud first' investing. Data-driven, publishes 'State of the Cloud' and 'Anti-Portfolio' as proof of intellectual honesty. Invests in enduring software businesses with strong unit economics. Invented modern SaaS metrics (ARR, NRR, Magic Number).",
        "check_size": "Seed $1M–$5M; Series A/B $10M–$50M; Growth $50M–$200M",
        "notable_portfolio": ["LinkedIn", "Yelp", "Skype", "Twitch", "Pinterest", "Shopify", "Twilio", "SendGrid", "Wix", "Toast", "Canva", "Fiverr", "Intercom"],
        "differentiator": "World's oldest VC firm (founded 1911, VC since 1974). Famous 'Anti-Portfolio' (passed on Apple, Google, Facebook, Amazon). BVP Cloud Index and 'State of the Cloud' are industry-standard resources.",
        "portfolio_count": 858,
    },
    "GV (Google Ventures)": {
        "website": "https://www.gv.com",
        "focus_sectors": ["Life Sciences/Healthcare", "AI/ML", "Consumer", "Enterprise", "Climate", "Cybersecurity", "Developer Tools"],
        "stage": "Seed through Series C",
        "geography": "US primary; selective Europe",
        "thesis": "Combines Alphabet resources with independent VC. Differiated insight: access to Google/Alphabet technologies, data, talent, and commercial partnerships creates unfair advantages for portfolio companies.",
        "check_size": "$250K–$50M (flexible)",
        "notable_portfolio": ["Uber", "Slack", "GitLab", "Robinhood", "Nest", "Foundation Medicine", "Flatiron Health", "Oscar Health", "23andMe", "One Medical", "CrowdStrike"],
        "differentiator": "Only major VC backed by a technology giant (Alphabet). Portfolio gets Google engineer access. Deep life sciences practice unusual for a CVC. Pioneered Design Sprint methodology (now global product standard).",
        "portfolio_count": 779,
    },
    "Index Ventures": {
        "website": "https://www.indexventures.com",
        "focus_sectors": ["Consumer", "Enterprise", "Fintech", "Gaming", "Developer/Infrastructure", "Crypto", "Healthcare", "AI"],
        "stage": "Seed through Series C (primarily early stage)",
        "geography": "Europe and US (dual-headquartered Geneva/London + San Francisco)",
        "thesis": "Backs the most ambitious founders globally. Particular strength finding European companies that achieve global scale. Truly trans-Atlantic — not a US firm with a European office.",
        "check_size": "Seed $500K–$5M; Series A $5M–$30M; Series B/C $30M–$100M",
        "notable_portfolio": ["Adyen", "Etsy", "Dropbox", "Robinhood", "Revolut", "Farfetch", "Discord", "Roblox", "Figma", "Glossier", "Deliveroo", "Datadog", "Slack"],
        "differentiator": "Most prominent genuinely trans-Atlantic VC firm. Backed multiple European unicorn milestones. Publishes free Compensation Explorer — equity benchmarking tool used by thousands of startups.",
        "portfolio_count": 754,
    },
    "General Catalyst": {
        "website": "https://www.generalcatalyst.com",
        "focus_sectors": ["AI/ML", "Healthcare", "Climate/Energy Transition", "Enterprise", "Consumer", "Fintech", "Defense/National Security", "Education"],
        "stage": "Seed through Growth; also late-stage/structured equity",
        "geography": "Global — US, Europe, India, Southeast Asia, Middle East",
        "thesis": "'Responsible Innovation' — backing companies solving the world's hardest problems at scale. 'Health Assurance' initiative aims to transform US healthcare. Strong AI-native company thesis. Evolved from traditional VC into a global transformation company.",
        "check_size": "Seed/Early $1M–$20M; Series A/B $20M–$100M; Growth $100M–$500M+",
        "notable_portfolio": ["Stripe", "Airbnb", "Snap", "Warby Parker", "Canva", "HubSpot", "Livongo", "Ro", "Samsara", "Gusto", "Anduril", "Grammarly"],
        "differentiator": "Dramatic transformation into 'global investment and transformation company.' Health Assurance thesis investing across full healthcare value chain. Dedicated practices in climate, defense, and healthcare transformation.",
        "portfolio_count": 749,
    },
    "Founders Fund": {
        "website": "https://www.foundersfund.com",
        "focus_sectors": ["Deep Tech/Hard Science", "Space/Aerospace", "AI/ML", "Biotech/Longevity", "Energy/Defense Tech", "Consumer", "Fintech/Crypto"],
        "stage": "Seed through Growth; no stage restrictions",
        "geography": "US (San Francisco); global portfolio",
        "thesis": "'We wanted flying cars, instead we got 140 characters.' Contrarian philosophy: avoids consensus trends, prefers difficult science-driven or monopoly-building ventures. Seeks 10x+ improvements, not incremental innovations. Explicitly avoids SaaS/enterprise as 'too consensus.'",
        "check_size": "$1M–$200M+ (extremely flexible)",
        "notable_portfolio": ["SpaceX", "Palantir", "Facebook (early)", "Airbnb", "Stripe", "Lyft", "Spotify", "Asana", "Anduril Industries", "Nubank"],
        "differentiator": "Founded by Peter Thiel. Most ideologically distinct major VC. First institutional investor in SpaceX and Facebook. Strong defense tech (Palantir, Anduril) before it was popular. No scouts, no accelerator — very selective.",
        "portfolio_count": 654,
    },
    "Greylock Partners": {
        "website": "https://www.greylock.com",
        "focus_sectors": ["Consumer", "Enterprise", "AI/ML", "Security", "Infrastructure", "Developer Tools", "Fintech"],
        "stage": "Seed through Series B (primarily early stage)",
        "geography": "US (Silicon Valley + NYC primary); selective global",
        "thesis": "Invests in category-defining companies at earliest stages. All partners are former operators and entrepreneurs — founder-first philosophy. Great companies are built by exceptional people; prioritizes founder relationship over market timing.",
        "check_size": "Seed $1M–$5M; Series A $5M–$25M; Series B $25M–$60M",
        "notable_portfolio": ["LinkedIn", "Facebook (early)", "Airbnb", "Workday", "Palo Alto Networks", "Instagram", "Roblox", "Discord", "Figma", "Coinbase", "Dropbox", "Replit"],
        "differentiator": "Founded 1965. All investment partners are former founders/operators (Reid Hoffman, etc.) — not career VCs. Greylock Edge operational support program. Extremely concentrated portfolios with high conviction.",
        "portfolio_count": 636,
    },
    "GGV Capital": {
        "website": "https://www.ggvc.com",
        "focus_sectors": ["Consumer", "Enterprise SaaS", "Social/Creator Economy", "Fintech", "AI/ML", "Logistics/Supply Chain", "Gaming"],
        "stage": "Series A through Growth",
        "geography": "US and Asia; split in 2023 into Notable Capital (US/global) and Granite Asia (Asia)",
        "thesis": "Built differentiation as the premier 'bridge' VC between US and China. After US-China tensions, split operations in 2023. Former GGV is now two separately branded firms.",
        "check_size": "Series A $10M–$40M; Growth $40M–$200M",
        "notable_portfolio": ["Alibaba", "Xiaomi", "Airbnb", "Slack", "Wish", "StockX", "Poshmark", "Peloton", "Lime", "HashiCorp", "XPeng"],
        "differentiator": "Most successful trans-Pacific VC firm — simultaneously backed Alibaba, Airbnb, Slack, and Xiaomi at early stages. 2023 split reflects geopolitical reconfiguration of VC industry.",
        "portfolio_count": 620,
    },
    "Khosla Ventures": {
        "website": "https://www.khoslaventures.com",
        "focus_sectors": ["AI/ML", "Climate/Clean Energy", "Health/Biotech", "Deep Tech", "Agriculture", "Consumer", "Enterprise", "Robotics", "Space", "Nuclear Energy"],
        "stage": "Seed through Series B; also Khosla Impact",
        "geography": "US primary; selective international",
        "thesis": "'Embrace the power of technology to solve impossible problems.' Famous for 'radical' bets on science-based companies most VCs avoid — climate tech, alternative proteins, nuclear, longevity. Very high failure tolerance in exchange for civilization-scale impact.",
        "check_size": "Seed/Early $500K–$5M; Series A/B $10M–$50M",
        "notable_portfolio": ["OpenAI (seed)", "Square", "Affirm", "DoorDash", "Instacart", "Okta", "Joby Aviation", "Impossible Foods", "Commonwealth Fusion Systems"],
        "differentiator": "Founded by Vinod Khosla (Sun Microsystems co-founder). Most aggressive deep-tech and climate-tech focus among top-tier VCs. Was an early seed investor in OpenAI. Khosla Impact fund for social missions.",
        "portfolio_count": 617,
    },
    "TechStars": {
        "website": "https://www.techstars.com",
        "focus_sectors": ["Broad/All sectors", "Fintech", "Healthcare", "Energy", "Retail", "Media", "Defense"],
        "stage": "Pre-Seed (accelerator model)",
        "geography": "Global — programs in 30+ cities worldwide",
        "thesis": "Accelerate the lifecycle of the entrepreneur — provide a 13-week intensive accelerator program with mentorship, $120K standard investment, and access to alumni network. Corporate-partnership model runs vertical-specific programs with Fortune 500 sponsors.",
        "check_size": "$120K standard (common equity) per batch company",
        "notable_portfolio": ["Uber (early)", "SendGrid", "Digital Ocean", "SalesLoft", "Sphero", "ClassPass", "PillPack (acquired by Amazon)", "Remitly"],
        "differentiator": "One of the world's largest accelerator networks with 3,000+ portfolio companies. Deep corporate sponsor model (Barclays, Nike, Target-backed programs). Alumni network of 50,000+ entrepreneurs. Community-led deal flow in non-Silicon Valley cities.",
        "portfolio_count": 615,
    },
    "Battery Ventures": {
        "website": "https://www.battery.com",
        "focus_sectors": ["Enterprise Software/SaaS", "Cloud Infrastructure", "Security", "Fintech", "Consumer Tech", "Industrial Tech", "AI"],
        "stage": "Seed through Growth/Buyout (uniquely broad mandate)",
        "geography": "US (Boston + San Francisco), Europe, Israel",
        "thesis": "Backs entrepreneurs across all stages — from seed to growth and even buyouts of established software companies. Uniquely broad mandate: great opportunities arise at every stage of the company lifecycle.",
        "check_size": "Seed $1M–$5M; Growth $20M–$100M; Buyout $100M–$1B+",
        "notable_portfolio": ["Wayfair", "Procore", "Marketo", "Glassdoor", "Addepar", "Intercom", "Sprinklr", "BladeLogic", "Angi"],
        "differentiator": "Very few VCs operate from seed through software buyouts within the same fund family. Boston-based. Battery Open Source fund for open-source companies. 30+ software buyouts completed — more than almost any growth equity firm.",
        "portfolio_count": 611,
    },
    "Kima Ventures": {
        "website": "https://www.kimaventures.com",
        "focus_sectors": ["Software (broadly)", "SaaS", "Marketplaces", "Fintech", "Developer Tools", "Consumer Internet", "AI"],
        "stage": "Pre-seed and Seed exclusively",
        "geography": "Global — France-based but invests worldwide",
        "thesis": "Volume-based pre-seed investor: writes ~150 small checks per year. At pre-seed, the best strategy is broad diversification with fast decisions — impossible to predict winners this early. 48-hour decision process.",
        "check_size": "$150K–$300K (very small, standardized)",
        "notable_portfolio": ["Algolia", "Sunrise (acquired by Microsoft)", "Zenly (acquired by Snap)", "ManoMano", "Batch"],
        "differentiator": "One of the most active pre-seed investors globally by deal count (~150/year). Backed by Xavier Niel (founder of Iliad/Free). Famous for 48-hour yes/no decisions. Strong gateway into European early-stage ecosystem.",
        "portfolio_count": 583,
    },
    "Global Founders Capital": {
        "website": "https://www.globalfounderscapital.com",
        "focus_sectors": ["Consumer Internet/Marketplaces", "Enterprise Software/SaaS", "Fintech", "E-commerce", "EdTech", "HealthTech"],
        "stage": "Seed through Series A; stage-agnostic in practice",
        "geography": "Global — Europe, Americas, Asia, Africa; truly borderless",
        "thesis": "Great founders exist globally, not just in Silicon Valley. Brings operational playbooks from Rocket Internet's company-building experience alongside capital. Has invested in 100+ countries.",
        "check_size": "$100K–$10M (wide range, stage-dependent)",
        "notable_portfolio": ["Lazada", "Delivery Hero", "Zalando (via Rocket)", "HelloFresh (via Rocket)", "Lyft", "Slack", "Airbnb (secondary)", "Canva"],
        "differentiator": "Rocket Internet DNA — operational expertise in building and scaling internet businesses. One of the few major funds with deep roots in Africa, SEA, and LATAM simultaneously. No geographic or sector restrictions.",
        "portfolio_count": 572,
    },
    "First Round Capital": {
        "website": "https://www.firstround.com",
        "focus_sectors": ["Consumer", "Enterprise/SaaS", "Fintech", "Healthcare", "AI/ML", "Developer Tools", "Marketplace"],
        "stage": "Pre-Seed and Seed only (strictly early stage)",
        "geography": "US primary (San Francisco, NYC)",
        "thesis": "The first check is the highest-leverage moment in any company's life. Exclusively pre-seed/seed. Built the First Round Network — a platform connecting founders and operators across portfolio.",
        "check_size": "$500K–$3M (seed/pre-seed only)",
        "notable_portfolio": ["Uber", "Square", "Warby Parker", "Roblox", "Notion", "Looker", "Flatiron Health", "Bombas", "ClassPass", "Coda"],
        "differentiator": "Strictly seed-only. The First Round Review is one of the most widely-read startup management blogs. First Round Network — proprietary online community for portfolio founders. Famous for Uber seed check at $1.25M pre-product.",
        "portfolio_count": 556,
    },
    "SB Investment Advisers (Vision Fund)": {
        "website": "https://www.visionfund.com",
        "focus_sectors": ["AI/ML", "Robotics", "IoT/Smart Cities", "HealthTech", "Fintech", "E-commerce", "Autonomous Vehicles", "Consumer Tech", "PropTech", "Logistics"],
        "stage": "Series B through Pre-IPO (primarily late-stage growth)",
        "geography": "Global — US, China, India, Southeast Asia, Europe, Latin America, Middle East",
        "thesis": "AI will touch every industry and create trillions in value. Vision Fund 1 was the largest VC fund ever raised ($98.6B). Vision Fund 2 shifted to smaller, more disciplined checks post-WeWork debacle. 300-year vision for AI.",
        "check_size": "Vision Fund 1 $100M–$10B; Vision Fund 2 $25M–$500M",
        "notable_portfolio": ["Uber", "WeWork", "ByteDance", "Didi", "OYO", "Grab", "Klarna", "DoorDash", "Coupang", "Nuro", "Opendoor", "Paytm", "ARM Holdings", "Revolut"],
        "differentiator": "By far the largest VC fund ever raised ($98.6B). Changed late-stage venture by writing $500M+ single-company checks. WeWork implosion and ~$50B in 2021–2022 write-downs led to dramatic scaling back. Closest thing to a sovereign wealth fund in structure.",
        "portfolio_count": 515,
    },
    "DST Global": {
        "website": "https://dst-global.com",
        "focus_sectors": ["Consumer Internet", "E-commerce", "Social Media", "Fintech", "Marketplaces", "On-demand Services"],
        "stage": "Late-stage / Growth (Series B+); primarily pre-IPO",
        "geography": "Global — US, Europe, Asia, Latin America, India",
        "thesis": "Backs category-defining consumer internet companies at scale. Takes minority stakes without board seats — founder-friendly, hands-off style. Largest internet platforms deliver outsized returns over long holding periods.",
        "check_size": "$100M–$1B+ per round",
        "notable_portfolio": ["Facebook", "Twitter", "Airbnb", "Spotify", "Snapchat", "Alibaba", "JD.com", "Flipkart", "Klarna", "Revolut", "DoorDash", "Robinhood", "Nubank"],
        "differentiator": "Founded by Yuri Milner. Famous for writing very large checks at unconventional (high) valuations without requiring board seats — revolutionary when DST invested in Facebook at $10B valuation in 2009.",
        "portfolio_count": 497,
    },
    "Redpoint Ventures": {
        "website": "https://www.redpoint.com",
        "focus_sectors": ["SaaS/Cloud", "Infrastructure", "AI/ML", "Developer Tools", "Security", "Consumer", "Fintech"],
        "stage": "Seed through Series B",
        "geography": "US primary; separate Redpoint China fund",
        "thesis": "Backs founders building infrastructure and applications for the next generation of computing. Strong emphasis on data-driven developer-centric infrastructure. Believes in being early to secular technology transitions (cloud, AI). Publishes Redpoint Data Center — SaaS metrics benchmarking.",
        "check_size": "Seed $500K–$3M; Series A $5M–$25M; Series B $25M–$75M",
        "notable_portfolio": ["Netflix", "Stripe", "Snowflake", "Twilio", "Heroku", "Zendesk", "Hashicorp", "Zuora", "Looker", "Domo"],
        "differentiator": "One of the earliest believers in cloud/SaaS — backed Netflix, Stripe, Snowflake, Twilio at early stages. Tom Tunguz is one of the most data-driven VC bloggers, regularly publishing SaaS benchmarks.",
        "portfolio_count": 488,
    },
    "Greycroft Partners": {
        "website": "https://www.greycroft.com",
        "focus_sectors": ["Consumer Internet", "SaaS/Enterprise", "Mobile", "Media/Entertainment", "Fintech", "Healthcare Technology", "E-commerce"],
        "stage": "Seed through Series B; selective growth follow-ons",
        "geography": "US (New York City and Los Angeles)",
        "thesis": "Invests in technology at the intersection of media, commerce, and software. Strong belief in NY and LA ecosystems as complements to Silicon Valley. Capital efficiency emphasis.",
        "check_size": "$1M–$20M initial; up to $50M follow-on",
        "notable_portfolio": ["Bumble", "Venmo", "Acorns", "Bird", "Pluto TV", "Maker Studios", "Scopely", "Bright Health", "Trunk Club"],
        "differentiator": "One of the few funds with deep roots in both New York and Los Angeles. Strong access to media, advertising, and consumer deal flow. Partners include Alan Patricof (legendary media/tech investor).",
        "portfolio_count": 484,
    },
    "Salesforce Ventures": {
        "website": "https://www.salesforce.com/company/ventures",
        "focus_sectors": ["Enterprise SaaS", "CRM/Customer Experience", "AI/ML", "Data/Analytics", "Marketing Tech", "HR Tech", "Integration/Workflow Automation", "Industry Clouds"],
        "stage": "Series A through late-stage / pre-IPO",
        "geography": "Global — strong in US, Europe, Asia-Pacific",
        "thesis": "Strategic CVC arm of Salesforce. Invests in enterprise cloud companies extending the Salesforce ecosystem or building next-gen enterprise software. Portfolio gets access to Salesforce's 150,000+ customer base and AppExchange distribution.",
        "check_size": "$5M–$100M+",
        "notable_portfolio": ["DocuSign", "Veeva Systems", "Zoom", "nCino", "Twilio", "Dropbox", "Snowflake", "Databricks", "Monday.com", "Qualtrics", "GoCardless"],
        "differentiator": "One of the most active and largest CVCs globally. Unparalleled distribution leverage through Salesforce's enterprise customer base. Salesforce AppExchange gives portfolio companies direct go-to-market channels. Dedicated Impact Fund.",
        "portfolio_count": 466,
    },
    "Norwest Venture Partners": {
        "website": "https://www.nvp.com",
        "focus_sectors": ["Enterprise Software/SaaS", "Consumer", "Healthcare/Life Sciences", "Fintech", "AI/Data", "Infrastructure/DevOps"],
        "stage": "Seed through growth / pre-IPO; flexible across all stages",
        "geography": "US (Palo Alto primary); active in India and Israel",
        "thesis": "Multi-stage investor with long-term partnership mindset. Backed by Wells Fargo — provides patient capital without traditional fund cycle pressure. Founder-centric, low-ego partnership model.",
        "check_size": "$1M–$100M+ depending on stage",
        "notable_portfolio": ["Uber (early)", "Spotify", "Pendo", "Calm", "Intercom", "Sprinklr", "Samsara", "Daily Harvest", "Grail", "Talkdesk"],
        "differentiator": "Uniquely multi-stage and sector-agnostic within tech and healthcare. Backed by Wells Fargo — enables evergreen capital without traditional fund cycle pressure. Dedicated India practice — one of the most active US VCs in India.",
        "portfolio_count": 460,
    },
    "Matrix Partners": {
        "website": "https://www.matrixpartners.com",
        "focus_sectors": ["Enterprise Software/SaaS", "Infrastructure", "Consumer Internet", "Fintech", "Developer Tools", "Cybersecurity"],
        "stage": "Seed and Series A (primary focus); occasional Series B",
        "geography": "US (Boston and San Francisco); affiliated funds in India and China",
        "thesis": "Early-stage conviction investor. Deep sector research before meeting companies. Takes concentrated, high-conviction bets; works closely with founders from day one. 40+ year track record.",
        "check_size": "$1M–$20M at initial investment",
        "notable_portfolio": ["Apple (early)", "HubSpot", "Zendesk", "Oculus VR", "Canva", "Quora", "Drift", "CloudBees"],
        "differentiator": "One of the oldest VC franchises (founded 1977). 'Patient capital' approach. Strong operator-investor DNA. Separate affiliated funds in India (Matrix Partners India) and China (Matrix China) operate independently.",
        "portfolio_count": 452,
    },
    "Benchmark Capital": {
        "website": "https://www.benchmark.com",
        "focus_sectors": ["Consumer Internet", "Enterprise Software/SaaS", "Marketplaces", "Infrastructure", "AI", "Fintech"],
        "stage": "Seed and Series A exclusively (pure early-stage; refuses growth investing)",
        "geography": "US (San Francisco Bay Area primary); selective Europe",
        "thesis": "High-conviction, early-stage generalist. Writes small funds, takes concentrated positions in a handful of companies per year. Equal partnership model — all five partners earn equal carry with no hierarchy. The best returns come from being the first institutional capital in category-defining companies.",
        "check_size": "$5M–$25M initial",
        "notable_portfolio": ["Uber", "Twitter", "Snapchat", "Instagram", "eBay", "WeWork", "Yelp", "Discord", "Riot Games", "Stitch Fix", "New Relic"],
        "differentiator": "Legendary equal partnership model — no managing partner, no hierarchy. Intentionally small funds (~$425M–$500M) for discipline. Refuses to raise growth or opportunity funds — stays early-stage. Famous for Uber investment (~$12M → $7B+ return).",
        "portfolio_count": 451,
    },
    "East Ventures": {
        "website": "https://east.vc",
        "focus_sectors": ["Consumer Internet/E-commerce", "Fintech/Financial Inclusion", "SaaS/Enterprise", "HealthTech", "EdTech", "Logistics/Supply Chain", "Social Media/Gaming"],
        "stage": "Seed through Series B; Southeast Asia early-stage specialist",
        "geography": "Southeast Asia (Indonesia primary — Jakarta; also Singapore, Japan, Vietnam, Philippines)",
        "thesis": "Pioneer of tech venture investing in Southeast Asia, with Indonesia at the core. 680M people, rising middle class, rapidly mobilizing internet users — the next great frontier for technology company creation.",
        "check_size": "$100K–$5M at seed; up to $30M at Series A/B",
        "notable_portfolio": ["Tokopedia (acquired by GoTo)", "Traveloka", "Kudo (acquired by Grab)", "Ruangguru", "Sociolla", "KoinWorks", "Xendit", "Shipper"],
        "differentiator": "First mover advantage in Southeast Asia — began investing in 2009 when region was largely ignored. Tokopedia is a landmark portfolio company. Bridges Japanese and Southeast Asian tech ecosystems. Deep Indonesia-specific expertise.",
        "portfolio_count": 444,
    },
    "Institutional Venture Partners (IVP)": {
        "website": "https://www.ivp.com",
        "focus_sectors": ["Consumer Internet/Media", "SaaS/Enterprise", "Fintech", "Healthcare IT", "Infrastructure", "Cybersecurity"],
        "stage": "Later-stage growth (Series C, D, beyond); pre-IPO specialist",
        "geography": "US (primary); selective international",
        "thesis": "Growth-stage specialist investing in proven, high-velocity companies preparing for IPO. Backs the 'franchise players' of tech — companies with durable competitive moats. 40+ year track record, 110+ IPOs and 30+ acquisitions >$1B.",
        "check_size": "$30M–$200M per investment",
        "notable_portfolio": ["Twitter", "Netflix", "Snap", "Dropbox", "Github", "Figma", "Robinhood", "Coinbase", "UiPath", "HashiCorp", "Supercell", "Slack", "Datadog"],
        "differentiator": "One of the most successful late-stage/growth funds in history (founded 1980). Deep IPO expertise. Known for entering at Series C/D when risk profile is still venture-like but outcomes more predictable.",
        "portfolio_count": 432,
    },
    "CRV": {
        "website": "https://www.crv.com",
        "focus_sectors": ["Enterprise Software/SaaS", "Developer Tools/Infrastructure", "Consumer", "Fintech", "AI/ML", "Biotech/Healthcare"],
        "stage": "Seed and Series A (core focus)",
        "geography": "US (San Francisco Bay Area and Boston)",
        "thesis": "Early-stage firm backing extraordinary founders at the very beginning. Low ego, highly accessible partners, fast decisions, deep operational support. One of the continuously operating longest VC firms (founded 1970).",
        "check_size": "$1M–$15M at seed/Series A",
        "notable_portfolio": ["Twitter", "DoorDash", "Airtable", "Patreon", "Zendesk (early)", "HubSpot", "Vercel", "Loom"],
        "differentiator": "One of the oldest continuously operating venture firms (est. 1970). Bi-coastal with genuine depth in both Bay Area and Boston. Known for founder-friendly culture — same-week term sheets. Strong in developer-focused and infrastructure companies.",
        "portfolio_count": 420,
    },
    "Coatue Management": {
        "website": "https://www.coatue.com",
        "focus_sectors": ["Consumer Internet", "Enterprise SaaS", "Fintech", "AI/Data Infrastructure", "Gaming", "Healthcare Tech", "E-commerce/Marketplaces"],
        "stage": "Multi-stage: late-stage private (Series C–pre-IPO) through public equities; also seed via Coatue Ventures",
        "geography": "Global — US, China, India, Southeast Asia, Latin America",
        "thesis": "Technology-focused crossover investor. Uses deep quantitative and fundamental research to identify technology winners across public and private markets. Proprietary data science/quant team embedded in investment process.",
        "check_size": "$10M–$500M+ in private rounds; unlimited in public markets",
        "notable_portfolio": ["ByteDance (TikTok)", "Snap", "Lyft", "Instacart", "Didi", "Meituan", "Grab", "Chime", "Epic Games", "Discord", "Brex", "Plaid"],
        "differentiator": "One of the original 'Tiger Cubs' (founded by ex-Tiger Global analyst Philippe Laffont). Ability to invest across full company lifecycle in a single vehicle. Proprietary quant team in investment process. ~$50B+ total AUM.",
        "portfolio_count": 413,
    },
    "Canaan Partners": {
        "website": "https://www.canaan.com",
        "focus_sectors": ["Healthcare/Life Sciences", "Biotech/Therapeutics", "Enterprise Technology/SaaS", "Fintech", "Consumer Technology", "AI/ML"],
        "stage": "Early-stage: Seed through Series B; occasional growth",
        "geography": "US (Menlo Park and New York); Israel",
        "thesis": "Backs exceptional entrepreneurs at earliest stages in technology and healthcare. Unique dual focus: deep life sciences (therapeutics, diagnostics, devices) alongside enterprise and consumer technology. Believes in convergence of biology and technology.",
        "check_size": "$5M–$25M initial investment",
        "notable_portfolio": ["LendingClub", "Kabbage", "Instacart (early)", "Zulily", "DoubleClick", "Ebates", "Match.com"],
        "differentiator": "One of the few top-tier VCs with genuine equal depth in both technology and life sciences under one roof. Strong Israel presence — one of the earliest US VCs with consistent Israel deal flow. 35+ year track record, 200+ portfolio companies.",
        "portfolio_count": 412,
    },
    "Spark Capital": {
        "website": "https://www.sparkcapital.com",
        "focus_sectors": ["Consumer Internet", "Enterprise SaaS", "Fintech", "Crypto/Web3", "Gaming/Media", "AI", "Commerce/Marketplaces"],
        "stage": "Seed through Series B (early-stage focus); will follow on through growth",
        "geography": "US (Boston and San Francisco)",
        "thesis": "Backs transformative founders building category-defining companies. Does not constrain to specific sectors — follows exceptional founders. Emphasis on companies that reshape behavior at scale, particularly at the intersection of consumer behavior and technology.",
        "check_size": "$1M–$30M at initial check; significant reserves for follow-on",
        "notable_portfolio": ["Twitter", "Tumblr", "Oculus VR", "Slack", "Coinbase", "Affirm", "Postmates", "Discord", "Wayfair", "Plaid"],
        "differentiator": "Known for backing culturally resonant tech companies. Strong consumer behavior change thesis. Bi-coastal (Boston/SF). Small, high-conviction team — partners carry limited portfolio sizes for maximum attention.",
        "portfolio_count": 410,
    },
    "Qiming Venture Partners": {
        "website": "https://www.qimingvc.com/en",
        "focus_sectors": ["Healthcare/Life Sciences", "Technology (AI, SaaS, Enterprise)", "Consumer Internet", "Clean Energy", "Biotech/Biopharma", "Medical Devices/Diagnostics"],
        "stage": "Series A through Series C; some seed",
        "geography": "China (primary — Shanghai, Beijing, Shenzhen); selective US cross-border",
        "thesis": "Leading China-focused venture fund with dual mandate: technology companies and healthcare/life sciences. China's healthcare modernization and tech innovation are two of the largest wealth-creation opportunities of the next decade.",
        "check_size": "$5M–$50M per investment",
        "notable_portfolio": ["Xiaomi", "Meituan Dianping", "Bilibili", "ZTO Express", "Zai Lab", "BeiGene (early)", "WuXi AppTec (early)", "Nuro (US)"],
        "differentiator": "Top-tier China VC with exceptional healthcare-tech balance. Founded by Gary Rieschel (formerly Softbank Venture Capital). Xiaomi investment is one of the most successful China VC bets ever. Strong US-China bridge.",
        "portfolio_count": 409,
    },
    "Shunwei Capital Partners": {
        "website": "https://www.shunwei.com",
        "focus_sectors": ["Mobile Internet", "Consumer Applications", "AI/ML", "Short Video/Entertainment", "EdTech", "HealthTech", "Smart Hardware/IoT", "Southeast Asia Tech"],
        "stage": "Series A through Series C",
        "geography": "China (primary); Southeast Asia; India",
        "thesis": "Mobile internet-focused VC co-founded by Xiaomi's Lei Jun. Mobile will reshape every aspect of Chinese consumer and enterprise life. Leverages deep connection to Xiaomi ecosystem to identify and accelerate portfolio companies.",
        "check_size": "$5M–$30M per investment",
        "notable_portfolio": ["Xiaomi (ecosystem)", "Cheetah Mobile", "Musical.ly (acquired by ByteDance → TikTok)", "ShareChat (India)", "YY Live"],
        "differentiator": "Unique Xiaomi ecosystem advantage — portfolio gets access to Xiaomi's 300M+ device user base for distribution. Co-founded by Lei Jun (Xiaomi CEO). Early bet on Musical.ly (became TikTok).",
        "portfolio_count": 401,
    },
    "Menlo Ventures": {
        "website": "https://www.menlovc.com",
        "focus_sectors": ["AI/Generative AI", "Enterprise SaaS", "Cybersecurity", "Consumer Technology", "Infrastructure/DevOps", "Fintech"],
        "stage": "Early-stage (Seed, Series A) through growth (Series B/C)",
        "geography": "US (Menlo Park, California)",
        "thesis": "Invests in technology redefining how people work, communicate, and live. Pivoted heavily toward AI/generative AI — one of the earliest and most vocal advocates of the generative AI wave. AI will fundamentally restructure every software category.",
        "check_size": "$5M–$30M initial; up to $100M in growth rounds",
        "notable_portfolio": ["Uber (early)", "Anthropic (major backer)", "Poshmark", "Benchling", "Chime", "Carta", "Abnormal Security", "Pinecone"],
        "differentiator": "Silicon Valley's oldest VC firm (founded 1976) that has successfully reinvented itself. Defining $100M bet on Anthropic — one of the most talked-about VC positions of the AI era. Strong cybersecurity and infrastructure thesis alongside AI.",
        "portfolio_count": 400,
    },
}


# Secondary intelligence: firm categorization for quick matching
VC_STAGE_MAP = {
    "pre_seed_seed": ["500 Global", "Kima Ventures", "First Round Capital", "SV Angel", "TechStars", "SOSV"],
    "early_stage": ["Sequoia Capital", "Accel", "Kleiner Perkins", "Greylock Partners", "Benchmark Capital",
                    "Matrix Partners", "CRV", "Spark Capital", "Canaan Partners", "East Ventures",
                    "Khosla Ventures", "Founders Fund", "Redpoint Ventures", "Greycroft Partners"],
    "multi_stage": ["Andreessen Horowitz (a16z)", "New Enterprise Associates (NEA)", "General Catalyst",
                    "Lightspeed Venture Partners", "Bessemer Venture Partners", "Index Ventures",
                    "Battery Ventures", "GV (Google Ventures)", "Norwest Venture Partners",
                    "Menlo Ventures", "Coatue Management", "Intel Capital", "IDG Capital"],
    "growth_late": ["Insight Partners", "Tiger Global Management", "DST Global",
                    "Institutional Venture Partners (IVP)", "SB Investment Advisers (Vision Fund)",
                    "GGV Capital"],
}

VC_GEOGRAPHY_MAP = {
    "india_active": ["Sequoia Capital", "Accel", "New Enterprise Associates (NEA)", "Lightspeed Venture Partners",
                     "Norwest Venture Partners", "Matrix Partners", "General Catalyst",
                     "500 Global", "Tiger Global Management"],
    "southeast_asia": ["East Ventures", "500 Global", "GGV Capital", "Sequoia Capital"],
    "china_focused": ["IDG Capital", "GGV Capital", "Qiming Venture Partners", "Shunwei Capital Partners",
                      "Tiger Global Management"],
    "europe_strong": ["Index Ventures", "Kima Ventures", "Global Founders Capital",
                      "Greycroft Partners", "Accel", "SB Investment Advisers (Vision Fund)"],
    "us_only": ["Benchmark Capital", "Founders Fund", "Spark Capital", "CRV", "Menlo Ventures",
                "Institutional Venture Partners (IVP)"],
}

VC_SECTOR_SPECIALISTS = {
    "deep_tech_science": ["Founders Fund", "Khosla Ventures", "SOSV", "High-Tech Gründerfonds"],
    "enterprise_saas": ["Insight Partners", "Bessemer Venture Partners", "Accel",
                        "Salesforce Ventures", "Battery Ventures", "Redpoint Ventures"],
    "healthcare_biotech": ["New Enterprise Associates (NEA)", "GV (Google Ventures)",
                           "Canaan Partners", "Qiming Venture Partners", "General Catalyst"],
    "consumer": ["Sequoia Capital", "Benchmark Capital", "Andreessen Horowitz (a16z)",
                 "Founders Fund", "Index Ventures"],
    "crypto_web3": ["Andreessen Horowitz (a16z)", "Spark Capital", "Coinbase Ventures"],
    "defense_national_security": ["Andreessen Horowitz (a16z)", "General Catalyst", "Founders Fund"],
    "climate_energy": ["Khosla Ventures", "General Catalyst", "Founders Fund", "Kleiner Perkins"],
}


def get_vc_firms_intel_context(firm_name: str = "", sector: str = "", stage: str = "") -> str:
    """Return VC firm intelligence. If firm_name given, returns that firm's profile.
    If sector/stage given, returns relevant firms. Otherwise returns overview."""
    lines = []

    # Specific firm lookup
    if firm_name:
        # Try exact match first, then partial match
        matched = None
        for name, data in VC_FIRMS_INTEL.items():
            if firm_name.lower() in name.lower() or name.lower() in firm_name.lower():
                matched = (name, data)
                break
        if matched:
            name, data = matched
            lines.append(f"## {name} — Firm Intelligence\n")
            lines.append(f"- **Website**: {data['website']}")
            lines.append(f"- **Focus Sectors**: {', '.join(data['focus_sectors'][:6])}")
            lines.append(f"- **Stage**: {data['stage']}")
            lines.append(f"- **Geography**: {data['geography']}")
            lines.append(f"- **Thesis**: {data['thesis']}")
            lines.append(f"- **Check Size**: {data['check_size']}")
            lines.append(f"- **Notable Portfolio**: {', '.join(data['notable_portfolio'][:8])}")
            lines.append(f"- **Differentiator**: {data['differentiator']}")
            return "\n".join(lines)

    # Stage-filtered overview
    lines.append("## VC Landscape — Firm Intelligence Summary\n")

    # Top 10 firms by portfolio size as quick reference
    lines.append("### Top Firms by Portfolio Scale")
    for name, data in list(VC_FIRMS_INTEL.items())[:10]:
        lines.append(f"- **{name}** ({data['portfolio_count']} companies): {data['stage'][:60]}... | {data['geography'][:50]}")

    lines.append("\n### Stage Specialization")
    for stage_key, firms in VC_STAGE_MAP.items():
        label = stage_key.replace("_", " ").title()
        lines.append(f"- **{label}**: {', '.join(firms[:5])}")

    lines.append("\n### India-Active Firms")
    india_firms = VC_GEOGRAPHY_MAP.get("india_active", [])
    for firm in india_firms:
        data = VC_FIRMS_INTEL.get(firm, {})
        if data:
            lines.append(f"- **{firm}**: {data.get('thesis', '')[:80]}...")

    lines.append("\n### Sector Specialists")
    for sector_key, firms in VC_SECTOR_SPECIALISTS.items():
        label = sector_key.replace("_", " ").title()
        lines.append(f"- **{label}**: {', '.join(firms[:4])}")

    return "\n".join(lines)


def get_firm_fit_context(startup_description: str, sector: str = "", stage: str = "") -> str:
    """Given a startup description/sector/stage, return the most relevant VC firms and their fit."""
    lines = ["## VC Firm Fit Analysis\n"]

    relevant_firms = []

    # Stage-based filtering
    stage_key_map = {
        "idea": "pre_seed_seed",
        "pre-revenue": "pre_seed_seed",
        "early-revenue": "early_stage",
        "growth": "growth_late",
    }
    stage_key = stage_key_map.get(stage, "early_stage")
    stage_firms = set(VC_STAGE_MAP.get(stage_key, []) + VC_STAGE_MAP.get("multi_stage", []))

    # Sector-based filtering
    sector_firms = set()
    sector_key_map = {
        "saas": "enterprise_saas",
        "d2c": "consumer",
        "fintech": "enterprise_saas",
        "marketplace": "consumer",
    }
    sector_key = sector_key_map.get(sector, "")
    if sector_key:
        sector_firms = set(VC_SECTOR_SPECIALISTS.get(sector_key, []))

    # Combine and rank by overlap
    combined = stage_firms & sector_firms if sector_firms else stage_firms
    if not combined:
        combined = stage_firms

    for firm in list(combined)[:8]:
        data = VC_FIRMS_INTEL.get(firm, {})
        if data:
            relevant_firms.append((firm, data))

    lines.append(f"For a **{stage or 'early stage'}** startup in **{sector or 'your sector'}**:\n")
    for firm, data in relevant_firms[:6]:
        lines.append(f"### {firm}")
        lines.append(f"- Thesis: {data.get('thesis', '')[:120]}...")
        lines.append(f"- Check Size: {data.get('check_size', 'Unknown')}")
        lines.append(f"- What they look for: {data.get('differentiator', '')[:100]}...")
        lines.append("")

    return "\n".join(lines)
