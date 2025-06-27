import sqlite3
import os
import pickle
from api import update_recent_problems
import time

def load_pickle(filepath, object_default):
    if not os.path.exists(filepath):
        #with open(filepath, 'wb') as f:
        #    pickle.dump(object_default, f)
        return object_default
    with open(filepath, 'rb') as f:
        obj = pickle.load(f)
    return obj
handle_to_user = load_pickle('handle_to_user.pkl', { })

con = sqlite3.connect("data.sqlite3", autocommit=True)
cur = con.cursor()

cur.execute("""CREATE TABLE IF NOT EXISTS users(
               user_id INTEGER PRIMARY KEY AUTOINCREMENT,
               handle TEXT NOT NULL, 
               grader TEXT NOT NULL, 
               discord_id INTEGER NOT NULL)""")

cur.execute("""CREATE TABLE IF NOT EXISTS problems(
               user_id INTEGER NOT NULL,
               name TEXT NOT NULL, 
               url TEXT,
               timestamp INTEGER NOT NULL,
               rating_grader TEXT,
               rating_clist INTEGER,
               FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE) """)

for grader in handle_to_user:
    for handle in handle_to_user[grader]:
        cur.execute(f"INSERT INTO users (handle, grader, discord_id) VALUES ('{handle}', '{grader}', {handle_to_user[grader][handle]})")

for handle, grader in cur.execute('SELECT handle, grader FROM users').fetchall():
    if grader=='codeforces':
        time.sleep(2) # rate limits
    update_recent_problems(handle, grader, 20, cur)
