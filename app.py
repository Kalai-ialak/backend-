from flask import Flask, json, request, jsonify, make_response
from flask_cors import CORS
from firebase_config import df_firestore
from datetime import datetime, timedelta
from firebase_admin import auth
import re
import traceback
from together import Together
import os

app = Flask(__name__)

CORS(app)

# --- Rule-based title generator ---
def generate_title_rule(text):
    stop_words = {"how", "to", "and", "in", "the", "a", "of", "for", "is"}
    
    words = re.findall(r'\w+', text.lower())
    words = [w for w in words if w not in stop_words]

    title = " ".join(words[:5]).title()
    return title

client = Together(api_key=os.getenv("TOGETHER_API_KEY"))

def generate_title_llm(text):
    prompt = f"""
    You are a system that generates short chat titles.

    Rules:
    - Max 3-5 words
    - Be concise and meaningful
    - Do NOT repeat the input
    - Convert greetings into category names
    - Convert comparisons into "X vs Y"
    - Convert errors into "X Error" or "Fix X Error"
    - Remove filler words like "how", "what", "explain"

    Examples:
    Input: Good morning
    Output: Greetings

    Input: Difference between BERT and GPT
    Output: BERT vs GPT

    Input: How to fix Redis connection error
    Output: Redis Connection Error

    Input: Explain Flask GET and POST methods
    Output: Flask GET POST Methods

    Now generate:

    Input: {text}
    Output:
    """

    response = client.chat.completions.create(
        model=os.getenv("MODEL"),
        messages=[
            {"role": "user", "content": prompt}
        ],
        max_tokens=20,
        temperature=0.3
    )

    title = response.choices[0].message.content.strip()
    print(title)

    return title

@app.route('/')
def home():
  return "Hello, this is Zukko API"

@app.route("/login", methods=["POST"])
def login():
    data = request.get_json(silent=True) or {}
    id_token = data.get("idToken")
    user_uid = data.get("localId")
    mail_id = data.get("email")
    firstname = data.get("firstName")
    lastname = data.get("lastName")
    displayname = data.get("displayName")
    photo_url = data.get("photoUrl")

    if not id_token:
        return jsonify({"error": "idToken missing"}), 400
    try:
        decoded = auth.verify_id_token(id_token)  # verifies token from Firebase client
        uid = decoded["uid"]

        #  Firebase session cookie (server-side session)
        # expires_in = timedelta(days=7)    # choose your lifetime
        # session_cookie = auth.create_session_cookie(id_token, expires_in=expires_in)
        resp = make_response(jsonify({"message": "ok", "uid": uid}))

        df_firestore.collection("users").document(uid).set({
           "user_uid": user_uid,
           "access_token": id_token,
           "mail_id" : mail_id,
           "firstname" : firstname,
           "lastname" : lastname,
           "displayname" : displayname,
           "photo_url": photo_url,
           "created_at": datetime.utcnow()
        },merge=True)

        return resp
    except Exception as e:
        return jsonify({"error": str(e)}), 403
    
@app.route("/generate-title", methods=["POST"])
def generate_title():
    data = request.get_json() or {}
    text = data.get("text")
    user_uid = data.get("user_uid")
    session_id = data.get("session_id")

    if not text:
        return jsonify({"error": "Text is required"}), 400
    
    print("Calling LLM...")
    title = generate_title_llm(text)
    
    if not title:
        print("rule based generated title...")
        title = generate_title_rule(text)

    df_firestore.collection("session").document(user_uid).collection("session_ids").document(session_id).set({
        "text" : text,
        "title" : title,
        "created_at": datetime.utcnow()

    })

    return jsonify({
        "input": text,
        "title": title
    })


@app.route("/get_sessions", methods=["POST"])
def get_sessions():
    data = request.get_json() or {}
    user_uid = data.get("user_uid")

    if not user_uid:
        return jsonify({"error": "user_uid is required"}), 400

    try:
        sessions_ref = df_firestore.collection("session") \
            .document(user_uid) \
            .collection("session_ids")

        docs = sessions_ref.stream()

        session_list = []

        for doc in docs:
            doc_data = doc.to_dict()

            session_list.append({
                "session_id": doc.id,
                "title": doc_data.get("title"),
                "text": doc_data.get("text"),
                "created_at": doc_data.get("created_at").isoformat() if doc_data.get("created_at") else None
            })

        # Optional: sort by latest (if you add timestamp later)
        session_list.sort(key=lambda x: x["created_at"], reverse=True)

        return session_list

        # return jsonify({
        #     "sessions": session_list
        # })
    
    except Exception as e:
        print(traceback.format_exc())
        return jsonify({"error": str(e)}), 500
    
if __name__ == "__main__":
  app.run()
