from datetime import datetime, date
from neo4j import GraphDatabase
import pytz
import shortuuid


__version__ = "0.0.1"


class CastNetConn:
    """
    CastNetConn is a class which handles a connection to a database.
    """

    def __init__(self, uri, user, password, schema, url_key):
        """
        Connects to a database
        """
        if uri and user and password:
            self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.schema = self._parse_schema(schema)
        self.url_key = url_key

    @staticmethod
    def _parse_schema(schema):
        new_schema = {}

        # first pass, build the schema
        for key in schema:
            new_schema[key] = {}
            # create id, name, description attributes
            temp_dict = {"name": str, "id": str, "description": str}
            if "attributes" in schema[key]:
                temp_dict.update(schema[key]["attributes"])
            new_schema[key]["attributes"] = temp_dict

            # build relationships
            temp_dict = {}
            if "relationships" in schema[key]:
                temp_dict.update(schema[key]["relationships"])
            new_schema[key]["relationships"] = temp_dict

            # build graphql
            temp_dict = {}
            if "graphql" in schema[key]:
                temp_dict.update(schema[key]["graphql"])
            new_schema[key]["graphql"] = temp_dict

            # creeate a IS_IN relationship
            if "IS_IN" in schema[key]:
                new_schema[key]["relationships"]["IS_IN"] = schema[key]["IS_IN"]
                new_schema[key]["graphql"]["isIn"] = {
                    "rel": "IS_IN",
                    "dir": "OUT",
                    "lab": schema[key]["IS_IN"],
                }

            new_schema[key]["graphql"] = temp_dict

        # do some checks
        for key, current in new_schema.items():
            # make sure all graphql things point to something
            for graphql_name in current["graphql"]:
                if not isinstance(current["graphql"][graphql_name], dict):
                    continue
                lab = current["graphql"][graphql_name]["lab"]
                rel = current["graphql"][graphql_name]["rel"]
                dir = current["graphql"][graphql_name]["dir"]
                check_label = key if dir.lower() == "out" else lab

                if rel not in new_schema[check_label]["relationships"].keys():
                    raise Exception(f"Relationship {rel} not found in {lab}")
        return new_schema

    @staticmethod
    def _submit_query(tx, query, **kwargs):
        """
        Performs a query to a database.
         Intended to be used by a driver.session()  in read/write methods.
        """
        result = tx.run(query, **kwargs)
        result = [r for r in result]  # pylint: disable=unnecessary-comprehension
        return result

    def request_to_cypher(
        self, label, source_id="", params=None, method="PATCH"
    ):
        """
        Converts a request for PUT/PATCH, based on path, to a valid cypher query and
        its vars.
        See the unittest for an example.
        """
        if not params:
            params = {}
        target_ids, clean_params = self.parse_params(label, params)

        # generate source identifying information
        source_matches = []
        create_source_block = ""
        cypher_vars = clean_params
        source_set_block = ""
        if method == "PATCH":
            source_set_block += ",\n".join(
                [f"source.{key}=${key}" for key in clean_params]
            )
            cypher_vars.update({"source_id": source_id})
            source_matches.append("(source:%s {id: $source_id})" % label)
        if method == "POST":
            create_source_block += (
                f"(source:{label} {{id: $source_id"
                f"{''.join([f', {p}:${p}' for p in clean_params])}}})"
            )
            cypher_vars["source_id"] = gen_id(label, clean_params["name"])

        # generate target identifying information
        target_matches = []
        d_t_matches = []
        d_t_deletes = []
        create_target = []
        rels_to_delete = set()
        for i, (conn_name, target_id) in enumerate(target_ids):
            n_target_var = f"target_{i}"
            tlabel = self.schema[label]["relationships"][conn_name]
            if isinstance(tlabel, list):
                tlabel = tlabel[0]

            # remove old relationships if we are overwriting relationships
            if method == "PATCH":
                if conn_name not in rels_to_delete:  # ensure one delete per rel
                    d_t_matches.append(
                        f"OPTIONAL MATCH (source)-[{n_target_var}_r:{conn_name}]-()"
                    )
                    d_t_deletes.append(f"{n_target_var}_r")
                    rels_to_delete.add(conn_name)

            # if target is empty, don't create a new relationship
            if target_id in ["", None, []]:
                continue
            cypher_vars[n_target_var + "_id"] = target_id
            target_matches.append(
                f"({n_target_var}:{tlabel} {{id: ${n_target_var}_id}})"
            )
            create_target.append(
                f"(source)-[:{conn_name} {{order_num: {i}}}]->({n_target_var})"
            )
        # Build the blocks
        source_match_block = ",\n".join(source_matches)
        target_match_block = ",\n".join(target_matches)
        d_t_match_block = "\n".join(d_t_matches)
        d_t_delete_block = ",\n".join(d_t_deletes)
        create_target_block = ",\n".join(create_target)

        # Create query
        query = (
            (("MATCH\n" + source_match_block + "\n") if source_match_block else "")
            + (("WITH source\n" + d_t_match_block + "\n") if d_t_match_block else "")
            + (
                ("DELETE\n" + d_t_delete_block + "\nWITH DISTINCT source\n")
                if d_t_delete_block
                else ""
            )
            + (("MATCH\n" + target_match_block + "\n") if target_match_block else "")
            + (("CREATE\n" + create_source_block + "\n") if create_source_block else "")
            + (("CREATE\n" + create_target_block + "\n") if create_target_block else "")
            + (("SET\n" + source_set_block + "\n") if source_set_block else "")
            + "RETURN\nsource"
        )
        # build params
        return query, cypher_vars

    @staticmethod
    def delete_cypher(label, source_id):  # pylint: disable-msg=too-many-locals
        """
        Converts request to a cypher delete statement
        """
        # Build the blocks
        query = "MATCH\n(source:%s {id: $source_id})\nDETACH DELETE source" % label

        # build params
        params = {"source_id": source_id}
        return query, params

    def _check_dependencies(self, resource_type):
        """
        Checks dependencies of resource by generating a cypher query to find them
        Todo: This should some day be atomic with generic_delete, can generate race conditions
        """
        resource_label = self.url_key[resource_type]
        dep_labels = []  # eg. Project, SampleSet
        for label in self.schema:
            if "IS_IN" in self.schema[label]["relationships"]:
                dependency_label = self.schema[label]["relationships"]["IS_IN"]
                if resource_label == dependency_label:
                    dep_labels.append(label)

        if len(dep_labels) > 0:
            individual_queries = []
            for i, dep in enumerate(dep_labels):
                query = (
                    "MATCH (main:"
                    + resource_label
                    + "{id: $id})<-[:IS_IN]-(d"
                    + str(i + 1)
                    + ":"
                    + dep
                    + ")\nRETURN d"
                    + str(i + 1)
                    + " as deps"
                )
                individual_queries.append(query)
            query = """\nUNION ALL\n""".join(individual_queries)
            return query
        return ""

    def close(self):
        """
        Closes a database
        """
        self.driver.close()

    def read(self, query, **kwargs):
        """
        Reads from a Cypher query
        """
        with self.driver.session() as session:
            # Write transactions allow the driver to handle retries and transient errors
            result = session.read_transaction(self._submit_query, query, **kwargs)
        return result

    def write(self, query, **kwargs):
        """
        Writes from a cypher query
        """
        with self.driver.session() as session:
            # Write transactions allow the driver to handle retries and transient errors
            result = session.write_transaction(self._submit_query, query, **kwargs)

        return result

    def auto_commit(self, query, **kwargs):
        """
        Auto commit, use is discouraged
        """
        with self.driver.session() as session:
            # Write transactions allow the driver to handle retries and transient errors
            result = session.run(query, **kwargs)

        return result

    def read_graphql(self, query, **kwargs):
        """
        Executes a graphql query with variables
        Returns a dictionary containing top level labels and data
        """

        # Convert graphql to cypher
        cypher = self.gql_to_cypher(query)
        results = self.read(cypher, **kwargs)

        # convert the top level results to graphql-like response?
        for result in results:
            labels = result.__dict__["_Record__keys"]
            records = {label: r for (label, r) in zip(labels, result)}

        return records

    def gql_to_cypher(self, query):
        """Converts a GraphQL request to Cypher"""
        query = self._strip_query(query)
        parsed_query = self._gql_to_ast(query)
        return self._ast_to_cypher(parsed_query)

    def parse_params(self, label, params):
        """
        Sanitizes and splits params into relationships and properly casted attributes

        Example:
        label = 'InjectionSet'
        params = {
            "LED_BY": "courtney_id",
            "USING_METHOD": "hp_id",
            "TEST_LIST1": ['hp_id', 'cn_id'], # just a test for ordered lists of connections
            "ON_INSTRUMENT": "",
            "num": "100",
            "acquisitionStarted": "2021-01-01",
        }

        Return:
        relationship_params = [
            ("LED_BY", "courtney_id"),
            ("USING_METHOD": "hp_id"),
            ("TEST_LIST1": "hp_id"),
            ("TEST_LIST1": "cn_id"),
            ("ON_INSTRUMENT": "")
        ]
        attribute_params = {
            "num": int("100"),
            "acquisitionStarted": (
                date.isoformat(date.fromisoformat("2021-01-01"))
            )
        }


        """
        relationship_params = []
        attribute_params = {}

        for key, value in params.items():
            if key in self.schema[label]["attributes"]:
                param_type = self.schema[label]["attributes"][key]
                # If there is no value, it is none
                if not value:
                    attribute_params[key] = None
                # dates are cast to ISO format
                elif param_type in [datetime, date]:
                    try:
                        attribute_params[key] = param_type.isoformat(
                            param_type.fromisoformat(value)
                        )
                    except ValueError as err:
                        raise ValueError(
                            f"For label '{key}', '{value}' is not suitable. Must be"
                            f" in the format YYYY-MM-DD."
                        ) from err
                # catchall. Value error if it can't be converted
                else:
                    try:
                        attribute_params[key] = param_type(value)
                    except ValueError as err:
                        raise ValueError(
                            f"For label '{key}', '{value}' is not suitable. Must be"
                            f" convertible to {param_type}: {str(err)}"
                        ) from err

            # otherwise it's a relationship
            elif key in self.schema[label]["relationships"]:
                param_type = self.schema[label]["relationships"][key]
                if isinstance(param_type, str):
                    relationship_params.append((key, value))
                elif isinstance(param_type, list):
                    if len(value) == 0:
                        relationship_params.append((key, []))
                    for v_single in value:
                        relationship_params.append((key, v_single))
            else:
                raise Exception(
                    f"Couldn't find {key} in attributes or relations for {label}"
                )

        return relationship_params, attribute_params

    def convert_dtypes(self, value, attr_name, label="Injection"):
        """
        Converts the value to the correct type for Neo4j
        """
        param_type = self.schema[label]["attributes"][attr_name]
        if param_type in [date, datetime]:
            return convert_datetime(value)
        return param_type(value)

    def generic_post(self, request):
        """
        Creates a new record from a request.
        request: Flask-Request like object, with attributes
            json: String, json payload from front end
            path: String, routing path, e.g "/birdfeeders"
        Returns a tuple with data and expected HTTP status.
        """
        path_params = self.get_path(request.path)
        label = self.url_key[path_params[0]]
        # check it has a name
        if not request.json["name"]:
            return ("You must specify a name.", 400)
        # disallow forward slashes in names
        if "/" in request.json["name"]:
            return (
                f"Forwarded slashes are not allowed in names. You provided: "
                f"'{request.json['name']}'",
                400,
            )
        # check the required resource exists
        # Todo this should be atomic (but isn't)
        if "IS_IN" in self.schema[label]["relationships"]:
            req_label = self.schema[label]["relationships"]["IS_IN"]
            if not request.json["IS_IN"]:
                return (
                    f"You are missing the parent node. Please specify with the 'IS_IN' relation.",
                    400,
                )

            cypher = (
                f"MATCH (a:{req_label} {{id: $id}}) OPTIONAL MATCH "
                f"(a)-[:IS_IN]-(b:{label}) RETURN a, b"
            )
            records = self.read(cypher, id=request.json["IS_IN"])
            if len(records) == 0:
                return (
                    f"The resource id {request.json['IS_IN']} does not match any "
                    f"node labeled as {req_label}.",
                    400,
                )
            try:
                names = [rec["b"]["name"] for rec in records]
            except TypeError:
                names = []
            if request.json["name"] in names:
                return (f"The name {request.json['name']} already exists.", 400)
        else:
            # if it's top level, check that no other resource exists with that name
            # Todo this should be atomic but isn't
            cypher = f"MATCH (a:{label} {{name: $name}}) RETURN a"
            records = self.read(cypher, name=request.json["name"])
            if len(records) > 0:
                return (
                    "You already have a resource with that name.",
                    400,
                )
        # proceed with the POST
        try:
            cypher, params = self.request_to_cypher(
                label, params=request.json, method=request.method
            )
        except (KeyError, ValueError) as err:
            return (f"There was an error: {err}", 400)
        records = self.write(cypher, **params)
        if len(records) >= 1:
            return ([dict(r["source"]) for r in records], 200)
        return (
            f"Error creating new {label}. Your fields might be the wrong type,"
            f" or the connections might not exist.",
            400,
        )

    def generic_patch(self, request):
        """
        Patches a record.
        request: Flask-Request like object, with attributes
            json: String, json payload from front end
            path: String, routing path containg the url label and the resource id
                e.g. "/birdfeeders/20220101_feeder_backyard_abcd"

        Returns a tuple with data and expected HTTP status.
        """
        path_params = self.get_path(request.path)
        label = self.url_key[path_params[0]]
        resource_id = path_params[1]
        # Disable changing the name or hierarchy
        if "id" in request.json or "IS_IN" in request.json or "name" in request.json:
            return (
                "You are not allowed to change the id, name, or target parent node.",
                400,
            )
        try:
            cypher, params = self.request_to_cypher(label, resource_id, request.json)
        except (KeyError, ValueError) as err:
            return (f"There was an error: {err}", 400)
        records = self.write(cypher, **params)
        if len(records) >= 1:
            return (dict(records[0][0]), 200)
        return (
            f"Error updating {label}. It may not exist, or your entries might be"
            f" the wrong type.",
            400,
        )

    def generic_delete(self, request):
        """Deletes a record. Returns a tuple with data and status code"""
        path_params = self.get_path(request.path)
        label = self.url_key[path_params[0]]
        path_params = self.get_path(request.path)
        resource_id = path_params[1]
        dependency_query = self._check_dependencies(path_params[0])
        if dependency_query:
            num_dependencies = len(self.read(dependency_query, id=resource_id))
            if num_dependencies > 0:
                return (
                    "Your resource still has dependencies and "
                    "cannot be deleted until they are deleted.",
                    400,
                )

        cypher, params = self.delete_cypher(label, resource_id)
        self.write(cypher, **params)
        return ("Deleted", 200)

    def generic_graphql(self, request):
        """Executes a graphql request from an HTTP request
        Returns tuple, data and expected response"""
        query = request.json["query"]
        try:
            params = request.json["variables"]
        except KeyError:
            params = {}
        if not params:
            params = {}
        results = self.read_graphql(query, **params)
        return ([True, {"data": results}], 200)

    @staticmethod
    def get_path(path):
        """
        Parse the path into arguments
        """
        path_params = path.replace("//", "/").split("/")[1:]
        path_params = [p.replace("{forwardSlash}", "/") for p in path_params]
        return path_params

    #######
    # Graphql Conversion Functions
    #######
    def _ast_to_cypher(self, query, p_varname="a"):
        """Translates graphql ast to cypher"""
        cypher = ""
        # top level, some special rules
        if isinstance(query, list):  # top level, slightly special rules
            returns = []
            for i, single_query in enumerate(query):
                returns.append(single_query["name"])
                cypher += "CALL {\n"
                cypher += self._ast_to_cypher(single_query, p_varname=p_varname)
                cypher += "\n}\n"
            cypher += "RETURN " + ",".join(returns)
            return cypher
        c_varname = p_varname + "_1"
        attributes = [attr for attr in query["attributes"] if isinstance(attr, str)]
        relationships = [attr for attr in query["attributes"] if isinstance(attr, dict)]

        label = query["label"]
        name = query["name"]

        cypher += f"MATCH ({c_varname}:{label}"

        # this is an insecure hack to allow for conditions
        if "condition" in query:
            cypher += " {" + query["condition"][1:-1] + "}"
        cypher += ")"
        if "dir" in query:
            rel = query["rel"]
            arrows = ("-", "->") if query["dir"].lower() == "in" else ("<-", "-")
            cypher += f"{arrows[0]}[r:{rel}]{arrows[1]}({p_varname}_s)"

        cypher += f"\nUNWIND {c_varname} as {c_varname + '_s'}"
        for rel in relationships:
            cypher += f"\nCALL {{\nWITH {c_varname+'_s'}\n"
            cypher += self._ast_to_cypher(rel, c_varname)
            cypher += "\n}"

        # create a return collect with attributes and subqueries
        cypher += "\nRETURN COLLECT({"
        attr_str = [f"{attr}: {c_varname}.{attr}" for attr in attributes]

        cypher += ",".join(attr_str)
        # if "dir" in query:
        #     cypher += ",__order: r.order_num"

        rel_str = [rel["name"] + ": " + rel["name"] for rel in relationships]
        if rel_str:
            cypher += "," + ",".join(rel_str)
        cypher += "}) as " + name

        return cypher

    def _gql_to_ast(self, query_str, label=None):
        """
        Parses a graphql request and converts to an ast. See unit tests for example
        """

        query_str = query_str.strip("\t\n ")
        attributes = []
        token_generator = self._next_token(query_str)
        for token, remaining in token_generator:
            if token is None:
                break

            # if it's a query, a graphql subquery, or a top level label
            if (
                token == "query"
                or (not label and token in self.schema)
                or token in self.schema[label]["graphql"]
            ):
                parsed_subquery = {}
                # if its a query, get the label from the next item
                if token == "query":
                    new_label, _ = next(token_generator)
                    token = new_label

                # token is the label in this case
                elif not label:
                    new_label = token

                # its a rel like 'collaborationWith', get labelname and direction
                else:
                    new_label = self.schema[label]["graphql"][token]["lab"]
                    parsed_subquery.update(
                        {
                            "dir": self.schema[label]["graphql"][token]["dir"],
                            "rel": self.schema[label]["graphql"][token]["rel"],
                        },
                    )

                if new_label not in self.schema:
                    raise ValueError(f"{new_label} label not found in schema.")

                subquery, _ = next(token_generator)

                # if there is a condition, add it in and get the next
                if subquery.startswith("("):
                    parsed_subquery.update({"condition": subquery})
                    subquery, _ = next(token_generator)

                parsed_subquery.update(
                    {
                        "name": token,
                        "attributes": self._gql_to_ast(subquery, new_label),
                        "label": new_label,
                    }
                )
                attributes.append(parsed_subquery)

            # if it is an attribute for our active label, just append it
            elif token in self.schema[label]["attributes"]:
                attributes.append(token)

            # if it's something else, complain
            else:
                raise ValueError(f"{repr(token)} not found in {label}")
        return attributes

    @staticmethod
    def _strip_query(query):
        """Quick fix function to strip the "query" out of graphql"""
        query = query.strip("\n\t ")
        # strip open and close brackets if it starts with them or with query
        if query.startswith(("{", "query")):
            o_bracket = query.find("{")
            c_bracket = query.rfind("}")
            query = query[o_bracket + 1 : c_bracket]
        return query

    @staticmethod
    def _next_token(query):
        """
        GraphQL Tokenizer, using a generator. Returns the token and remaining query.
        """
        # strip out whitespace and opening/closing brackets
        query = query.strip("\t\n ")
        if query.startswith("{"):
            query = query[query.find("{") + 1 : query.rfind("}")]

        while len(query) > 0:
            # find the start of the next token. Whitespace or brackets
            occurrences = [
                query.find(x) for x in ["\n", "\t", " ", "{", "("] if query.find(x) > -1
            ]
            # if nothing is found, must be last word.
            if len(occurrences) == 0:
                word = query
                query = ""
                yield word, query
                continue

            first = min(occurrences)

            # if the first item is a token sepator, use it. it's { or [
            if first == 0:
                first = 1
            word = query[:first]

            # if it's whitespace, go to the next item
            if word in [" ", "", "\n", "\t"]:
                query = query[first:].strip("\t\n ")
                continue

            # if it's an opening bracket, find the closing bracket and return that. Advance the whole query.

            elif word in ["{", "("]:
                if word == "{":
                    opposite = "}"
                else:
                    opposite = ")"
                status = 0
                for (closing_bracket, character) in enumerate(query):
                    if character == word:
                        status += 1
                    if character == opposite:
                        status -= 1
                    if status == 0:
                        break
                if status != 0:
                    raise Exception("Could not find a closing ", opposite)

                word = query[: closing_bracket + 1]
                query = query[closing_bracket + 1 :]

            else:
                query = query[first:]

            # yield the word and the remaining query
            yield word.strip(), query
        yield None, None


