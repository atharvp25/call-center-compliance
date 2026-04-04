import requests, base64, json, time

API = "http://127.0.0.1:8001/api/call-analytics"
KEY = "hcl-guvi-hackathon-2026"

tests = [("test1.mp3", "Hindi"), ("test2.mp3", "Hindi")]

for f, lang in tests:
    sep = "=" * 60
    print(f"\n{sep}")
    print(f"Testing: {f} | Language: {lang}")
    print(sep)
    
    with open(f, "rb") as fp:
        b64 = base64.b64encode(fp.read()).decode()
    print(f"File size: {len(b64)//1024} KB (base64)")
    
    t0 = time.time()
    r = requests.post(
        API,
        json={"language": lang, "audioFormat": "mp3", "audioBase64": b64},
        headers={"x-api-key": KEY, "Content-Type": "application/json"},
        timeout=120,
    )
    elapsed = time.time() - t0
    
    print(f"Status: {r.status_code} | Time: {elapsed:.1f}s")
    
    if r.status_code == 200:
        d = r.json()
        print(f"Transcript: {d['transcript'][:150]}...")
        print(f"Summary: {d['summary'][:200]}")
        print(f"SOP: {d['sop_validation']}")
        print(f"Analytics: {d['analytics']}")
        print(f"Keywords: {d['keywords']}")
        out = f.replace(".mp3", "_result.json")
        json.dump(d, open(out, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
        print(f"Saved to {out}")
    else:
        print(f"ERROR: {r.text[:300]}")
