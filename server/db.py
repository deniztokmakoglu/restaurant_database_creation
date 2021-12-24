from os import path
import json
import jellyfish as td
import string #we're using it to get letters of the alphabet
import math

# Error class for when request data is bad
class InspError(Exception):
    def __init__(self, message=None, error_code=400):
        Exception.__init__(self)
        if message:
            self.message = message
        else:
            self.message = "Bad Request"
        self.error_code = error_code
    def to_dict(self):
        rv = dict()
        rv['message'] = self.message
        return rv

# Utility factor to allow results to be used like a dictionary
def dict_factory(cursor, row):
    d = {}
    for idx, col in enumerate(cursor.description):
        d[col[0]] = row[idx]
    return d

"""
Wraps a single connection to the database with higher-level functionality.
"""
class DB:
    def __init__(self, connection):
        self.conn = connection

    def execute_script(self, script_file):
        with open(script_file, "r") as script:
            c = self.conn.cursor()
            # Only using executescript for running a series of SQL commands.
            c.executescript(script.read())
            self.conn.commit()

    def create_script(self):
        """
        Calls the schema/create.sql file
        """
        script_file = path.join("schema", "create.sql")
        if not path.exists(script_file):
            raise InspError("Create Script not found")
        self.execute_script(script_file)

    def seed_data(self):
        """
        Calls the schema/seed.sql file
        """
        script_file = path.join("schema", "seed.sql")
        if not path.exists(script_file):
            raise InspError("Seed Script not found")
        self.execute_script(script_file)

    def find_restaurant(self, restaurant_id):
        """
        Searches for the restaurant with the given ID. Returns None if the
        restaurant cannot be found in the database.

        Inputs: restaurant_id - (integer) id for a restaurant.
        Returns: restaurant object if it exists, None if it does not.
        """
        c = self.conn.cursor()
        table = c.execute(""" SELECT * FROM ri_restaurants WHERE id == (?)""",
                            [str(restaurant_id)])
        results = table.fetchall()
        c.close()
        if results == []:
             return None
        else:
            return results

    def find_inspection(self, inspection_id):
        """
        Searches for the inspection with the given ID. Returns None if the
        inspection cannot be found in the database.

        Inputs: inspection_id - (string) id for an individual inspection.
        Returns: inspection object if it exists, None if it does not.
        """
        c = self.conn.cursor()
        table = c.execute(""" SELECT * FROM ri_inspections WHERE id == (?)""",
                            [str(inspection_id)])
        results = table.fetchall()
        c.close()
        if results == []:
            return None
        else:
            return results

    def find_inspections(self, restaurant_id):
        """
        Searches for all the inspection associated with a restaurant.

        Inputs: restaurant_id - (integer) id for an restaurant.
        Returns: all inspections associated with the corresponding restaurant.
        """
        c = self.conn.cursor()
        table = c.execute("""SELECT i.id, risk,
                            inspection_date, inspection_type, results,
                            violations
                            FROM ri_inspections as i JOIN ri_restaurants AS r 
                            ON i.restaurant_id == r.id 
                            WHERE restaurant_id == (?)""", [str(restaurant_id)])
        results = table.fetchall()
        c.close()
        return results

    def add_inspection_for_restaurant(self, inspection, restaurant):
        """
        Finds or creates the restaurant then inserts the inspection and
        associates it with the restaurant.

        Inputs: inspection - (object): inspection data
                restaurant - (object): restaurant data
        Returns: None
        """
        restaurant_id = restaurant["id"]
        inspection_id = inspection["id"]
        c = self.conn.cursor()
        if self.find_restaurant(restaurant_id) is None:
            c.execute(""" INSERT INTO ri_restaurants 
                    (restaurant_id, name, facility_type, address, city,
                    state, zip, latitude, longitude, clean) 
                    VALUES (?,?,?,?,?,?,?)""",
                    (restaurant_id, restaurant["name"], 
                    restaurant.get("facility_type", None),
                    restaurant.get("address", None), 
                    restaurant.get("city", None),
                    restaurant.get("state", None), 
                    restaurant.get("zip", None),
                    restaurant.get("latitude", None), 
                    restaurant.get("longitude", None),
                    False))
            c.close()
        else:
            return None
    
    def add_inspection(self, inspection, restaurant_id):
        """
        Adds an inspection into the database. If the corresponding restaurant 
        does not already exist, it is created.

        Inputs: inspection - (object) data structure containing inspection.
                restuarant_id - (integer) id for an restaurant.
        """
        inspection_id = inspection["inspection_id"]
        c = self.conn.cursor()
        c.execute("""INSERT INTO ri_inspections 
                    (id,risk,inspection_date,inspection_type,
                    results,violations,restaurant_id)
                    VALUES (?,?,?,?,?,?,?)""", 
                    (inspection_id, inspection.get("risk", None),
                    inspection.get("date", None),
                    inspection.get("inspection_type", None),
                    inspection.get("results", None),
                    inspection.get("violations", None), restaurant_id))
        c.close()
    
    def add_restaurant(self, data, clean = False):
        """
        Reads in data and adds a restaurant to the database.

        Inputs: data (JSON) - information about restaurant
        """
        c = self.conn.cursor()
        c.execute(""" INSERT INTO ri_restaurants 
                    (name, facility_type, address, city, state, zip,
                    latitude, longitude, clean) VALUES (?,?,?,?,?,?,?,?,?)""",
                    (data["name"], data.get("facility_type", None),
                    data.get("address", None), data.get("city", None),
                    data.get("state", None), data.get("zip", None),
                    data.get("latitude", None), data.get("longitude", None),
                    clean))
        c.close()

    def find_restaurant_by_name_adress(self, restaurant_name,
                                             restaurant_address,
                                             return_all_attr = True,
                                             return_all_dcts = False):
        """
        Uses the restaurant name and address (the unique identifiers)
        to locate and return a restaurant object, or None if it does not exist.

        Inputs: restuarant_name - (string) name of a restaurant object
                restaurant_address - (string) address of a restaurant object
        Returns: Restaurant (object) if it exists, None if it does not.
        """
        c = self.conn.cursor()
        if return_all_attr:
            table = c.execute("""SELECT id, 
                                        name, 
                                        facility_type, 
                                        address, 
                                        city, 
                                        state, 
                                        zip, 
                                        latitude, 
                                        longitude, 
                                        clean 
                                FROM ri_restaurants 
                                WHERE name == (?) AND address == (?)""",
                            (restaurant_name, restaurant_address))
        else:
            table = c.execute("""SELECT id FROM ri_restaurants 
                                WHERE name == (?) AND address == (?)""",
                                (restaurant_name, restaurant_address))
        results = table.fetchall()
        c.close()
        if results == []:
            return None
        else:
            if return_all_dcts:
                return results
            else:
                return results[0]

    def find_restaurant_by_inspection_id(self, inspection_id, raw = False):
        """
        Uses an inspection_id to locate and return a restaurant object,
        or None if it does not exist.

        Inputs: inspection_id - (string) id for an individual inspection.
        Returns: Restaurant (object) if it exists.
        """
        try:
            c = self.conn.cursor()
            table = c.execute("""SELECT * FROM ri_inspections as i
                                JOIN ri_restaurants as r ON
                                r.id = i.restaurant_id
                                WHERE i.id == (?)""", [str(inspection_id)])
            results = table.fetchall()
            if raw:
                return results[0]
            name = results[0]["name"]
            address = results[0]["address"]
            c.close()
            return self.find_restaurant_by_name_adress(name, address)
        except Exception as e:
            print(e, "find_restaurant_by_inspection_id")

    def commit(self):
        """
        Commits 
        """
        self.conn.commit()

    def abort(self):
        """
        Aborts
        """
        self.conn.rollback()

    def set_transaction_size(self, transaction_size):
        """
        Sets transaction size
        """
        self.transaction_size = transaction_size

    def find_tweets_by_restaurant(self, restaurant_id):
        """
        Finds all tweets associated with a restaurant.

        Inputs: restaurant_id - (integer) restaurant id
        Returns: a list of tweets
        """
        try:
            c = self.conn.cursor()
            sql = """select tkey, match from ri_tweetmatch 
                     where restaurant_id == (?)"""
            table = c.execute(sql, [str(restaurant_id)]).fetchall()
            return table
        except:
            return []
        
    def match_tweet_restaurant(self, tweet, tweet_ngrams, lat, lon):
        """
        Find a restaurant match of a tweet

        Inputs: tweet - (object) contains information for tweet
                tweet_ngrams - (list) n grams of words in tweet
                lat - (string) latitude
                lon - (string) longitude
        Returns: a dictionary of matches
        """
        match_by_name = self.match_by_name(tweet_ngrams)
        matches = {rest_id: "name" for rest_id in match_by_name}
        if lat and lon:
            match_by_geo = self.match_by_geo(float(lat), float(lon))
            for rest_id in match_by_geo:
                if matches.get(rest_id, None) is not None:
                    matches[rest_id] = "both"
                else:
                    matches[rest_id] = "geo"
        if matches:
            self.add_tweet(tweet["key"], matches) 
        return {"matches": sorted(matches)}

    def match_by_name(self, tweet_ngrams):
        """
        Find a restaurant match by comparing searching
        for name in tweet_ngrams

        Inputs: tweet_ngrams - (list) n grams of words in tweet
        Returns: rv - (list) a list of matches
        """
        try:
            c = self.conn.cursor()
            questionmarks = '?' * len(tweet_ngrams)
            sql = """select id from ri_restaurants 
                    where lower(name) in (%s)""" % (",").join(questionmarks)
            table = c.execute(sql, tweet_ngrams).fetchall()
            rv = [dct["id"] for dct in table]
            c.close()
            return rv
        except:
            return []

    def match_by_geo(self, lat, lon):
        """
        Find a restaurant match by comparing latitiude
        and longitude of tweet and restaurant

        Inputs: lat - (string) latitiude
                lon - (string) longitude
        Returns: rv - (list) a list of matches
        """
        try:
            c = self.conn.cursor()
            range_loc = [lat - 0.00225001,
                         lat + 0.00225001,
                         lon - 0.00302190,
                         lon + 0.00302190]
            sql = """SELECT id FROM ri_restaurants WHERE latitude 
                    BETWEEN ? AND ? AND longitude BETWEEN ? AND ?"""
            table = c.execute(sql, range_loc).fetchall()
            rv = [dct["id"] for dct in table]
            c.close()
            return rv
        except Exception as e:
            return []

    def insert_tweet_rest_match(self, tweet_key, rest_id, match):
        """
        Adds a tweet and it restaurant match.

        Inputs: tweet_key - (string) tweet key
                rest_id - (integer) restaurant id
                match - (string) how the tweet was matched.
        """
        c = self.conn.cursor()
        c.execute(""" INSERT INTO ri_tweetmatch 
                    (tkey, restaurant_id, match) VALUES (?,?,?)""",
                    (tweet_key, rest_id, match))
        c.close()
        
    def add_tweet(self, tweet_key, matches):
        """
        Adds a tweet.

        Inputs: tweet_key - (string) key
                matches (dictionary) if it exists.
        """
        for rest, match in matches.items():
            self.insert_tweet_rest_match(tweet_key, rest, match)
    
    def not_clean(self):
        '''
        Identifies all of the restaurants where the tag 'clean'
        is False.

        Returns: All not cleaned restaurants.
        '''
        try:
            c = self.conn.cursor()
            sql = """SELECT *
            FROM ri_restaurants WHERE clean == 0"""
            table = c.execute(sql).fetchall()
            return table
        except Exception as e:
            return []
    
    def find_linked(self, restaurant_main, restaurants, parameter):
        '''
        Takes the restaurant identified as the main and gets all
        restaurants within a similaritty score of it.

        Inputs: restaurant_main (object) - the chosen main restaurant
                restaurants (list) - list of restaurants that will
                                     be checked for similarity
                parameter (float) - threshold determined for similarity
        
        Returns: list of all restuarants linked to main
        '''
        try:  
            ids = []
            linked_rests = {restaurant_main["id"]:[]}
            for restaurant in restaurants:
                jw_state = td.jaro_winkler(restaurant_main["state"].lower(),
                                        restaurant["state"].lower())
                jw_city = td.jaro_winkler(restaurant_main["city"].lower(),
                                        restaurant["city"].lower())
                if jw_state >= parameter and jw_city >= parameter:
                    jw_name  = td.jaro_winkler(restaurant_main["name"].lower(),
                                        restaurant["name"].lower())
                    if jw_name >= parameter:
                        linked_rests[restaurant_main["id"]].append(restaurant)
                        ids.append(restaurant["id"])
            return (linked_rests, ids)
        except Exception as e:
            print(e)

    def find_all_linked(self, parameter, block = False):
        '''
        Finds all linked restaurants for every restauarant in the DB.

        Inputs: parameter (float) - threshold determined for similarity

        Retuens: list of linked restaurants
        '''
        try:
            all_ids = []
            not_clean = list(self.not_clean())
            all_restaurants = list(self.find_all_restaurants())
            linked_rests = []
            for restaurant_main in not_clean:
                if restaurant_main["id"] not in all_ids:
                    dct_linked, ids_temp = self.find_linked(restaurant_main,
                                                all_restaurants, parameter)
                    linked_rests.append(dct_linked)
                    all_ids += ids_temp
            return linked_rests
        except Exception as e:
            return None

    def find_all_restaurants(self, table_name = None):
        '''
        Returns all resturants
        '''
        c = self.conn.cursor()
        if table_name:
            list_index_matched = self.get_candidates_within_block(table_name)
        else:
            sql = """SELECT *
            FROM ri_restaurants"""
            table = c.execute(sql).fetchall()
            return table

    def gen_aut_restaurant(self, matched_restaurants):
        '''
        Generates the primary restaurants for the matched restaurants 
        and adds it to the database. In the mean time, updates 
        other restaurants that were matched, changes their status 
        to clean and adds each match pair to the database.

        Inputs: matched_restaurants (list) -  a list of restaurants determined
                                              to be matches.
        '''
        try:
            restaurant_id = list(matched_restaurants.keys())[0]
            composite_restaurant = {}
            attribues = ['name', "facility_type", 'address',
                         'city', 'state', 'zip', 'latitude', 'longitude']
            for attribute in attribues:
                composite_restaurant[attribute] = \
                     self.compare_strings(matched_restaurants, attribute)
            self.add_restaurant(composite_restaurant, clean = True)
            restaurant_ids = \
                [rest["id"] for rest in matched_restaurants[restaurant_id]]
            if len(restaurant_ids) == 1:   
                self.update_cleaned_restaurant(restaurant_ids)
            else:    
                all_ids = \
                    self.find_restaurant_by_name_adress(\
                        composite_restaurant["name"],
                        composite_restaurant["address"], True, True)
                for dct in all_ids:
                    if dct["id"] not in restaurant_ids:
                        composite_id = dct["id"]
                        break
                self.add_linked_restaurants(composite_id, restaurant_ids)
                self.update_cleaned_restaurant(restaurant_ids)
                self.update_inspection_restaurant_id(composite_id,
                                                    restaurant_ids)
        except Exception as e:
            return None

        
    def compare_strings(self, matched_restaurants, attribute):
        '''
        Takes matched restaurants and attribute to compare on and
        determined the string to use in the primary.

        Inputs: matched_restaurants (list) -  a list of all matched restaurants
                attribute (key) - name, address, facility type, etc. 

        Returns: the value associated with the attribute to be used in the
                 primary
        '''
        key = list(matched_restaurants.keys())[0]
        rests = [rest for rest in matched_restaurants[key]]
        values = [rest[attribute] for rest in rests]
        if type(values[0]) == str:
            max_len = 0
            index = 0
            for i, j in enumerate(values): 
                if len(j) >= max_len:
                    max_len = len(j)
                    index = i
            return values[index]
        else:
            for value in values:
                if value is not None:
                    return value

    def add_linked_restaurants(self, composite_id, restaurant_ids):
        '''
        Takes a composite_id and a list of restaurant ids and adds
        linked restaurants.

        Inputs: composite_id (int) - composite restaurant id
                restaurant_ids (list) - list of restaurant ids
        '''
        try:
            c = self.conn.cursor()
            for restaurant_id in restaurant_ids:   
                c.execute(""" INSERT INTO ri_linked 
                            (primary_rest_id, original_rest_id) 
                            VALUES (?, ?)""",
                            (str(composite_id), str(restaurant_id)))
            self.conn.commit()
            c.close()
        except Exception as e:
            return []
        
    def update_cleaned_restaurant(self, restaurant_ids):
        '''
        Updates restuarants clean tag from 0 to 1 (cleaned).

        Inputs: restaurant_ids (list) - a list of restaurant ids to
                                        be updated.
        '''
        try:
            c = self.conn.cursor()
            for rest_id in restaurant_ids:  
                sql = """UPDATE ri_restaurants 
                        SET clean = 1 
                        WHERE id == (?)"""
                c.execute(sql, [str(rest_id)])
            self.conn.commit()
            c.close()
        except Exception as e:
            return []

    def update_inspection_restaurant_id(self, clean_id, link_ids):
        '''
        Updates the inspection 
        '''
        try:
            c = self.conn.cursor()
            questionmarks = '?' * len(link_ids)
            sql = """UPDATE ri_inspections 
                    SET restaurant_id = (?) 
                    WHERE restaurant_id IN (%s)""" % (",").join(questionmarks)
            c.execute(sql, [str(clean_id)] + link_ids)
            self.conn.commit()
            c.close()
        except Exception as e:
            print(e, "error")
    
    def find_all_restaurants_by_inspection_id(self, inspection_id):
        '''
        Finds all restaurants associated with an inspection_id

        Inputs: inspection_id - (string) id for an individual inspection.

        Returns: a tuple of all the linked restaurants and the primary
                 restaurant associated with the inspection.
        '''
        try:  
            p_restaurant = self.find_restaurant_by_inspection_id(inspection_id,
                                                                True)
            attributes = ["id", "name", "facility_type", "address",
                          "city", "state", "zip", "latitude",
                          "longitude", "clean"]
            p_restaurant = {attribute:p_restaurant[attribute] 
                            for attribute in attributes}
            p_restaurant_id = p_restaurant["id"]
            linked_restaurants = self.find_linked_restaurants(p_restaurant_id)
            return (linked_restaurants, p_restaurant)
        except Exception as e:
            print(e, "error_find_all_by_insp")


    def find_primary_restaurant(self, restaurant_id):
        '''
        Selects the primiary restaurant from the list of
        linked restaurants.

        Inputs: restuarant_id - (integer) id for an restaurant.

        Returns: primary restaurant if it exists
        '''
        try:
            c = self.conn.cursor()
            sql = """ SELECT primary_rest_id FROM ri_linked
                    WHERE original_rest_id == (?)"""
            table = c.execute(sql, [restaurant_id]).fetchall()
            print(table, "table find p rest")
            if table == []:
                return []
            primary_rest_id = table[0]["primary_rest_id"]
            primary_restaurant = self.find_restaurant(primary_rest_id)
            return primary_restaurant[0]
        except Exception as e:
            return []
    
    def find_linked_restaurants(self, primary_rest_id):
        '''
        Gets all linked restaurants associated with the primary
        restaurant. 

        Inputs: primary_rest_id - (integer) id for primary restaurant.

        Returns: information from linked restaurants associated with
                 the primary restaurant id.
        '''
        try:
            c = self.conn.cursor()
            sql = """ SELECT rir.id, rir.name, rir.facility_type,
                       rir.address, rir.city, rir.state, rir.zip,
                       rir.latitude, rir.longitude, rir.clean
                       FROM ri_linked as ril 
                       INNER JOIN ri_restaurants as rir
                       ON ril.original_rest_id == rir.id
                       WHERE primary_rest_id == (?)"""
            table = c.execute(sql, [primary_rest_id]).fetchall()
            return table
        except Exception as e:
            print(e, "find_linked_restaurants")
            return []

    def create_blocks(self, num_blocks):
        """
        Creates #n blocks within the database based on the 
        first letter of restaurant names. Creates chunks 
        of letters and adds the restaurant to the chunk if the 
        first letter of the restaurant is in that chunk.
        Inputs:
            - num_blocks: Number of blocks to be created.
        Returns:
            - nothing. Updates the dataset.
        """
        try:    
            c = self.conn.cursor()
            alphabet_string = list(string.ascii_lowercase)
            for i in range(0, 10):
                alphabet_string.append(str(i))
            n = math.ceil(len(alphabet_string)/num_blocks)
            chunks = [alphabet_string[x:x+n] for x in range(0, len(alphabet_string), n)]
            for index, chunk in enumerate(chunks):
                questionmarks = '?' * len(chunk)
                temp_table_name = f"ri_rest_b_{index + 1}"
                temp_table_query = """CREATE TEMPORARY TABLE \"{}\" 
                                    AS SELECT id, name, facility_type,
                                    address, city, state, zip,
                                    latitude, longitude, clean  
                                    FROM ri_restaurants WHERE SUBSTR(LOWER(name), 1, 1) IN ({})""".format(temp_table_name, (",").join(questionmarks))
                c.execute(temp_table_query, chunk)
                self.conn.commit()
        except Exception as e:
            print(e, "error from create_blocks")
    
    def create_index(self, table_name, index_num):
        """
        Creates an index in the block based on the 
        first 4 digits of the restaurants zip code. 
        Inputs:
            - table_name(str): name of the block table
            - index_num(int): unique number for the index name
        Returns:
            - nothing. Updates the database.
        """
        try:
            c = self.conn.cursor()
            index_query = """CREATE INDEX zip_index_{}
                            ON {} (SUBSTR(zip, 0, 5))""".format(index_num, table_name)
            c.execute(index_query)
            self.conn.commit()
        except Exception as e:
            print(e, "error from create_index")
    
    def get_block_names(self):
        """
        Gets the temporary table names in the database.
            - Returns:
                table (list): list of temporary table names.
        """
        try:
            c = self.conn.cursor()
            table = c.execute("""SELECT tbl_name FROM sqlite_temp_master where 
                         type='table' and tbl_name like 'ri_rest_b_%'""").fetchall()
            table = [dct["tbl_name"] for dct in table]
            return table
        except Exception as e:
            print(e, "error in get block names")
    
    def get_candidates_within_block(self, table_name):
        """
        Gets the candidates for matching algorithm within the block
        based on the first 4 digits of the zip code.
        Inputs: 
            - table_name: name of the block
        Returns:
            - candidate_blocks (list of tuples): candidates for matching
            (row, list of candidates)
        """
        try:
            candidate_blocks = []
            c = self.conn.cursor()
            rows = c.execute(f"SELECT * FROM {table_name} WHERE clean == 0")
            for row in rows.fetchall():
                _zip_subcode = row["zip"][:4]
                query = f"SELECT * FROM {table_name} WHERE SUBSTR(zip, 0, 5) == (?)"""
                cantidate_temp = c.execute(query, [_zip_subcode]).fetchall()
                candidate_blocks.append((row, cantidate_temp))
            return candidate_blocks
        except Exception as e:
            print(e, "error in get candidates_within_block")

    def match_with_blocking(self, block_name, parameter):
        """
        Matches the candidate restaurants comes within a block and with
        similar zip codes.

        Inputs:
            - Parameter(float): JW similarity score paramter
            - block_name(str): name of the block
        Returns:
            - matched restaurants(list): list of matched restaurants based 
            on the algorithm
        """
        try:
            candidate_pairs = self.get_candidates_within_block(block_name)
            all_ids = []
            linked_rests = []
            for pair in candidate_pairs:
                restaurant_main = pair[0]
                list_candidates = pair[1]
                
                if restaurant_main["id"] not in all_ids:
                    dct_linked, ids_temp = self.find_linked(restaurant_main,
                                                list_candidates, parameter)
                    linked_rests.append(dct_linked)
                    all_ids += ids_temp
            return linked_rests
        except Exception as e:
            print(e, "error within clean_with_blocking")
        

        

        
        




