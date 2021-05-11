#!/usr/bin/env python
import sys
import inspect
import os

import jsonschema
import json
import jsonref
from validator_collection import checkers
from jsonschema import validate

def open_jsonref(fileUrl):
    import requests
    if fileUrl[0:4] == "http":
        # es URL
        try:
            pointer = requests.get(fileUrl)
            output = jsonref.loads(pointer.content.decode('utf-8'), load_on_repr=False)
            return output
        except:
            return ""
    else:
        # es file
        try:
            file = open(fileUrl, "r")
            return jsonref.loads(file.read())
        except:
            return ""

def fail_with_msg(msg):
    print(msg)
    sys.exit(1)

def checkObject(jsonObject):
    result = {}
    if isinstance(jsonObject, list):
        if jsonObject in objectsToBeIgnored:
            return
        for subObject in jsonObject:
            result[subObject] = {}
            result[subObject]["result"] = checkObject(subObject)
    elif isinstance(jsonObject, str):
        print("String object")
    elif isinstance(jsonObject, dict):
        result["result"] = check_description(jsonObject)
        for subObject in jsonObject:
            result[subObject] = {}
            result[subObject]["result"] = checkObject(jsonObject[subObject])
    return result

def check_description(jsonObject):
    result = {}
    print(jsonObject)
    try:
        description = jsonObject["description"]
        if len(description) > 10:
            result["documented"] = True
            result["text"] = description
        else:
            result["documented"] = False
            result["text"] = incompleteDescription
    except:
        # special handling for geojson, they are considered to be documentd through reference
        try:
            if jsonObject["$id"] == geoJsonId:
                result["documented"] = True
                result["text"] = "GeoJson reference."
            else:
                result["documented"] = False
                result["text"] =withoutDescription
        except:
            result["documented"] = False
            result["text"] =withoutDescription
    return result

def order_dictionary(dictionary):
    # This function return the same dictionary but ordered by its keys
    import collections
    if isinstance(dictionary, dict):
        od = collections.OrderedDict(sorted(dictionary.items()))
        return od
    else:
        return dictionary

def find_line(schemaFile, phrase) :
    with open(schemaFile) as myFile:
        # github counts from 1...
        for num, line in enumerate(myFile, 1):
            if phrase in line:
                return num

def handleInvalidDescription(output, key, text):
    output["properties"][key] = {}
    lineNumber = -1
    if yamlDict[key]["ref"] is not None:
        lineNumber = find_line(schemaToValidate, yamlDict[key]["ref"])
        output["properties"][key]["ref"] = yamlDict[key]["ref"]
    else:
        lineNumber = find_line(schemaToValidate, f""""{key}":""")
    output["properties"][key]["line"] = lineNumber
    output["properties"][key]["documented"] = False
    output["properties"][key]["text"] = text

def checkDescription(output, key, description):
    if len(description) > 10:
        output["properties"][key]["documented"] = True
        output["properties"][key]["text"] = description
    else:
        handleInvalidDescription(output, key, incompleteDescription)

def checkForGeoJson(output, key, description):
    if yamlDict[key]["$id"] == geoJsonId:
        output["properties"][key]["documented"] = True
        output["properties"][key]["text"] = "GeoJson reference."
    else:
        handleInvalidDescription(output, key, withoutDescription)


def parse_payload(schema, level, referenceObject = None):
    output = {}
    if isinstance(schema, jsonref.JsonRef) or referenceObject is not None:
        if referenceObject is None:
            referenceObject = schema.__reference__
    if "allOf" in schema:
        for index in range(len(schema["allOf"])):
            partialOutput = parse_payload(schema["allOf"][index], level + 1, referenceObject)
            output = dict(output, **partialOutput)
    if "anyOf" in schema:
        for index in range(len(schema["anyOf"])):
            partialOutput = parse_payload(schema["anyOf"][index], level + 1, referenceObject)
            output = dict(output, **partialOutput)
    if "properties" in schema:
        for prop in schema["properties"]:
            if "allOf" in prop:
                output = parse_payload(schema["properties"]["allOf"], level + 1, referenceObject)
            elif "anyOf" in prop:
                output[prop] = parse_payload(schema["properties"]["anyOf"], level + 1, referenceObject)
            else:
                if prop in propertyList:
                    fail_with_msg(f"""Duplicate property key {prop}""")
                propertyList.append(prop)
                if prop not in output:
                    output[prop] = {}
                output[prop]["ref"] = referenceObject
                for item in list(schema["properties"][prop]):
                    if item == "description":
                        separatedDescription = str(schema["properties"][prop]["description"]).split(". ")
                        copiedDescription = list.copy(separatedDescription)
                        for descriptionPiece in separatedDescription:
                            if descriptionPiece in propertyTypes:
                                output[prop]["type"] = descriptionPiece
                                copiedDescription.remove(descriptionPiece)
                            elif descriptionPiece.find("Model:") > -1:
                                copiedDescription.remove(descriptionPiece)
                                try:
                                    output[prop]["x-ngsi"]["model"] = descriptionPiece.replace("'", "").replace("Model:", "")
                                except:
                                    output[prop]["x-ngsi"] = {}
                                    output[prop]["x-ngsi"]["model"] = descriptionPiece.replace("'", "").replace("Model:", "")

                            elif descriptionPiece.find("Units:") > -1:
                                copiedDescription.remove(descriptionPiece)
                                try:
                                    output[prop]["x-ngsi"]["units"] = descriptionPiece.replace("'", "").replace("Units:", "")
                                except:
                                    output[prop]["x-ngsi"] = {}
                                    output[prop]["x-ngsi"]["units"] = descriptionPiece.replace("'", "").replace("Units:", "")
                        description = ". ".join(copiedDescription)
                        output[prop]["description"] = description  # the remaining part of the description is used

                    elif item == "type":
                        output[prop]["type"] = schema["properties"][prop]["type"]
                    else:
                        output[prop][item] = schema["properties"][prop][item]
        return output
    else:
        return output

