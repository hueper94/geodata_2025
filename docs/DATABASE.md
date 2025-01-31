# Datenbankschema

## Aktuelle Tabellen

### layers
```sql
CREATE TABLE layers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    title TEXT,
    original_name TEXT,
    cleaned_name TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Geplante Erweiterungen

### attributes
```sql
CREATE TABLE attributes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layer_id INTEGER,
    name TEXT NOT NULL,
    type TEXT,
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (layer_id) REFERENCES layers(id)
);
```

### attribute_values
```sql
CREATE TABLE attribute_values (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    attribute_id INTEGER,
    value TEXT,
    frequency INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (attribute_id) REFERENCES attributes(id)
);
```

### layer_metadata
```sql
CREATE TABLE layer_metadata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    layer_id INTEGER,
    key TEXT NOT NULL,
    value TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (layer_id) REFERENCES layers(id)
);
```

## Indizes

```sql
CREATE INDEX idx_layers_cleaned_name ON layers(cleaned_name);
CREATE INDEX idx_attributes_layer_id ON attributes(layer_id);
CREATE INDEX idx_attribute_values_attribute_id ON attribute_values(attribute_id);
CREATE INDEX idx_layer_metadata_layer_id ON layer_metadata(layer_id);
```

## Beispielabfragen

### Alle Layer mit Attributen
```sql
SELECT l.*, a.*
FROM layers l
LEFT JOIN attributes a ON l.id = a.layer_id;
```

### Attributwerte mit Häufigkeit
```sql
SELECT a.name, av.value, av.frequency
FROM attributes a
JOIN attribute_values av ON a.id = av.attribute_id
ORDER BY av.frequency DESC;
```

### Layer mit spezifischen Attributwerten
```sql
SELECT l.*, av.value
FROM layers l
JOIN attributes a ON l.id = a.layer_id
JOIN attribute_values av ON a.id = av.attribute_id
WHERE av.value LIKE '%suchbegriff%';
```

## Backup und Migration

- Tägliche Backups in `database/backups/`
- Migrations-Scripts in `database/migrations/`
- Automatische Versionierung der Datenbank 