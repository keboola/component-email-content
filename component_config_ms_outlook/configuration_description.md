- The content and metadata of emails are stored in the `emails` table.
- The attachments will be by default stored in the File Storage. To change this behaviour please use [processors](https://developers.keboola.com/extend/component/tutorial/processors/). See the example below.

Additional documentation [available](https://help.keboola.com/components/extractors/communication/email-imap/)

#### Example - Storing CSV attachments in Table Storage.

If your attachments are in csv format you can use this combination of processors to store them in the Table Storage:

- The `folder` parameter of the [first processor](https://github.com/keboola/processor-move-files) matches the resulting table name
- The [second processor](https://components.keboola.com/components/keboola.processor-create-manifest) defines that the result will always replace the destination table and expects header in the csv file.
- NOTE that in this setup all attachments will be stored in the same table, so they have to share the same structure.

```json
{
  "before": [],
  "after": [
    {
        "definition": {
          "component": "keboola.processor-move-files"
        },
        "parameters": {
          "direction": "tables",
          "folder": "result_table"
        }
      },
      {
        "definition": {
          "component": "keboola.processor-create-manifest"
        },
        "parameters": {
          "delimiter": ",",
          "enclosure": "\"",
          "incremental": false,
          "primary_key": [],
          "columns_from": "header"
        }
      }]
}
```