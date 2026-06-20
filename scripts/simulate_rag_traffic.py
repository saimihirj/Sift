import httpx
import json
import time
import sys

API_BASE = "http://localhost:8000"
CLIENT_ID = "synthetic-bot-001"

PERSONAS = [
    {
        "name": "The Hesitant Founder",
        "session": {
            "sessionType": "mentor",
            "provider": "ollama",
            "model": "qwen3:8b",
            "sector": "healthtech",
            "stage": "idea",
            "founderType": "founder",
            "mode": "think_it_through",
            "setupContext": "Building a tool for doctors."
        },
        "turns": [
            "We want to reduce paperwork.",
            "I don't know, maybe using AI to transcribe?",
            "Yes, we'd sell it to small clinics first.",
            "I'm not sure how to price it. Maybe $50 a month?",
        ]
    },
    {
        "name": "The Over-Explainer",
        "session": {
            "sessionType": "mentor",
            "provider": "ollama",
            "model": "qwen3:8b",
            "sector": "saas",
            "stage": "early-revenue",
            "founderType": "operator",
            "mode": "quick_stress_test",
            "setupContext": "An AI-native CRM that completely replaces Salesforce by ingesting all emails, Slack messages, and Notion docs to automatically build the pipeline."
        },
        "turns": [
            "The main problem is that sales reps hate data entry. So our system uses a multi-agent orchestration layer. We have one agent that reads the email, extracts the intent, scores the lead based on a proprietary NLP model we fine-tuned, and then another agent actually drafts the reply, but it waits for human approval, except for Tier 3 leads which get auto-replies. I think this will save 40 hours a week per rep.",
            "Our ideal customer profile is mid-market tech companies with 50-200 employees. We are targeting VP of Sales. The challenge is they are locked into Salesforce contracts. But we offer a sync layer so they can use us as a front-end, while Salesforce acts as the system of record. We built a bi-directional sync engine using Postgres logical replication.",
            "Wait, maybe we shouldn't do the sync. Maybe we just focus purely on the SDR use case first? Just inbound lead qualification?",
        ]
    },
    {
        "name": "The Pivot",
        "session": {
            "sessionType": "expert",
            "provider": "ollama",
            "model": "qwen3:8b",
            "sector": "unknown",
            "stage": "idea",
            "founderType": "other",
            "mode": "think_it_through",
            "setupContext": "A new social network for dog owners to find playdates."
        },
        "turns": [
            "Users will swipe on dogs they want their dog to play with.",
            "Actually, acquiring users is too hard. Let's pivot. We are now building B2B software for dog daycares to manage their bookings.",
            "The market for dog daycares is fragmented. We can offer a simple scheduling tool with Stripe integration. How do we do go-to-market for this?",
        ]
    }
]

def simulate_chat(session_id: str, message: str, provider: str, model: str):
    print(f"\n[User]: {message}")
    print(f"[Assistant]: ", end="", flush=True)
    
    payload = {
        "sessionId": session_id,
        "clientId": CLIENT_ID,
        "message": message,
        "provider": provider,
        "model": model,
        "responseProfile": "balanced",
    }
    
    full_response = ""
    with httpx.stream("POST", f"{API_BASE}/api/chat", data=payload, timeout=300.0) as r:
        if r.status_code != 200:
            print(f"Error: HTTP {r.status_code}")
            return
            
        for line in r.iter_lines():
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "delta" in data:
                        print(data["delta"], end="", flush=True)
                        full_response += data["delta"]
                except Exception:
                    pass
    print() # Newline after response

def run_simulation(dry_run=False):
    print("=== Starting Synthetic RAG Simulation ===")
    
    if dry_run:
        print("Dry run enabled. Exiting.")
        return

    for persona in PERSONAS:
        print(f"\n\n--- Persona: {persona['name']} ---")
        
        try:
            # 1. Start Session
            res = httpx.post(f"{API_BASE}/api/session/start", json={
                "clientId": CLIENT_ID,
                "displayName": persona["name"],
                "sessionType": persona["session"]["sessionType"],
                "provider": persona["session"]["provider"],
                "model": persona["session"]["model"],
                "sector": persona["session"]["sector"],
                "stage": persona["session"]["stage"],
                "founderType": persona["session"]["founderType"],
                "mode": persona["session"]["mode"],
                "setupContext": persona["session"]["setupContext"]
            }, timeout=120.0)
            
            if res.status_code != 200:
                print(f"Failed to start session: {res.text}")
                continue
                
            session_data = res.json()
            session_id = session_data["sessionId"]
            print(f"Session started: {session_id}")
            print(f"[Assistant]: {session_data.get('openingMessage', '')}")
            
            time.sleep(1) # Breathe before first chat
            
            # 2. Iterate Turns
            for turn in persona["turns"]:
                simulate_chat(
                    session_id, 
                    turn, 
                    persona["session"]["provider"], 
                    persona["session"]["model"]
                )
                time.sleep(3) # Safe delay for 16GB RAM
                
        except Exception as e:
            print(f"Error running persona: {e}")
            
        print("\nCooling down for 5 seconds before next persona...")
        time.sleep(5)
        
    print("\n=== Simulation Complete ===")

if __name__ == "__main__":
    dry_run = "--dry-run" in sys.argv
    run_simulation(dry_run=dry_run)
