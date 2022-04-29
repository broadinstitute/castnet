# CastNet
Turn your URL requests into Cypher! Did you ever want to use a REST web interface to update Graph database records (and retrieve via GraphQL), but didn't want to handle each individual endpoint on a server? Then this might be for you!

`pip install castnet`

CastNet is a REST-CRUD middleware package designed for interacting with a Neo4j Graph Database through a web server, automatically routing and transforming requests from the front end into CYPHER queries. Castnet automatically handles
* Create: POST
* Update: PATCH
* Delete: DELETE

...and

* Retrieve: GraphQL (Through POST)

Incoming URL requests are transformed to their labels by a route-label table and types/relationships are automatically cast from the incoming JSON based on a schema.

Each node by default has an automatically generated ID, a user-specified name which should be unique to that label, and a description.

CastNet supports:
* Attributes
* Relationships (and preserves order of same-label nodes!)
* Hierarchies
* Simple GraphQL
* Per-label basis `name` uniqueness
* Logging function to record changes.

## How to Use
1. Define a schema
2. Define a URL/Label table
3. Plug in to your REST backend (Tested with Flask)

## Minimal Example
`{'id': str, 'name': str, and 'description': str}` are automatically included in the schema.
```Python
import json
from flask import Flask, request
from castnet import CastNetConn
def make_response(response, status=200):
    return (json.dumps(response), status, {"Access-Control-Allow-Origin": "*"})
SCHEMA = {"Person" :{}}
URL_KEY = {"people": "person"}
CONN = CastNetConn("database_uri", "username", "password", SCHEMA, URL_KEY)
app = Flask(__name__)
@app.route("/<path:path>", methods=["POST", "PATCH", "OPTIONS", "DELETE"])
def main(**_):
    path_params = CONN.get_path(request.path)
    if path_params[0] == "graphql":
        return make_response(*CONN.generic_graphql(request))
    if request.method == "POST":
        return make_response(*CONN.generic_post(request))
    if request.method == "PATCH":
        return make_response(*CONN.generic_patch(request))
    if request.method == "DELETE":
        return make_response(*CONN.generic_delete(request))
app.run(debug=True)
```
Create a Person:
```
curl -X POST localhost:5000/people -H 'Content-Type: application/json' 
  -d '{"name":"Alice", "description":"Pretty nice."}'
```
Retrieve People (Post to the GraphQL endpoint)
```
curl -X POST localhost:5000/graphql -H 'Content-Type: application/json' 
  -d '{"qeury":"Person{id name description}"}'
```
Update a Person (IDs and Names are immutable):
```
curl -X POST localhost:5000/people/<Alice's ID> -H 'Content-Type: application/json' 
  -d '{"description":"Actually really nice."}'
```
Delete a Person:
```
curl -X DELETE localhost:5000/people/<Alice's ID>
```


## More Complicated Example
Let's say we want to create a database to handle easy updates to a Bird tracker at various birdfeeders, at multiple houses, each with multiple feeders. One possible way to have a database is by making a hierarcheical database, starting with Houses. And, we may want a running list of birds and know when/where they were seen. Most importantly, we want to build a snazzy web based front end, and don't want to make a dedicated endpoint for each update.

The database entries, with their hierarchies might look something like this:

* My House (House)
  * GardenFeeder (Feeder)
    * Day1 (FeederScan)
    * Day2 (FeederScan)
  * SideYardFeeder (Feeder)
    * Day1 (FeederScan)
    * Day2 (FeederScan)
* Bob's House (House)
  * BackyardFeeder (Feeder)
    * Day1 (FeederScan)
    * Day2 (FeederScan)
* BlueJay (Bird)
* Eastern BlueBird (Bird)
* Ruby-Throated Hummingbird (Bird)
* Ivory-Billed Woodpecker (Bird)

We have two Houses, 3 Feeders, and 6 observations (FeederScan) and 2 birds in the database. In this design, we could build a schema like so:

```python
from datetime import datetime
from castnet import CastNetConn

# NOTE: {'id': str, 'name': str, and 'description': str} is automatically added to attributes
# If there is the "IS_IN" rel, then an automatic "isIn" GraphQL endpoint is created.
SCHEMA = {
  
  "House": {},
  "Feeder": {
    "attributes": {"feederType": str, "feederHeight": float, "seedType": str, "dateInstalled": datetime},
    "IS_IN": "House"
  },
  "Scan": {
    "attributes": {"scanTime": datetime, "feederHeight": float, "seedType": str, "dateInstalled": datetime},
    "relationships": {"BIRDS_OBSERVED": ["Bird"]},
    "IS_IN": "Feeder",
    "graphql": {"rel": "BIRDS_OBSERVED", "dir": "OUT", "lab": "Bird"}
  },
  "Bird": {
    "attributes": {"favoriteFood": str},
    "graphql":{
      "seenAt": {"rel": "BIRDS_OBSERVED", "dir": "IN", "lab": "Scan"}
    }
  },
}
```
and tie it in to our url scheme
```python
URL_KEY = {
    "birds": "Bird",
    "houses": "House",
    "birdfeeders": "Feeder",
    "birdscan": "Scan",
}
```

And now we can begin making requests!

### Create a House:
```
POST: /birdserver/houses
JSON: "{'name': 'My House', 'description': 'This is my house.'}"
``` 
which automatically generates an id (e.g. `House_20220429_myhouse_abcd`), parses and casts the name and submits the following Cypher:
```
CREATE
(source:House {id: $source_id, name:$name, description:$description})
RETURN
source
```
### Now add a feeder, which is that the house
```
Method: POST
URL: /birdserver/birdfeeders
JSON: "{'name': 'GardenFeeder', 'dateInstalled': "2022-04-22': 'IS_IN': 'House_20220429_myhouse_abcd'}"
```
which becomes:
```Cypher
MATCH
(target_0:House {id: $target_0_id})
CREATE
(source:Feeder {id: $source_id, dateInstalled:$dateInstalled})
CREATE
(source)-[:IS_IN {order_num: 0}]->(target_0)
RETURN
source
```
And assuming the birds are added, add a scan
```
Method: POST
URL: /birdserver/feederscans
JSON: "{'name': 'Day1', 'timeStamp': "2022-04-22': 'IS_IN': 'Feeder_20220429_gardenfeeder_abcd',
        'BIRDS_OBSERVED': ['Feeder_20220429_ivorybilledwoodpecker_abcd', Feeder_20220429_bluejay_abcd]}"
```
```Cypher
MATCH
(target_0:Feeder {id: $target_0_id})
(target_0:Bird {id: $target_1_id})
(target_0:Bird {id: $target_2_id})
CREATE
(source:Scan {id: $source_id, timeStamp:timeStamp})
CREATE
(source)-[:IS_IN {order_num: 0}]->(target_0),
(source)-[:BIRDS_OBSERVED {order_num: 1}]->(target_1),
(source)-[:BIRDS_OBSERVED {order_num: 2}]->(target_2)
RETURN
source
```
Or remove the Ivory-Billed Woodpecker by updating with just a bluejay...
```
Method: PATCH
URL: /birdserver/scans/Scan_20220429_day1_abcd
JSON: "{'BIRDS_OBSERVED': ['Feeder_20220429_bluejay_abcd']}"
```
 


## Schema
