# Panduan Melihat Graph di Neo4j Browser

## Cara Akses Neo4j Browser

### 1. Login ke Neo4j Aura
- Buka: https://console.neo4j.io/
- Login dengan akun Neo4j Aura Anda
- Pilih instance database Anda (ef142151.databases.neo4j.io)

### 2. Buka Neo4j Browser
- Setelah login, klik tombol **"Open"** atau **"Query"** pada instance database Anda
- Atau langsung akses: https://browser.neo4j.io/
- Masukkan kredensial:
  - **URI**: `neo4j+s://ef142151.databases.neo4j.io`
  - **Username**: (dari NEO4J_USER di .env)
  - **Password**: (dari NEO4J_PASSWORD di .env)

## Query Cypher untuk Melihat Graph

### 1. Lihat Semua Node dan Relationship (Overview)
```cypher
MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 50
```

### 2. Lihat Struktur Documentation → Version → Content
```cypher
MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CONTENT]->(c:Content)
RETURN d, v, c
LIMIT 20
```

### 3. Lihat Semua Documentation dengan Versinya
```cypher
MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)
RETURN d.name as Documentation, 
       collect(v.version) as Versions,
       d.description as Description
ORDER BY d.name
```

### 4. Lihat Versi yang Terhubung (Version Chain)
```cypher
MATCH path = (v1:Version)-[:NEXT_VERSION*]->(v2:Version)
RETURN path
LIMIT 10
```

### 5. Lihat Category dan Documentation yang Terhubung
```cypher
MATCH (cat:Category)-[:CONTAINS]->(d:Documentation)
RETURN cat.name as Category, 
       collect(d.name) as Documentations
ORDER BY cat.name
```

### 6. Lihat Changes untuk Setiap Version
```cypher
MATCH (d:Documentation)-[:HAS_VERSION]->(v:Version)-[:HAS_CHANGES]->(ch:Changes)-[:INCLUDES]->(change:Change)
RETURN d.name as Documentation,
       v.version as Version,
       change.name as ChangeName,
       change.description as ChangeDescription
LIMIT 20
```

### 7. Visualisasi Lengkap Graph (Semua Node Types)
```cypher
MATCH (n)
OPTIONAL MATCH (n)-[r]->(m)
RETURN n, r, m
LIMIT 100
```

### 8. Count Nodes by Type
```cypher
MATCH (n)
RETURN labels(n)[0] as NodeType, count(n) as Count
ORDER BY Count DESC
```

### 9. Lihat File Path dari Content Nodes
```cypher
MATCH (c:Content)
RETURN c.file as FilePath, c.type as Type
LIMIT 20
```

### 10. Lihat Graph dengan Filter Kategori Tertentu
```cypher
MATCH (cat:Category {name: 'kalender-akademik'})-[:CONTAINS]->(d:Documentation)-[:HAS_VERSION]->(v:Version)
RETURN cat, d, v
```

## Tips Visualisasi

1. **Gunakan Layout yang Sesuai**:
   - Klik ikon layout di toolbar (Force-directed, Hierarchical, dll)
   - Pilih yang paling sesuai untuk melihat struktur

2. **Filter Node**:
   - Klik kanan pada node untuk hide/show
   - Gunakan filter di sidebar untuk fokus pada node tertentu

3. **Expand Relationships**:
   - Klik node untuk expand relationships
   - Atau gunakan query dengan path yang lebih spesifik

4. **Warna Node**:
   - Neo4j Browser otomatis memberi warna berbeda untuk setiap label node
   - Documentation, Version, Content, Category, Change akan punya warna berbeda

## Query untuk Debugging

### Cek apakah ada node yang terisolasi
```cypher
MATCH (n)
WHERE NOT (n)--()
RETURN n
```

### Cek relationship types
```cypher
CALL db.relationshipTypes()
```

### Cek node labels
```cypher
CALL db.labels()
```

