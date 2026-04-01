// List all Cloud Run jobs and services in the system graph.
MATCH (n)
WHERE n:CloudRunJob OR n:CloudRunService
RETURN labels(n)[0] AS kind, n.name AS name, n.key AS key
ORDER BY kind, name;
