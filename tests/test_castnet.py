"""
Test castnet
"""
from castnet import CastNetConn

SCHEMA = {
    "Project": {
        "attributes": {"alias": str,},
        "relationships": {"LED_BY": "MxpMember"},
        "graphql": {
            "ledBy": {"rel": "LED_BY", "dir": "OUT", "lab": "MxpMember",},
            "sampleSets": {"rel": "IS_IN", "dir": "IN", "lab": "SampleSet",},
        },
    },
    "SampleSet": {
        "IS_IN": "Project",
        "graphql": {"hasSamples": {"rel": "IS_IN", "dir": "IN", "lab": "Sample",},},
    },
    "InjectionSet": {
        "attributes": {"num": int,},
        "relationships": {
            "ON_INSTRUMENT": "Instrument",
            "LED_BY": "MxpMember",
            "USING_METHOD": "Method",
            "TEST_LIST1": ["Method"],  # Just for testing
            "TEST_LIST2": ["MxpMember"],  # Just for testing
        },
        "IS_IN": "SampleSet",
    },
    "Injection": {"relationships": {"IS_SAMPLE": "Sample",}, "IS_IN": "InjectionSet",},
    "Sample": {"IS_IN": "SampleSet",},
    "Instrument": {
        "graphql": {
            "injectionSets": {
                "rel": "ON_INSTRUMENT",
                "dir": "IN",
                "lab": "InjectionSet",
            }
        }
    },
    "MxpMember": {},
}
URL_KEY = {
    "projects": "Project",
    "samplesets": "SampleSet",
    "injectionsets": "InjectionSet",
    "samples": "Sample",
    "instruments": "Instrument",
}
CONN = CastNetConn(None, None, None, SCHEMA, URL_KEY)


def test_parse_to_cypher():
    """
    Integration test for the parsing of a query to Cypher
    """
    dflabel = "InjectionSet"
    dfuuid = "injectionset_id"
    params = {
        "LED_BY": "courtney_id",
        "USING_METHOD": "method_id",
        "ON_INSTRUMENT": "",
        "num": 100,
    }
    query, val = CONN.request_to_cypher(dflabel, dfuuid, params, method="PATCH")

    assert (
        query
        == """MATCH
(source:InjectionSet {id: $source_id})
WITH source
OPTIONAL MATCH (source)-[target_0_r:LED_BY]-()
OPTIONAL MATCH (source)-[target_1_r:USING_METHOD]-()
OPTIONAL MATCH (source)-[target_2_r:ON_INSTRUMENT]-()
DELETE
target_0_r,
target_1_r,
target_2_r
WITH DISTINCT source
MATCH
(target_0:MxpMember {id: $target_0_id}),
(target_1:Method {id: $target_1_id})
CREATE
(source)-[:LED_BY {order_num: 0}]->(target_0),
(source)-[:USING_METHOD {order_num: 1}]->(target_1)
SET
source.num=$num
RETURN
source"""
    )
    assert val == {
        "num": 100,
        "source_id": "injectionset_id",
        "target_0_id": "courtney_id",
        "target_1_id": "method_id",
    }

    query, val = CONN.request_to_cypher(dflabel, dfuuid, {})
    assert (
        query
        == """MATCH
(source:InjectionSet {id: $source_id})
RETURN
source"""
    )
    assert val == {
        "source_id": "injectionset_id",
    }

    params = {
        "IS_IN": "sampleset_id",
        "LED_BY": "courtney_id",
        "USING_METHOD": "method_id",
        "ON_INSTRUMENT": "",
        "name": "source_name",
        "num": 100,
    }
    query, val = CONN.request_to_cypher(dflabel, dfuuid, params, "POST")

    assert (
        query
        == """MATCH
(target_0:SampleSet {id: $target_0_id}),
(target_1:MxpMember {id: $target_1_id}),
(target_2:Method {id: $target_2_id})
CREATE
(source:InjectionSet {id: $source_id, name:$name, num:$num})
CREATE
(source)-[:IS_IN {order_num: 0}]->(target_0),
(source)-[:LED_BY {order_num: 1}]->(target_1),
(source)-[:USING_METHOD {order_num: 2}]->(target_2)
RETURN
source"""
    )
    val.pop("source_id")
    assert val == {
        "name": "source_name",
        "num": 100,
        "target_0_id": "sampleset_id",
        "target_1_id": "courtney_id",
        "target_2_id": "method_id",
    }

    query, val = CONN.delete_cypher(dflabel, dfuuid)
    assert (
        query
        == """MATCH
(source:InjectionSet {id: $source_id})
REMOVE source:InjectionSet
SET source:_archived_InjectionSet
RETURN
source"""
    )
    assert val == {
        "source_id": "injectionset_id",
    }

    params = {
        "IS_IN": "sampleset_id",
        "LED_BY": "courtney_id",
        "USING_METHOD": "method_id",
        "ON_INSTRUMENT": "",
        "name": "source_name",
        "num": 100,
        "TEST_LIST1": ["hp_id", "cn_id"],
        "TEST_LIST2": ["courtney_id", "daniel_id"],
    }

    query, val = CONN.request_to_cypher(dflabel, dfuuid, params, "PATCH")
    assert (
        query
        == """MATCH
(source:InjectionSet {id: $source_id})
WITH source
OPTIONAL MATCH (source)-[target_0_r:IS_IN]-()
OPTIONAL MATCH (source)-[target_1_r:LED_BY]-()
OPTIONAL MATCH (source)-[target_2_r:USING_METHOD]-()
OPTIONAL MATCH (source)-[target_3_r:ON_INSTRUMENT]-()
OPTIONAL MATCH (source)-[target_4_r:TEST_LIST1]-()
OPTIONAL MATCH (source)-[target_6_r:TEST_LIST2]-()
DELETE
target_0_r,
target_1_r,
target_2_r,
target_3_r,
target_4_r,
target_6_r
WITH DISTINCT source
MATCH
(target_0:SampleSet {id: $target_0_id}),
(target_1:MxpMember {id: $target_1_id}),
(target_2:Method {id: $target_2_id}),
(target_4:Method {id: $target_4_id}),
(target_5:Method {id: $target_5_id}),
(target_6:MxpMember {id: $target_6_id}),
(target_7:MxpMember {id: $target_7_id})
CREATE
(source)-[:IS_IN {order_num: 0}]->(target_0),
(source)-[:LED_BY {order_num: 1}]->(target_1),
(source)-[:USING_METHOD {order_num: 2}]->(target_2),
(source)-[:TEST_LIST1 {order_num: 4}]->(target_4),
(source)-[:TEST_LIST1 {order_num: 5}]->(target_5),
(source)-[:TEST_LIST2 {order_num: 6}]->(target_6),
(source)-[:TEST_LIST2 {order_num: 7}]->(target_7)
SET
source.name=$name,
source.num=$num
RETURN
source"""
    )

    assert val == {
        "num": 100,
        "name": "source_name",
        "source_id": "injectionset_id",
        "target_0_id": "sampleset_id",
        "target_1_id": "courtney_id",
        "target_2_id": "method_id",
        "target_4_id": "hp_id",
        "target_5_id": "cn_id",
        "target_6_id": "courtney_id",
        "target_7_id": "daniel_id",
    }

    dflabel = "Project"
    dfuuid = "project_id"
    params = {"LED_BY": "courtney_id", "alias": "test", "name": "project_name"}
    query, val = CONN.request_to_cypher(dflabel, dfuuid, params, "POST")

    assert (
        query
        == """MATCH
(target_0:MxpMember {id: $target_0_id})
CREATE
(source:Project {id: $source_id, alias:$alias, name:$name})
CREATE
(source)-[:LED_BY {order_num: 0}]->(target_0)
RETURN
source"""
    )
    val.pop("source_id")
    assert val == {
        "alias": "test",
        "target_0_id": "courtney_id",
        "name": "project_name",
    }

    query, val = CONN.delete_cypher(dflabel, dfuuid)
    assert (
        query
        == """MATCH
(source:Project {id: $source_id})
REMOVE source:Project
SET source:_archived_Project
RETURN
source"""
    )
    assert val == {
        "source_id": "project_id",
    }


