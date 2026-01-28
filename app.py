from flask import Flask, render_template, request, jsonify, redirect, url_for, session
#from functools import lru_cache
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from dotenv import load_dotenv
import pandas as pd
import os
import json
import numpy as np
import requests
import re
import numpy
from pathlib import Path

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
    params={"key": _KEY, "steamid": steamID, "count": 4}
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

def build_tfidf_matrix(text_features, max_features=5000):
    vectorizer=TfidfVectorizer(stop_words="english",max_features=max_features)
    tfidf_matrix=vectorizer.fit_transform(text_features)
    return tfidf_matrix, vectorizer

def build_appid_index(df):
    return { appid: i  for i,appid in enumerate(df["appid"]) }

def build_game_df(owned_games: list):
    rows=[]
    games=getTopGames(owned_games)
    for game in games:
        appid=game["appid"]
        meta=getGameData(str(appid))
        if not meta:
            continue
        print(meta["name"])
        rows.append({
            "appid": appid,
            "name": meta.get("name"),
            "genres": meta.get("genre","").split(","),
            "tags": meta.get("tags",{}).keys(),
            "playtime_forever": game.get("playtime_forever",0),
            "playtime_2weeks":game.get("playtime_2weeks",0)
        })
        df=pd.DataFrame(rows)
        df["text_features"]=(
            df["genres"].apply(" ".join)+" "+
            df["tags"].apply(" ".join)
        )
    return df

def build_user_vector(df, tfidf_matrix, appid_to_index, owned_appids):
    vectors=[]
    for appid in owned_appids:
        if appid in appid_to_index:
            idx=appid_to_index[appid]
            vectors.append(tfidf_matrix[idx])
    if not vectors:
        return None
    
    user_vector=np.mean(vectors, axis=0)
    return user_vector

def apply_playtime_weight(df, user_vector):
    TOTAL_WEIGHT=0.7
    RECENT_WEIGHT=0.3
    weights=(
        TOTAL_WEIGHT * df["playtime_forever"] +
        RECENT_WEIGHT * df["playtime_2weeks"]
    )
    norm_weights = weights / (weights.max() + 1e-6)
    weighted_vector = user_vector.multiply(norm_weights.mean())
    return weighted_vector

def compute_similarity(user_vector, tfidf_matrix):
    similarities=cosine_similarity(user_vector, tfidf_matrix)
    return similarities.flatten()

def recommend(df, similarities, owned_appids, top_n=10):
    df=df.copy()
    df["similarity"]=similarities
    recommendations=df[~df["appid"].isin(owned_appids)].sort_values(by="similarity",ascending=False).head(top_n)
    return recommendations[["appid","name","similarity"]]

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
    owned_appids=[game["appid"] for game in owned]
    df=build_game_df(owned)
    tfidf_matrix, vectorizer=build_tfidf_matrix(df["text_features"])
    appid_to_index=build_appid_index(df)
    user_vector = build_user_vector(df, tfidf_matrix, appid_to_index, owned_appids)
    user_vector = apply_playtime_weight(df, user_vector)
    similarities = compute_similarity(user_vector, tfidf_matrix)
    recommendations = recommend(df, similarities, owned_appids)
    print(recommendations)
    return redirect(url_for("results"))

@app.route("/results")
def results():
    return render_template("results.html", profile=session.get("profileData"), recentlyPlayedGames=session.get("recentlyPlayedGames"))
 
if __name__ == "__main__":
    app.run(debug=True)