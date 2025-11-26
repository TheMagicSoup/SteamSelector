from flask import Flask, render_template, request, jsonify
from functools import lru_cache
from dotenv import load_dotenv
import os
import json
import requests
import re
from pathlib import Path

app = Flask(__name__)

lru_cache(maxsize=1024)
CACHE_FILE = Path("vanity_cache.json")
if CACHE_FILE.exists():
    with open(CACHE_FILE, "r") as f:
        vanity_cache = json.load(f)
else:
    vanity_cache = {}
load_dotenv()

_KEY = os.getenv("STEAM_API_KEY")

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(vanity_cache, f)

def getSteamID(val: str) -> str | None:
    matchNum = re.match(r"[0-9]{17}$",val)
    if matchNum:
        return matchNum.group(0)
    
    matchURL=re.search(r"/profiles/([0-9]{17})",val)
    if matchURL:
        return matchURL.group(1)
    
    matchVanity=re.search(r"/id/([A-Za-z0-9_-]+)",val)
    if matchVanity:
        return matchVanity.group(1)
    
    return None

def isSteamID64(val: str) -> bool:
    return val.isdigit() and len(val)==17

def checkVanity(vanity: str) -> str | None:
    if vanity in vanity_cache:
        return vanity_cache[vanity]
    url="https://api.steampowered.com/ISteamUser/ResolveVanityURL/v1/"
    params={"key": _KEY, "vanityurl": vanity}
    try:
        response = requests.get(url, params=params).json()
        steamID = response.get("response", {}).get("steamid")
        if steamID:
            vanity_cache[vanity] = steamID
            save_cache()
        return steamID
    except Exception:
        return None

def getProfileData(steamID: str) -> dict | None:
    url="https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/"
    params={"key": _KEY, "steamids": steamID}
    try:
        response=requests.get(url, params=params).json()
        return response.get("response", {}).get("players", [])[0]
    except Exception:
        return None
@app.route("/")
def index():
    return render_template("index.html")

@app.route("/submit", methods=["POST"])
def submit():
    steamInput=request.form.get("steamInput")
    sid=getSteamID(steamInput)
    if not sid:
        return render_template("index.html", error="Invalid entry.")
    if not isSteamID64(sid):
        sid=checkVanity(sid)
        if not sid:
            return render_template("badid.html")
    profileData=getProfileData(sid)
    print(profileData)
    return render_template("results.html", profile=profileData)

if __name__ == "__main__":
    app.run(debug=True)