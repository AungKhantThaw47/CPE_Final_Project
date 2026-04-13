// Show the daily pipeline orchestration order.
MATCH (:Workflow {name: "daily-pipeline"})-[r:ORCHESTRATES]->(job:CloudRunJob)
RETURN r.step_order AS step_order, job.name AS job_name
ORDER BY r.step_order;
