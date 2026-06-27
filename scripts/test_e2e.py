import os
import requests
import json
import time

API_BASE = "https://sift-987f.onrender.com"
FILE_PATH = "/Users/saimihirj/Desktop/Ideas/sift/TrueGene Pitch Deck NSRCEL.pdf"

def main():
    print("🚀 Starting End-to-End Test on LIVE Sift API...")
    
    # 1. Start Session
    print("\n1️⃣  Starting Session...")
    res = requests.post(
        f"{API_BASE}/api/session/start",
        json={
            "provider": "groq",
            "model": "",
            "sessionType": "evaluator",
            "founderType": "founder",
            "stage": "idea"
        }
    )
    if not res.ok:
        print("Failed to start session:", res.text)
        return
    session_data = res.json()
    session_id = session_data["sessionId"]
    print(f"✅ Session created: {session_id}")

    # 2. Upload File
    print(f"\n2️⃣  Uploading File: {os.path.basename(FILE_PATH)}...")
    with open(FILE_PATH, "rb") as f:
        res = requests.post(
            f"{API_BASE}/api/session/{session_id}/upload",
            files={"file": (os.path.basename(FILE_PATH), f, "application/pdf")}
        )
    if not res.ok:
        print("Failed to upload file:", res.text)
        return
    upload_data = res.json()
    print(f"✅ Upload successful. File ID: {upload_data.get('id', 'N/A')}")

    # 3. Evaluate Deck
    print("\n3️⃣  Evaluating Deck (this may take 10-20 seconds)...")
    res = requests.post(f"{API_BASE}/api/session/{session_id}/evaluate")
    if not res.ok:
        print("Failed to evaluate:", res.text)
        return
    eval_data = res.json()
    score = eval_data.get("readinessScore")
    issues = eval_data.get("issues", [])
    print(f"✅ Evaluation complete! Readiness Score: {score}/100")
    print(f"✅ Found {len(issues)} issues:")
    for i, issue in enumerate(issues[:3], 1):
        print(f"   {i}. {issue}")
    if len(issues) > 3:
        print(f"   ... and {len(issues) - 3} more")

    # 4. Chat with Sift
    print("\n4️⃣  Testing Chat with Sift...")
    chat_res = requests.post(
        f"{API_BASE}/api/chat",
        data={"sessionId": session_id, "message": "Can you help me fix the first issue?"},
        stream=True
    )
    if not chat_res.ok:
        print("Failed to start chat:", chat_res.text)
        return
        
    print("✅ Chat connected! Streaming response:")
    for line in chat_res.iter_lines():
        if line:
            line = line.decode('utf-8')
            if line.startswith("data: "):
                try:
                    data = json.loads(line[6:])
                    if "delta" in data:
                        print(data["delta"], end="", flush=True)
                    elif "message" in data:
                        print(f"\n[ERROR MESSAGE FROM BACKEND]: {data['message']}")
                except:
                    pass
    print("\n\n✅ Chat test complete!")
    print("🎉 End-to-End Test Passed Successfully!")

if __name__ == "__main__":
    main()
