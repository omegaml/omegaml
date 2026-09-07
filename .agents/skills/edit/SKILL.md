---
name: edit
description: how to use the edit command properly
---

# Edit Skill

## Tool: edit

### Important Argument Requirement: `edits`

The `edits` argument for the edit tool must be a proper JSON array, not a stringified version.

#### Correct Usage

```json
{
  "path": "/workspace/example.txt",
  "edits": [
    {
      "oldText": "old content",
      "newText": "new content"
    }
  ]
}
```

#### Incorrect Usage

```json
{
  "path": "/workspace/example.txt",
  "edits": "{\"oldText\": \"old content\", \"newText\": \"new content\"}"
}
```

When passing the `edits` argument, ensure it's structured as a JSON array of edit objects with `oldText` and `newText` properties. If you're constructing this programmatically, make sure to pass the actual JSON array rather than a string representation of that array.

