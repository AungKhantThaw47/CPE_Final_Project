// Show end-to-end path across the job-based DVB pipeline.
MATCH p = (:CloudRunJob {name: "dvb-crawler-job"})-[*1..10]->(:CloudRunJob {name: "dvb-extractor-job"})
RETURN p;