def gen_id(label, name):
    """Generates and ID for a node"""
    name = str(name)
    uuid = shortuuid.ShortUUID().random(length=8)
    # remove for gcp bucket compatibility
    disallowed = '\\\n\t/_*?"<>|.: '
    for character in disallowed:
        name = name.replace(character, "")
    datestr = datetime.now(tz=pytz.timezone("US/Eastern")).strftime("%Y%m%d")
    return f"{label}__{datestr}__{name}__{uuid}"


def convert_datetime(value):
    """Converts a date string to an ISO string"""
    try:
        return datetime.isoformat(datetime.strptime(value, "%m/%d/%y %H:%M"))
    except ValueError:
        pass
    try:
        return datetime.isoformat(datetime.strptime(value, "%m/%d/%Y %H:%M"))
    except ValueError:
        pass
    try:
        return datetime.isoformat(datetime.strptime(value, "%m/%d/%Y"))
    except ValueError:
        pass
    try:
        return datetime.isoformat(datetime.fromisoformat(value))
    except ValueError as err:
        raise ValueError(
            "There was an issue converting datetimes. Acceptable formats are:\nISO"
            "\nMM/DD/YYYY\nMM/DD/YYYY HH:MM\nMM/DD/YY HH:MM\nYou provided "
            f"'{value}'. Also verify that this is a 'real' date "
            "(e.g. not January 40th)"
        ) from err