rootFolder = os.environ['ROOT_FOLDER']
schemaFile = os.environ['SCHEMA_FILE']
schemaToValidate = rootFolder + "/" + schemaFile

print(schemaToValidate)

# initialize variables for the script
output = {}  # the json answering the test
metaSchema = open_jsonref("https://json-schema.org/draft/2019-09/hyper-schema")
propertyTypes = ["Property", "Relationship", "Geoproperty"]
incompleteDescription = "Incomplete description"
withoutDescription = "No description at all"
geoJsonId = "https://geojson.org/schema/Geometry.json"
propertyList = []

# tests allowed
validTests = {"1": "Check that properties are properly documented"}


# test that it is a valid schema against the metaschema
try:
    schema = open_jsonref(schemaToValidate)
    if not bool(schema):
        output["result"] = False
        output["cause"] = "Json schema returned empty (wrong $ref?)."
        fail_with_msg(json.dumps(output))
except:
    output["result"] = False
    output["cause"] = "Json schema cannot be fully loaded."
    fail_with_msg(json.dumps(output))

try:
    validate(instance=schema, schema=metaSchema)
except jsonschema.exceptions.ValidationError as err:
    # print(err)
    output["result"] = False
    output["cause"] = "Schema does not validate as a json schema."
    output["parameters"] = {"schemaUrl": schemaUrl, "mail": mail, "test": test}
    output["errorSchema"] = str(err)
    fail_with_msg(json.dumps(output))

yamlDict = parse_payload(schema, 1)

output["properties"] = {}
for key in yamlDict:
    if key != "id":
        try:
            propertyType = yamlDict[key]["type"]
            if propertyType in propertyTypes:
                output["properties"][key] = {}
                output["properties"][key]["x-ngsi"] = True
                output["properties"][key]["x-ngsi_text"] = "ok to " + str(propertyType)
            else:
                output["properties"][key]["x-ngsi"] = False
                output["properties"][key]["x-ngsi_text"] = "Missing any of" + str(propertyTypes) + " in the description of the property"
        except:
            output["properties"][key] = {}
            output["properties"][key]["x-ngsi"] = False
            output["properties"][key]["x-ngsi_text"] = "Missing any of" + str(propertyTypes) + " in the description of the property"

        # checking the pure description
        try:
            description = yamlDict[key]["description"]
            checkDescription(output, key, description)
        except:
            # special handling for geojson, they are considered to be documentd through reference
            try:
                checkForGeoJson(output, key, description)
            except:
                handleInvalidDescription(output, key, withoutDescription)

annotations = []

def createAnnotation(output, key):
    print(output["properties"][key])
    annotation = {}
    annotation["file"] = schemaFile
    annotation["line"] =  output["properties"][key]["line"]
    if output["properties"][key]["text"] == incompleteDescription:
        annotation["annotation_level"] = "warning"
        if "ref" in output["properties"][key]:
            annotation["message"] = f"""The description of the referenced property {key} is to short, please add more information."""
        else:
            annotation["message"] = f"""The description of the property {key} is to short, please add more information."""
    elif output["properties"][key]["text"] == withoutDescription:
        annotation["annotation_level"] = "failure"
        if "ref" in output["properties"][key]:
            annotation["message"] = f"""The referenced property {key} lacks proper description."""
        else:
            annotation["message"] = f"""The property {key} lacks proper description."""
    return annotation

allProperties = 0
documentedProperties = 0
faultyDescriptionProperties = 0
notDescribedProperties = 0

for key in output["properties"]:
    allProperties += 1
    if output["properties"][key]["documented"]:
        documentedProperties += 1
    elif output["properties"][key]["text"] == incompleteDescription:
        annotations.append(createAnnotation(output, key))
        faultyDescriptionProperties += 1
    elif output["properties"][key]["text"] == withoutDescription:
        annotations.append(createAnnotation(output, key))
        notDescribedProperties += 1

if annotations:
    print(annotations)
    with open(rootFolder + '/annotations.json', 'w') as f:
        json.dump(annotations, f)

output["schemaDiagnose"] = "This schema has " + str(allProperties) + " properties. " + str(notDescribedProperties) +" properties are not described at all and " + str(faultyDescriptionProperties) + " have descriptions that must be completed. " + str(allProperties - faultyDescriptionProperties - notDescribedProperties) + " are described but you can review them anyway. "

print(json.dumps(output))

if faultyDescriptionProperties > 0 or notDescribedProperties > 0:
    with open(rootFolder + '/failure-result.json', 'w') as f:
        json.dump(output, f)
    sys.exit(1)

