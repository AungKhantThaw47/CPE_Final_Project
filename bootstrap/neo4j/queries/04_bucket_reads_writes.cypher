// Show data flow between components and storage buckets.
MATCH (a)-[r:READS_FROM|WRITES_TO]->(b:StorageBucket)
RETURN a.key AS component_key, type(r) AS relation, b.name AS bucket, r.path AS path
ORDER BY component_key, relation, bucket;
