from flask import Flask, render_template, request, jsonify, redirect, url_for, session
#from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel
from sklearn.preprocessing import normalize
from dotenv import load_dotenv
import pandas as pd
import os
import math
import json
import numpy as np
import requests
import re
from pathlib import Path
import pickle

# Minimum number of owners for a game to be included in the dataset
MIN_OWNERS = 30000
# Weights for the categories involved in each game's document representation
TAGS_WEIGHT=3
GENRES_WEIGHT=2
CATEGORIES_WEIGHT=1
ABOUT_THE_GAME_WEIGHT=1
# Number of recommendations returned
TOP_N=5

app = Flask(__name__)
app.secret_key = os.urandom(24)

user_cache={}

with open("model.pkl","rb") as f:
    model=pickle.load(f)

df=model["df"]
tfidf_matrix=model["tfidf_matrix"]
cosine_sim=model["cosine_sim"]
vectorizer=model["vectorizer"]

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

def getRecentlyPlayedGames(steamID: str) -> list | None:
    url="https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/"
    params={"key": _KEY, "steamid": steamID}
    try:
        response=requests.get(url, params=params).json()
        return response.get("response", {}).get("games",[])
    except Exception:
        return None

def getOwnedGames(steamID: str) -> list | None:
    url="https://api.steampowered.com/IPlayerService/GetOwnedGames/v1/"
    params={"key": _KEY, "steamid": steamID, "include_appinfo": True}
    try:
        response=requests.get(url, params=params).json()
        return response.get("response", {}).get("games",[])
    except Exception:
        return None

def getTopGames(owned_games: list, n: int=20) -> list:
    top_games=sorted(owned_games, key=lambda x: x.get("playtime_forever",0),reverse=True)[:n]
    return top_games

def getGameData(appid: str) -> list:
    url="https://steamspy.com/api.php?request=appdetails"
    params={"appid": appid}
    try:
        response=requests.get(url, params=params).json()
        return response
    except Exception:
        return []

def get_min_owners(c):
    return int(c.split("-")[0])

def recommend(recent,owned,top_n=TOP_N):
    user_vector=np.zeros(tfidf_matrix.shape[1])
    for g in recent:
        appid=g["appid"]
        if appid not in appid_indices:
            continue
        idx=appid_indices[appid]
        weight=math.log1p(g["playtime_2weeks"])
        user_vector+=tfidf_matrix[idx].toarray().flatten()*weight
    if np.all(user_vector==0):
        return "No valid recently played games found."
    user_vector=normalize(user_vector.reshape(1,-1))
    sim_scores=linear_kernel(user_vector,tfidf_matrix).flatten()
    top_indices=sim_scores.argsort()[::-1]
    owned_appids=set(game["appid"] for game in owned)
    results=[]
    print("TOP CANDIDATES:")
    for i in top_indices:
        print(df.iloc[i]["Name"], df.iloc[i]["AppID"])
        appid=df.iloc[i]["AppID"]
        if appid in owned_appids:
            continue
        results.append({
            "appid": int(appid),
            "name": df.iloc[i]["Name"]
        })
        if len(results)==top_n:
            break
    print(results)
    return results

# Creating a Series mapping AppIDs to indices
appid_indices=pd.Series(df.index,index=df["AppID"]).drop_duplicates()

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
    if not profileData:
        return render_template("badid.html")
    recent=getRecentlyPlayedGames(sid)
    owned=getOwnedGames(sid)
    session["profileData"]=profileData
    session["recentlyPlayedGames"]=recent
    user_cache[sid]={
        "steamid": sid,
        "profile": profileData,
        "recent": recent,
        "owned": owned
    }
    return redirect(url_for("results"))

@app.route("/api/recommend")
def api_recommend():
    userid=session.get("profileData")["steamid"]

    if not userid or userid not in user_cache:
        return jsonify([])
    
    data = user_cache[userid]
    recs=recommend(data["recent"],data["owned"])
    return jsonify(recs)


@app.route("/results")
def results():
    userid=session.get("profileData")["steamid"]
    if not userid or userid not in user_cache:
        return redirect(url_for("index"))
    data=user_cache[userid]
    return render_template("results.html", profile=data["profile"], recentlyPlayedGames=data["recent"][:4])
 
if __name__ == "__main__":
    app.run(debug=True)