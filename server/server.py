from bottle import Bottle, post, get, HTTPResponse, request, response
import argparse
import os
import sys
import sqlite3
import logging
from db import DB
from db import dict_factory
from db import InspError
import string
import json
import time



DB_NAME = "insp.db"
logging.basicConfig(level=logging.INFO)

app = Bottle()
app.counter = 0
app.transaction_size = 1
app.num_blocks = 4

@app.get("/hello")
def hello():
    return "Hello, World!"

@app.get("/reset")
@app.get("/create")
def create():
    db = DB(app.db_connection)
    db.create_script()
    return "Created"


@app.get("/seed")
def seed():
    db = DB(app.db_connection)
    db.seed_data()
    return "Seeded"

@app.get("/restaurants/<restaurant_id:int>")
def find_restaurant(restaurant_id):
    """
    Returns a restaurant and all of its associated inspections.
    """
    db = DB(app.db_connection)
    try:
        rv = {}
        table = db.find_restaurant(restaurant_id)
        inspections = db.find_inspections(restaurant_id)
        rv["restaurant"] = table[0]
        rv["inspections"] = inspections
        return rv
    except:
        raise HTTPResponse(status=404)
    


@app.get("/restaurants/by-inspection/<inspection_id>")
def find_restaurant_by_inspection_id(inspection_id):
    """
    Returns a restaurant associated with a given inspection.
    """
    try:
        db = DB(app.db_connection)
        return db.find_restaurant_by_inspection_id(inspection_id)
    except:
        raise HTTPResponse(status=404)


@app.post("/inspections")
def load_inspection():
    """
    Loads a new inspection (and possibly a new restaurant) into the database.
    """
    db = DB(app.db_connection)
    try:
        data = request.json
        inspection_id = data.get("inspection_id", None)
        rest_name = data.get("name", None)
        if inspection_id is None or rest_name is None:
            raise HTTPResponse(status=400)
        rest_address = data["address"]
        inspection = db.find_inspection(inspection_id)
        restaurant = db.find_restaurant_by_name_adress(rest_name, data["address"], False)
        if inspection is not None:
            request.status = 200
            return restaurant
        elif inspection is None and restaurant is not None:
            restaurant_id = restaurant["id"]
            db.add_inspection(data, restaurant_id)
            commit_check(db)
            response.status = 200
            return restaurant
        else:
            db.add_restaurant(data)
            restaurant = db.find_restaurant_by_name_adress(rest_name, rest_address, False)
            restaurant_id = restaurant["id"]
            db.add_inspection(data, restaurant_id)
            commit_check(db)
            response.status = 201
            return restaurant
    except Exception as e:
        raise HTTPResponse(status=501)

@app.get("/txn/<txnsize:int>")
def set_transaction_size(txnsize):
    """
    Sets the transaction size for database commit.
    """
    try:
        db = DB(app.db_connection)
        if db.conn.in_transaction:
            db.commit()
            db.conn.start_transaction()
        app.counter = 0
        app.transaction_size = txnsize
        response.status = 200
    except:
        raise HTTPResponse(status=501)

@app.get("/commit")
def commit_txn():
    logging.info("Committing active transactions")
    db = DB(app.db_connection)
    try:
        db.commit()
        response.status = 200
    except:
        raise HTTPResponse(status=501)

@app.get("/abort")
def abort_txn():
    logging.info("Aborting/rolling back active transactions")
    db = DB(app.db_connection)
    try:
        db.abort()
        response.status = 200
    except:
        raise HTTPResponse(status=501)


@app.get("/count")
def count_insp():
    logging.info("Counting Inspections")
    db = DB(app.db_connection)
    try:
        c = db.conn.cursor()
        result = c.execute("""SELECT COUNT(id) as cnt FROM ri_inspections""")
        table = result.fetchall()
        c.close()
        response.status = 200
        count = table[0]["cnt"]
        return str(count)    
    except Exception as e:
        raise HTTPResponse(status=501)

