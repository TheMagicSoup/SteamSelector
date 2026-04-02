import os
import pandas as pd
import pickle
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import linear_kernel

# Minimum number of owners for a game to be included in the dataset
MIN_OWNERS = 30000
# Weights for the categories involved in each game's document representation
TAGS_WEIGHT=3
GENRES_WEIGHT=2
CATEGORIES_WEIGHT=1
ABOUT_THE_GAME_WEIGHT=1

df=pd.read_csv("data/games.xls")
def get_min_owners(c):
    return int(c.split("-")[0])

# Cleaning and preparing dataset
df["min_owners"] = df["Estimated owners"].apply(get_min_owners)
df=df[df["min_owners"]>=MIN_OWNERS]
df=df[~((df["Price"] == 0) & (df["Peak CCU"] == 0))]
df=df.dropna(subset=["Name"])
df=df.reset_index(drop=True)
df=df[[
    "AppID","Name","Price","Categories",
    "Genres","Tags","About the game"
    ]]

# 4 most important categories - Categories, Genres, Tags, About the Game

df["doc"]=(
    (df["Tags"].fillna("")+" ") * TAGS_WEIGHT +
    (df["Genres"].fillna("")+" ") * GENRES_WEIGHT +
    (df["Categories"].fillna("")+" ") * CATEGORIES_WEIGHT +
    (df["About the game"].fillna("")) * ABOUT_THE_GAME_WEIGHT
)

df["doc"] = df["doc"].str.replace(";", " ", regex=False)
# Constructing TF-IDF matrix
vectorizer=TfidfVectorizer(
    stop_words="english", # Removing common English words irrelevant to similarity
    max_features=20000, # Limiting the number of features to the top 20,000 most relevant
    min_df=2 # Only including terms that appear in >= 2 games
)

# Fitting vectorizer to the "doc" column and transforming it to a TF-IDF matrix
tfidf_matrix=vectorizer.fit_transform(df["doc"])

# Computing cosine similarity between all pairs of games based on TF-IDF vectors
cosine_sim=linear_kernel(tfidf_matrix,tfidf_matrix)

with open("model.pkl","wb") as f:
    pickle.dump({
        "df":df,
        "tfidf_matrix":tfidf_matrix,
        "cosine_sim":cosine_sim,
        "vectorizer":vectorizer
    },f)

print("Model saved!")