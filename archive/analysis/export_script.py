from google.cloud import firestore
import pandas as pd

db = firestore.Client()
docs = db.collection("channel").where("is_bot_checked", "==", True).stream()

rows = []
for doc in docs:
    d = doc.to_dict()
    print(d.get("is_bot"))
    metrics = d.get("avatar_metrics") or d.get("metrics")
    if metrics:
        rows.append({
            "channel_id": doc.id,
            **{m: metrics.get(m) for m in [
                "sat_mean","white","skin","ed","sat_std",
                "sym","lines","var","dom","bright","entropy"
            ]},
            "label": int(d.get("is_bot"))
        })

df = pd.DataFrame(rows)
df.to_csv("bot_metrics.csv", index=False)
