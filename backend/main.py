from fastapi import FastAPI, Request, HTTPException
import json
import traceback

app = FastAPI()

from infra.setup_gmail_watch import register_watch  # or wherever it's defined

@app.get("/refresh_watch")
async def refresh_watch():
    try:
        register_watch()
        return {"status": "watch refreshed ✅"}
    except Exception as e:
        return {"status": f"failed ❌ {str(e)}"}


@app.post("/pubsub")
async def pubsub_webhook(request: Request):
    """Receives Pub/Sub push messages from Gmail watch notifications."""
    try:
        envelope = await request.json()
        print("📩 Raw envelope:", json.dumps(envelope, indent=2))

        if "message" not in envelope or "data" not in envelope["message"]:
            print("❌ Invalid format:", envelope)
            raise HTTPException(status_code=400, detail="Invalid Pub/Sub message format")

        from .pubsub_handler import handle_pubsub_message
        await handle_pubsub_message(envelope)

        print("✅ Pub/Sub message handled successfully")
        return {"status": "ok"}

    except Exception as e:
        print("🔥 Exception in /pubsub:", e)
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))
