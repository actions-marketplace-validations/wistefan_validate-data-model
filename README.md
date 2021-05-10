# Create openapi.yaml github action

This action validates a given [JSON-Schema File](https://json-schema.org/) in regards to compliance as a [Smart-Data-Model](https://smartdatamodels.org/). 

The action provide information in the log output and annotation information for further usage.

## Inputs

### `schema-file`

**Required** Schema file to be validated, in reference to the repository root.

## Example usage

```yaml
uses: actions/validate-data-model@v1
with:
  schema-file: 'ACMeasurement/schema.json'
```