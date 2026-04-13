// Job-Service connections overview.
// 1) Graph view: direct edges plus shared-bucket dataflow links between jobs and services.
MATCH (a)
MATCH (b)
WHERE (a:CloudRunJob OR a:CloudRunService)
   AND (b:CloudRunJob OR b:CloudRunService)
   AND a.key < b.key
OPTIONAL MATCH direct=(a)-[r]->(b)
WHERE type(r) IN ["TRIGGERS", "ORCHESTRATES", "DEPENDS_ON_DATA_FROM", "CALLS", "INVOKES"]
OPTIONAL MATCH writeA=(a)-[wa:WRITES_TO]->(bucket:StorageBucket)<-[rb:READS_FROM]-(b)
OPTIONAL MATCH writeB=(b)-[wb:WRITES_TO]->(bucket2:StorageBucket)<-[ra:READS_FROM]-(a)
WITH a, b,
     collect(DISTINCT direct) AS direct_paths,
     collect(DISTINCT writeA) AS a_to_b_bucket_paths,
     collect(DISTINCT writeB) AS b_to_a_bucket_paths,
     collect(DISTINCT bucket) + collect(DISTINCT bucket2) AS shared_buckets
WHERE size(direct_paths) > 0 OR size(a_to_b_bucket_paths) > 0 OR size(b_to_a_bucket_paths) > 0
UNWIND CASE WHEN size(shared_buckets) = 0 THEN [null] ELSE shared_buckets END AS bucket_node
RETURN a, b, direct_paths, a_to_b_bucket_paths, b_to_a_bucket_paths, bucket_node
ORDER BY a.name, b.name;

// 2) Table view: concise connectivity summary per job-service pair.
MATCH (job:CloudRunJob)
MATCH (svc:CloudRunService)
OPTIONAL MATCH (job)-[wj:WRITES_TO]->(bucket_js:StorageBucket)<-[rs:READS_FROM]-(svc)
OPTIONAL MATCH (svc)-[ws:WRITES_TO]->(bucket_sj:StorageBucket)<-[rj:READS_FROM]-(job)
OPTIONAL MATCH (job)-[dj:DEPENDS_ON_DATA_FROM]->(svc)
OPTIONAL MATCH (svc)-[ds:DEPENDS_ON_DATA_FROM]->(job)
WITH job, svc,
     collect(DISTINCT bucket_js.name) AS job_to_service_buckets,
     collect(DISTINCT bucket_sj.name) AS service_to_job_buckets,
     count(DISTINCT dj) AS direct_dep_job_to_service,
     count(DISTINCT ds) AS direct_dep_service_to_job
WHERE size(job_to_service_buckets) > 0
   OR size(service_to_job_buckets) > 0
   OR direct_dep_job_to_service > 0
   OR direct_dep_service_to_job > 0
RETURN job.name AS job_name,
       svc.name AS service_name,
       job_to_service_buckets,
       service_to_job_buckets,
       direct_dep_job_to_service,
       direct_dep_service_to_job,
       CASE
         WHEN size(job_to_service_buckets) > 0 AND size(service_to_job_buckets) > 0 THEN "bidirectional"
         WHEN size(job_to_service_buckets) > 0 THEN "job_to_service"
         WHEN size(service_to_job_buckets) > 0 THEN "service_to_job"
         WHEN direct_dep_job_to_service > 0 THEN "direct_job_to_service"
         ELSE "direct_service_to_job"
       END AS connection_type
ORDER BY job_name, service_name;
