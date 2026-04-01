// Show deployment hash nodes and provenance metadata.
MATCH (h:DeploymentHash)
RETURN h.component_kind AS component_kind,
       h.component_name AS component_name,
       h.hash_value AS content_hash,
       h.deployment_source AS deployment_source,
       h.updater AS updater,
       h.deployment_ref AS deployment_ref
ORDER BY h.component_kind, h.component_name;
