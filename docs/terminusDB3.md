WOQLSchema
classterminusdb_client.woqlschema.woql_schema.TerminusKey(keys=None)
Bases: object

__init__(keys=None)
classterminusdb_client.woqlschema.woql_schema.HashKey(keys=None)
Bases: TerminusKey

Generating ID with SHA256 using provided keys

at_type= 'Hash'
classterminusdb_client.woqlschema.woql_schema.LexicalKey(keys=None)
Bases: TerminusKey

Generating ID with urllib.parse.quote using provided keys

at_type= 'Lexical'
classterminusdb_client.woqlschema.woql_schema.ValueHashKey(keys=None)
Bases: TerminusKey

Generating ID with SHA256

at_type= 'ValueHash'
classterminusdb_client.woqlschema.woql_schema.RandomKey(keys=None)
Bases: TerminusKey

Generating ID with UUID4

at_type= 'Random'
classterminusdb_client.woqlschema.woql_schema.TerminusClass(name, bases, nmspc)
Bases: type

__init__(name, bases, nmspc)
get_instances()
classterminusdb_client.woqlschema.woql_schema.DocumentTemplate(*args, **kwargs)
Bases: object

__init__(*args, **kwargs)
classterminusdb_client.woqlschema.woql_schema.EnumMetaTemplate(cls, bases, classdict, *, boundary=None, _simple=False, **kwds)
Bases: EnumMeta

classterminusdb_client.woqlschema.woql_schema.EnumTemplate(value)
Bases: Enum

An enumeration.

__init__(value=None)
classterminusdb_client.woqlschema.woql_schema.TaggedUnion(*args, **kwargs)
Bases: DocumentTemplate

__init__(*args, **kwargs)
classterminusdb_client.woqlschema.woql_schema.WOQLSchema(title=None, description=None, authors=None, schema_ref=None, base_ref=None)
Bases: object

__init__(title=None, description=None, authors=None, schema_ref=None, base_ref=None)
propertycontext
add_enum_class(class_name, class_values)
Construct a TerminusDB Enum class by provideing class name and member values then add into the schema.

Parameters
class_name (str) – Name of the class object constructed.

class_values (list) – A list of values in this Enum.

Returns
A Enum object with the sepcified name and members

Return type
EnumMetaTemplate

commit(client, commit_msg=None, full_replace=False)
Commit the schema to database

Parameters
client (WOQLClient) – A client that is connected to a database.

commit_msg (str) – Commit message.

full_replace (bool) – Does the commit fully wiped out the old shcema graph. Default to be False.

from_db(client, select=None)
Load classes in the database schema into schema

Parameters
client (WOQLClient) – Client that is connected to the database

select (list of str, optional) – The classes (and depended classes) that will be imported, default to None which will import all classes

import_objects(obj_dict)
Import a list of documents in json format to Python objects. The schema of those documents need to be in this schema.

from_json_schema(name, json_schema, pipe=False, subdoc=False)
Load classe object from json schema (http://json-schema.org/) and, if pipe mode is off, add into schema. All referenced object will be treated as subdocuments.

Parameters
name (str) – Name of the class object.

json_schema (dict or str or StringIO) – Json Schema in dictionary or jsonisable string format or json file stream.

pipe (bool) – Pipe mode, if True will return the schema in TerminusDB dictionary format (just like calling to_dict) WITHOUT loading the schema into the schema object. Default to False.

subdoc (bool) – If not in pipe mode, the class object will be added as a subdocument class.

add_obj(name, obj)
all_obj()
to_dict()
Return the schema in the TerminusDB dictionary format

to_json_schema(class_object)
Return the schema in the json schema (http://json-schema.org/) format as a dictionary for the class object.

Parameters
object (class) – Name of the class object or the class object represented as dictionary.

copy()