# A helper function that will take text and split it into n-grams based on spaces.
def ngrams(tweet, n):
    single_word = tweet.translate(str.maketrans('', '', string.punctuation)).split()
    output = []
    for i in range(len(single_word) - n + 1):
        output.append(' '.join(single_word[i:i + n]))
    return output


@app.post("/tweet")
def tweet():
    logging.info("Checking Tweet")
    try:
        db = DB(app.db_connection)
        tweet_ngrams = []
        tweet = request.json
        text = tweet['text']
        lat = tweet['lat']
        lon = tweet['long']
        for n in range(1, 5):
            n_grams = ngrams(text, n)
            n_grams = [word.lower() for word in n_grams]
            tweet_ngrams = tweet_ngrams + n_grams
        result = db.match_tweet_restaurant(tweet, tweet_ngrams, lat, lon)
        response.status = 201
        return result
    except Exception as e:
        raise HTTPResponse(status=501)


@app.get("/tweets/<restaurant_id:int>")
def find_restaurant_tweets(restaurant_id):
    """
    Returns a restaurant's associated tweets (tkey and match).
    """
    try:
        db = DB(app.db_connection)
        results = db.find_tweets_by_restaurant(restaurant_id)
        response.status = 200
        return json.dumps(results)
    except Exception as e:
        raise HTTPResponse(status=501)

def commit_check(db):
    """
    Checks if the transaction size is reached 
    and if so, commits the changes.
    Inputs:
        db: Database object
    Returns:
        Nothing.
    """
    app.counter += 1
    if app.counter == app.transaction_size:
        db.commit()
        app.counter = 0


@app.get("/clean")
def clean():
    '''
    Cleans the restaurants and links the associated restaurants together.
    '''
    logging.info("Cleaning Restaurants")
    start = time.time()
    try:    
        db = DB(app.db_connection)
        if app.scaling:
            print("blocking")
            db.create_blocks(app.num_blocks)
            block_names = db.get_block_names()
            for index, block_name in enumerate(block_names):
                db.create_index(block_name, index)
                matched = db.match_with_blocking(block_name, 0.7)
                for restaurant in matched:
                    db.gen_aut_restaurant(restaurant)
        else:
            print("not blocking")
            linked_restaurants = db.find_all_linked(0.7)
            for restaurant in linked_restaurants:
                db.gen_aut_restaurant(restaurant)
        response.status = 200
        end = time.time()
        print("Time took to clean:", end - start)
    except Exception as e:
        print(e)
        raise HTTPResponse(status=501)

@app.get("/restaurants/all-by-inspection/<inspection_id>")
def find_all_restaurants_by_inspection_id(inspection_id):
    '''
    Finds and returns all restaurants assocuated with an inspection id.
    '''
    logging.info("Finding all restaurants by inspection id: %s" % inspection_id)
    try:
        db = DB(app.db_connection)
        linked_restaurants, primary_restaurant = db.find_all_restaurants_by_inspection_id(inspection_id)
        ids = [rest["id"] for rest in linked_restaurants]
        ids.append(primary_restaurant["id"])
        rv = {"primary": primary_restaurant,
                "linked":linked_restaurants,
                "ids": ids}
        response.status = 200
    except Exception as e:
        raise HTTPResponse(status=501)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--host",
        help="Server hostname (default localhost)",
        default="localhost"
    )
    parser.add_argument(
        "-p","--port",
        help="Server port (default 30235)",
        default=30235,
        type=int
    )
    parser.add_argument(
        "-s","--scaling",
        help="Enable large scale cleaning",
        default=False,
        action="store_true"
    )

    # Create the parser argument object
    args = parser.parse_args()
    # Create the database connection and store it in the app object
    app.db_connection = sqlite3.connect(DB_NAME)
    # See https://stackoverflow.com/questions/3300464/how-can-i-get-dict-from-sqlite-query
    app.db_connection.row_factory = dict_factory
    app.scaling = False
    if args.scaling:
        logging.info("Set to use large scale cleaning")
        app.scaling = True
    try:
        logging.info("Starting Inspection Service")
        app.run(host=args.host, port=args.port)
    finally:
        app.db_connection.close()