def test_check_dependencies():
    """
    Test for checking existing dependencies before deleting
    """
    resource_type = "instruments"
    query = CONN._check_dependencies(resource_type)
    assert query == ""
    resource_type = "projects"
    query = CONN._check_dependencies(resource_type)
    assert (
        query
        == """MATCH (main:Project{id: $id})<-[:IS_IN]-(d1:SampleSet)
RETURN d1 as deps"""
    )

    resource_type = "samplesets"
    query = CONN._check_dependencies(resource_type)
    assert (
        query
        == """MATCH (main:SampleSet{id: $id})<-[:IS_IN]-(d1:InjectionSet)
RETURN d1 as deps
UNION ALL
MATCH (main:SampleSet{id: $id})<-[:IS_IN]-(d2:Sample)
RETURN d2 as deps"""
    )


def test_graphql():
    """Test conversion of grpahql to cypher"""
    query = """


query(ignore) {

Project(id: $id){
                name
        description
        sampleSets{
            id hasSamples      {name}
        }
        ledBy{name}
    }
    Instrument{name injectionSets{name}}
}
    """
    cypher = CONN.gql_to_cypher(query)
    assert (
        cypher
        == """CALL {
MATCH (a_1:Project {id: $id})
UNWIND a_1 as a_1_s
CALL {
WITH a_1_s
MATCH (a_1_1:SampleSet)-[r:IS_IN]->(a_1_s)
UNWIND a_1_1 as a_1_1_s
CALL {
WITH a_1_1_s
MATCH (a_1_1_1:Sample)-[r:IS_IN]->(a_1_1_s)
UNWIND a_1_1_1 as a_1_1_1_s
RETURN COLLECT({name: a_1_1_1.name}) as hasSamples
}
RETURN COLLECT({id: a_1_1.id,hasSamples: hasSamples}) as sampleSets
}
CALL {
WITH a_1_s
MATCH (a_1_1:MxpMember)<-[r:LED_BY]-(a_1_s)
UNWIND a_1_1 as a_1_1_s
RETURN COLLECT({name: a_1_1.name}) as ledBy
}
RETURN COLLECT({name: a_1.name,description: a_1.description,sampleSets: sampleSets,ledBy: ledBy}) as Project
}
CALL {
MATCH (a_1:Instrument)
UNWIND a_1 as a_1_s
CALL {
WITH a_1_s
MATCH (a_1_1:InjectionSet)-[r:ON_INSTRUMENT]->(a_1_s)
UNWIND a_1_1 as a_1_1_s
RETURN COLLECT({name: a_1_1.name}) as injectionSets
}
RETURN COLLECT({name: a_1.name,injectionSets: injectionSets}) as Instrument
}
RETURN Project,Instrument"""
    )
