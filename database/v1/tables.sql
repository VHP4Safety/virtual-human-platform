CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_applicability_domain" TEXT,
  "pbpk_applicability_domain__term" TEXT,
  "pbpk_confidence_statement" TEXT,
  "pbpk_confidence_statement__term" TEXT,
  "pbpk_intended_use" TEXT,
  "pbpk_intended_use__term" TEXT,
  "pbpk_limitations" TEXT,
  "pbpk_limitations__term" TEXT,
  "pbpk_mathematical_representation" TEXT,
  "pbpk_mathematical_representation__term" TEXT,
  "pbpk_model_structure_description" TEXT,
  "pbpk_model_structure_description__term" TEXT,
  "pbpk_reproducibility_instructions" TEXT,
  "pbpk_reproducibility_instructions__term" TEXT,
  "schema_application_category" TEXT,
  "schema_application_category__term" TEXT,
  "schema_conditions_of_access" TEXT,
  "schema_conditions_of_access__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_is_based_on" TEXT,
  "schema_is_based_on__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  "schema_version" TEXT,
  "schema_version__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__record" ON "bioschemas_computational_workflow" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__bioschemas_input" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__bioschemas_input__record" ON "bioschemas_computational_workflow__bioschemas_input" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__bioschemas_output" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__bioschemas_output__record" ON "bioschemas_computational_workflow__bioschemas_output" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_connections" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_connections__record" ON "bioschemas_computational_workflow__pbpk_connections" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_biological_system" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_biological_system__record" ON "bioschemas_computational_workflow__pbpk_has_biological_system" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_calibration" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_calibration__record" ON "bioschemas_computational_workflow__pbpk_has_calibration" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_chemical" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_chemical__record" ON "bioschemas_computational_workflow__pbpk_has_chemical" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_evaluation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_evaluation__record" ON "bioschemas_computational_workflow__pbpk_has_evaluation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_parameter" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_parameter__record" ON "bioschemas_computational_workflow__pbpk_has_parameter" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_suv_analysis" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_has_suv_analysis__record" ON "bioschemas_computational_workflow__pbpk_has_suv_analysis" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_implementation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_implementation__record" ON "bioschemas_computational_workflow__pbpk_implementation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__pbpk_structural_compartments" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__pbpk_structural_compartments__record" ON "bioschemas_computational_workflow__pbpk_structural_compartments" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_about__record" ON "bioschemas_computational_workflow__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_alternate_name__record" ON "bioschemas_computational_workflow__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_citation__record" ON "bioschemas_computational_workflow__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_code_repository" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_code_repository__record" ON "bioschemas_computational_workflow__schema_code_repository" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_contributor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_contributor__record" ON "bioschemas_computational_workflow__schema_contributor" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_creative_work_status" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_creative_work_status__record" ON "bioschemas_computational_workflow__schema_creative_work_status" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_creator__record" ON "bioschemas_computational_workflow__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_documentation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_documentation__record" ON "bioschemas_computational_workflow__schema_documentation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_encoding_format" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_encoding_format__record" ON "bioschemas_computational_workflow__schema_encoding_format" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_funding" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_funding__record" ON "bioschemas_computational_workflow__schema_funding" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_has_part__record" ON "bioschemas_computational_workflow__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_identifier__record" ON "bioschemas_computational_workflow__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_image" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_image__record" ON "bioschemas_computational_workflow__schema_image" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_keywords__record" ON "bioschemas_computational_workflow__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_maintainer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_maintainer__record" ON "bioschemas_computational_workflow__schema_maintainer" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_producer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_producer__record" ON "bioschemas_computational_workflow__schema_producer" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_programming_language" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_programming_language__record" ON "bioschemas_computational_workflow__schema_programming_language" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_publisher" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_publisher__record" ON "bioschemas_computational_workflow__schema_publisher" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_runtime_platform" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_runtime_platform__record" ON "bioschemas_computational_workflow__schema_runtime_platform" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_same_as__record" ON "bioschemas_computational_workflow__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_sd_publisher" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_sd_publisher__record" ON "bioschemas_computational_workflow__schema_sd_publisher" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_software_requirements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_software_requirements__record" ON "bioschemas_computational_workflow__schema_software_requirements" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_computational_workflow__schema_target_product" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_computational_workflow" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_computational_workflow__schema_target_product__record" ON "bioschemas_computational_workflow__schema_target_product" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "bioschemas_draft_ethical_legal_social" TEXT,
  "bioschemas_draft_ethical_legal_social__term" TEXT,
  "bioschemas_draft_intended_use" TEXT,
  "bioschemas_draft_intended_use__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_perform_time" TEXT,
  "schema_perform_time__term" TEXT,
  "schema_prep_time" TEXT,
  "schema_prep_time__term" TEXT,
  "schema_total_time" TEXT,
  "schema_total_time__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__record" ON "bioschemas_draft_lab_protocol" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_bio_sample" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_bio_sample__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_bio_sample" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_computational_tool" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_computational_tool__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_computational_tool" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_lab_equipment" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_lab_equipment__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_lab_equipment" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_advantage" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_advantage__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_advantage" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_application" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_application__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_application" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_limitation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_limitation__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_limitation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_outcome" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_outcome__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_protocol_outcome" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_reagent" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__bioschemas_draft_reagent__record" ON "bioschemas_draft_lab_protocol__bioschemas_draft_reagent" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_author" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_author__record" ON "bioschemas_draft_lab_protocol__schema_author" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_citation__record" ON "bioschemas_draft_lab_protocol__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_based_on__record" ON "bioschemas_draft_lab_protocol__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_part_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_part_of__record" ON "bioschemas_draft_lab_protocol__schema_is_part_of" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_keywords__record" ON "bioschemas_draft_lab_protocol__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_same_as__record" ON "bioschemas_draft_lab_protocol__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_step" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_step__record" ON "bioschemas_draft_lab_protocol__schema_step" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "bioschemas_draft_study_domain" TEXT,
  "bioschemas_draft_study_domain__term" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_author" TEXT,
  "schema_author__term" TEXT,
  "schema_citation" TEXT,
  "schema_citation__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_end_date" TEXT,
  "schema_end_date__term" TEXT,
  "schema_has_growth_facility" TEXT,
  "schema_has_growth_facility__term" TEXT,
  "schema_headline" TEXT,
  "schema_headline__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_is_part_of" TEXT,
  "schema_is_part_of__term" TEXT,
  "schema_keywords" TEXT,
  "schema_keywords__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_start_date" TEXT,
  "schema_start_date__term" TEXT,
  "schema_study_location" TEXT,
  "schema_study_location__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__record" ON "bioschemas_draft_study" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__bioschemas_draft_related_study" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__bioschemas_draft_related_study__record" ON "bioschemas_draft_study__bioschemas_draft_related_study" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__bioschemas_draft_study_process" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__bioschemas_draft_study_process__record" ON "bioschemas_draft_study__bioschemas_draft_study_process" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_about__record" ON "bioschemas_draft_study__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_additional_property" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_additional_property__record" ON "bioschemas_draft_study__schema_additional_property" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_creator__record" ON "bioschemas_draft_study__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_has_part__record" ON "bioschemas_draft_study__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_same_as__record" ON "bioschemas_draft_study__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_study_subject" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_study_subject__record" ON "bioschemas_draft_study__schema_study_subject" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_formal_parameter" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_default_value" TEXT,
  "schema_default_value__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_value_required" TEXT,
  "schema_value_required__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_formal_parameter__record" ON "bioschemas_formal_parameter" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_formal_parameter__schema_additional_type" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_formal_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_formal_parameter__schema_additional_type__record" ON "bioschemas_formal_parameter__schema_additional_type" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_formal_parameter__schema_encoding_format" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_formal_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_formal_parameter__schema_encoding_format__record" ON "bioschemas_formal_parameter__schema_encoding_format" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_formal_parameter__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_formal_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_formal_parameter__schema_identifier__record" ON "bioschemas_formal_parameter__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_about_page" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_main_entity" TEXT,
  "schema_main_entity__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_about_page__record" ON "schema_about_page" ("record");
CREATE TABLE IF NOT EXISTS "schema_about_page__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_about_page" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_about_page__schema_about__record" ON "schema_about_page__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_about_page__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_about_page" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_about_page__schema_has_part__record" ON "schema_about_page__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_chemical_composition" TEXT,
  "schema_chemical_composition__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_disambiguating_description" TEXT,
  "schema_disambiguating_description__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__record" ON "schema_chemical_substance" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_alternate_name__record" ON "schema_chemical_substance__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_bio_chem_interaction" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_bio_chem_interaction__record" ON "schema_chemical_substance__schema_bio_chem_interaction" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_bio_chem_similarity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_bio_chem_similarity__record" ON "schema_chemical_substance__schema_bio_chem_similarity" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_biological_role" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_biological_role__record" ON "schema_chemical_substance__schema_biological_role" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_chemical_role" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_chemical_role__record" ON "schema_chemical_substance__schema_chemical_role" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_has_bio_chem_entity_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_has_bio_chem_entity_part__record" ON "schema_chemical_substance__schema_has_bio_chem_entity_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_image" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_image__record" ON "schema_chemical_substance__schema_image" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_potential_use" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_potential_use__record" ON "schema_chemical_substance__schema_potential_use" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_same_as__record" ON "schema_chemical_substance__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_chemical_substance__schema_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_chemical_substance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_chemical_substance__schema_url__record" ON "schema_chemical_substance__schema_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_course" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_accessibility_summary" TEXT,
  "schema_accessibility_summary__term" TEXT,
  "schema_aggregate_rating" TEXT,
  "schema_aggregate_rating__term" TEXT,
  "schema_comment_count" TEXT,
  "schema_comment_count__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_educational_credential_awarded" TEXT,
  "schema_educational_credential_awarded__term" TEXT,
  "schema_educational_level" TEXT,
  "schema_educational_level__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_keywords" TEXT,
  "schema_keywords__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_thumbnail_url" TEXT,
  "schema_thumbnail_url__term" TEXT,
  "schema_time_required" TEXT,
  "schema_time_required__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__record" ON "schema_course" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_about__record" ON "schema_course__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_alternate_name__record" ON "schema_course__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_audience" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_audience__record" ON "schema_course__schema_audience" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_citation__record" ON "schema_course__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_comment" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_comment__record" ON "schema_course__schema_comment" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_course_code" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_course_code__record" ON "schema_course__schema_course_code" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_course_prerequisites" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_course_prerequisites__record" ON "schema_course__schema_course_prerequisites" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_creator__record" ON "schema_course__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_date_modified" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_date_modified__record" ON "schema_course__schema_date_modified" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_has_course_instance" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_has_course_instance__record" ON "schema_course__schema_has_course_instance" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_has_part__record" ON "schema_course__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_is_based_on__record" ON "schema_course__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_mentions" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_mentions__record" ON "schema_course__schema_mentions" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_provider" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_provider__record" ON "schema_course__schema_provider" ("record");
CREATE TABLE IF NOT EXISTS "schema_course__schema_teaches" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course__schema_teaches__record" ON "schema_course__schema_teaches" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_duration" TEXT,
  "schema_duration__term" TEXT,
  "schema_end_date" TEXT,
  "schema_end_date__term" TEXT,
  "schema_event_status" TEXT,
  "schema_event_status__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_in_language" TEXT,
  "schema_in_language__term" TEXT,
  "schema_location" TEXT,
  "schema_location__term" TEXT,
  "schema_maximum_attendee_capacity" TEXT,
  "schema_maximum_attendee_capacity__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_start_date" TEXT,
  "schema_start_date__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__record" ON "schema_course_instance" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_alternate_name__record" ON "schema_course_instance__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_contributor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_contributor__record" ON "schema_course_instance__schema_contributor" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_course_mode" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_course_mode__record" ON "schema_course_instance__schema_course_mode" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_funder" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_funder__record" ON "schema_course_instance__schema_funder" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_instructor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_instructor__record" ON "schema_course_instance__schema_instructor" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_offers" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_offers__record" ON "schema_course_instance__schema_offers" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_organizer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_organizer__record" ON "schema_course_instance__schema_organizer" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_sub_event" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_sub_event__record" ON "schema_course_instance__schema_sub_event" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_super_event" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_super_event__record" ON "schema_course_instance__schema_super_event" ("record");
CREATE TABLE IF NOT EXISTS "schema_course_instance__schema_work_featured" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_course_instance" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_course_instance__schema_work_featured__record" ON "schema_course_instance__schema_work_featured" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_about" TEXT,
  "schema_about__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__record" ON "schema_data_catalog" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_alternate_name__record" ON "schema_data_catalog__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_citation__record" ON "schema_data_catalog__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_dataset" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_dataset__record" ON "schema_data_catalog__schema_dataset" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_encoding_format" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_encoding_format__record" ON "schema_data_catalog__schema_encoding_format" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_identifier__record" ON "schema_data_catalog__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_keywords__record" ON "schema_data_catalog__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_provider" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_provider__record" ON "schema_data_catalog__schema_provider" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_source_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_source_organization__record" ON "schema_data_catalog__schema_source_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_has_part" TEXT,
  "schema_has_part__term" TEXT,
  "schema_is_accessible_for_free" TEXT,
  "schema_is_accessible_for_free__term" TEXT,
  "schema_is_part_of" TEXT,
  "schema_is_part_of__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_publisher" TEXT,
  "schema_publisher__term" TEXT,
  "schema_same_as" TEXT,
  "schema_same_as__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  "schema_version" TEXT,
  "schema_version__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__record" ON "schema_dataset" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_alternate_name__record" ON "schema_dataset__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_citation__record" ON "schema_dataset__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_creator__record" ON "schema_dataset__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_distribution" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_distribution__record" ON "schema_dataset__schema_distribution" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_identifier__record" ON "schema_dataset__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_included_in_data_catalog" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_included_in_data_catalog__record" ON "schema_dataset__schema_included_in_data_catalog" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_is_based_on__record" ON "schema_dataset__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_keywords__record" ON "schema_dataset__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_maintainer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_maintainer__record" ON "schema_dataset__schema_maintainer" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_measurement_technique" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_measurement_technique__record" ON "schema_dataset__schema_measurement_technique" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_variable_measured" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_variable_measured__record" ON "schema_dataset__schema_variable_measured" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_in_defined_term_set" TEXT,
  "schema_in_defined_term_set__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_term_code" TEXT,
  "schema_term_code__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__record" ON "schema_defined_term" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__schema_same_as__record" ON "schema_defined_term__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term__schema_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__schema_url__record" ON "schema_defined_term__schema_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_conditions_of_access" TEXT,
  "schema_conditions_of_access__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_is_accessible_for_free" TEXT,
  "schema_is_accessible_for_free__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_same_as" TEXT,
  "schema_same_as__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  "schema_version" TEXT,
  "schema_version__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__record" ON "schema_defined_term_set" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_alternate_name__record" ON "schema_defined_term_set__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_citation__record" ON "schema_defined_term_set__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_creator__record" ON "schema_defined_term_set__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_has_defined_term" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_has_defined_term__record" ON "schema_defined_term_set__schema_has_defined_term" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_keywords__record" ON "schema_defined_term_set__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_maintainer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_maintainer__record" ON "schema_defined_term_set__schema_maintainer" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_accessibility_summary" TEXT,
  "schema_accessibility_summary__term" TEXT,
  "schema_creative_work_status" TEXT,
  "schema_creative_work_status__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_educational_level" TEXT,
  "schema_educational_level__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_time_required" TEXT,
  "schema_time_required__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  "schema_version" TEXT,
  "schema_version__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__record" ON "schema_learning_resource" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_about__record" ON "schema_learning_resource__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_audience" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_audience__record" ON "schema_learning_resource__schema_audience" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_author" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_author__record" ON "schema_learning_resource__schema_author" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_competency_required" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_competency_required__record" ON "schema_learning_resource__schema_competency_required" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_contributor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_contributor__record" ON "schema_learning_resource__schema_contributor" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_has_part__record" ON "schema_learning_resource__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_identifier__record" ON "schema_learning_resource__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_in_language" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_in_language__record" ON "schema_learning_resource__schema_in_language" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_is_part_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_is_part_of__record" ON "schema_learning_resource__schema_is_part_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_keywords__record" ON "schema_learning_resource__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_learning_resource_type" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_learning_resource_type__record" ON "schema_learning_resource__schema_learning_resource_type" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_license" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_license__record" ON "schema_learning_resource__schema_license" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_mentions" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_mentions__record" ON "schema_learning_resource__schema_mentions" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_recorded_at" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_recorded_at__record" ON "schema_learning_resource__schema_recorded_at" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_teaches" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_teaches__record" ON "schema_learning_resource__schema_teaches" ("record");
CREATE TABLE IF NOT EXISTS "schema_learning_resource__schema_work_translation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_learning_resource" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_learning_resource__schema_work_translation__record" ON "schema_learning_resource__schema_work_translation" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_disambiguating_description" TEXT,
  "schema_disambiguating_description__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_in_ch_i" TEXT,
  "schema_in_ch_i__term" TEXT,
  "schema_in_ch_i_key" TEXT,
  "schema_in_ch_i_key__term" TEXT,
  "schema_iupac_name" TEXT,
  "schema_iupac_name__term" TEXT,
  "schema_molecular_formula" TEXT,
  "schema_molecular_formula__term" TEXT,
  "schema_molecular_weight" TEXT,
  "schema_molecular_weight__term" TEXT,
  "schema_monoisotopic_molecular_weight" TEXT,
  "schema_monoisotopic_molecular_weight__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__record" ON "schema_molecular_entity" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_alternate_name__record" ON "schema_molecular_entity__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_associated_disease" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_associated_disease__record" ON "schema_molecular_entity__schema_associated_disease" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_bio_chem_interaction" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_bio_chem_interaction__record" ON "schema_molecular_entity__schema_bio_chem_interaction" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_bio_chem_similarity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_bio_chem_similarity__record" ON "schema_molecular_entity__schema_bio_chem_similarity" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_biological_role" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_biological_role__record" ON "schema_molecular_entity__schema_biological_role" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_chemical_role" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_chemical_role__record" ON "schema_molecular_entity__schema_chemical_role" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_has_bio_chem_entity_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_has_bio_chem_entity_part__record" ON "schema_molecular_entity__schema_has_bio_chem_entity_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_has_molecular_function" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_has_molecular_function__record" ON "schema_molecular_entity__schema_has_molecular_function" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_has_representation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_has_representation__record" ON "schema_molecular_entity__schema_has_representation" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_image" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_image__record" ON "schema_molecular_entity__schema_image" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_is_encoded_by_bio_chem_entity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_is_encoded_by_bio_chem_entity__record" ON "schema_molecular_entity__schema_is_encoded_by_bio_chem_entity" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_is_involved_in_biological_process" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_is_involved_in_biological_process__record" ON "schema_molecular_entity__schema_is_involved_in_biological_process" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_is_located_in_subcellular_location" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_is_located_in_subcellular_location__record" ON "schema_molecular_entity__schema_is_located_in_subcellular_location" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_is_part_of_bio_chem_entity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_is_part_of_bio_chem_entity__record" ON "schema_molecular_entity__schema_is_part_of_bio_chem_entity" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_potential_use" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_potential_use__record" ON "schema_molecular_entity__schema_potential_use" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_same_as__record" ON "schema_molecular_entity__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_smiles" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_smiles__record" ON "schema_molecular_entity__schema_smiles" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_taxonomic_range" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_taxonomic_range__record" ON "schema_molecular_entity__schema_taxonomic_range" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_url__record" ON "schema_molecular_entity__schema_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_monetary_grant" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_alternate_name" TEXT,
  "schema_alternate_name__term" TEXT,
  "schema_amount" TEXT,
  "schema_amount__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_monetary_grant__record" ON "schema_monetary_grant" ("record");
CREATE TABLE IF NOT EXISTS "schema_monetary_grant__schema_funder" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_monetary_grant" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_monetary_grant__schema_funder__record" ON "schema_monetary_grant__schema_funder" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "biothings_bioschemas_budget" TEXT,
  "biothings_bioschemas_budget__term" TEXT,
  "biothings_bioschemas_funding_model" TEXT,
  "biothings_bioschemas_funding_model__term" TEXT,
  "schema_alternate_name" TEXT,
  "schema_alternate_name__term" TEXT,
  "schema_date_modified" TEXT,
  "schema_date_modified__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_dissolution_date" TEXT,
  "schema_dissolution_date__term" TEXT,
  "schema_founding_date" TEXT,
  "schema_founding_date__term" TEXT,
  "schema_keywords" TEXT,
  "schema_keywords__term" TEXT,
  "schema_legal_name" TEXT,
  "schema_legal_name__term" TEXT,
  "schema_location" TEXT,
  "schema_location__term" TEXT,
  "schema_logo" TEXT,
  "schema_logo__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_parent_organization" TEXT,
  "schema_parent_organization__term" TEXT,
  "schema_same_as" TEXT,
  "schema_same_as__term" TEXT,
  "schema_status" TEXT,
  "schema_status__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__record" ON "schema_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__biothings_bioschemas_attachment" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__biothings_bioschemas_attachment__record" ON "schema_organization__biothings_bioschemas_attachment" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__biothings_bioschemas_founder_member" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__biothings_bioschemas_founder_member__record" ON "schema_organization__biothings_bioschemas_founder_member" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__biothings_bioschemas_membership_category" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__biothings_bioschemas_membership_category__record" ON "schema_organization__biothings_bioschemas_membership_category" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__biothings_bioschemas_social_media" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__biothings_bioschemas_social_media__record" ON "schema_organization__biothings_bioschemas_social_media" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__biothings_bioschemas_topic" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__biothings_bioschemas_topic__record" ON "schema_organization__biothings_bioschemas_topic" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__rdf_type" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__rdf_type__record" ON "schema_organization__rdf_type" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_contact_point" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_contact_point__record" ON "schema_organization__schema_contact_point" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_department" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_department__record" ON "schema_organization__schema_department" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_member" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_member__record" ON "schema_organization__schema_member" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_member_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_member_of__record" ON "schema_organization__schema_member_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_owns" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_owns__record" ON "schema_organization__schema_owns" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_sub_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_sub_organization__record" ON "schema_organization__schema_sub_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_url__record" ON "schema_organization__schema_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_person" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "biothings_bioschemas_curriculum_vitae" TEXT,
  "biothings_bioschemas_curriculum_vitae__term" TEXT,
  "biothings_bioschemas_expertise" TEXT,
  "biothings_bioschemas_expertise__term" TEXT,
  "biothings_bioschemas_orcid" TEXT,
  "biothings_bioschemas_orcid__term" TEXT,
  "schema_email" TEXT,
  "schema_email__term" TEXT,
  "schema_home_location" TEXT,
  "schema_home_location__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_knows_language" TEXT,
  "schema_knows_language__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__record" ON "schema_person" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_advisor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_advisor__record" ON "schema_person__biothings_bioschemas_advisor" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_experience" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_experience__record" ON "schema_person__biothings_bioschemas_experience" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_interest" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_interest__record" ON "schema_person__biothings_bioschemas_interest" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_internatonal_activities" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_internatonal_activities__record" ON "schema_person__biothings_bioschemas_internatonal_activities" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_journal_referee" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_journal_referee__record" ON "schema_person__biothings_bioschemas_journal_referee" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__biothings_bioschemas_works" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__biothings_bioschemas_works__record" ON "schema_person__biothings_bioschemas_works" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_description" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_description__record" ON "schema_person__schema_description" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_funding" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_funding__record" ON "schema_person__schema_funding" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_keywords__record" ON "schema_person__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_main_entity_of_page" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_main_entity_of_page__record" ON "schema_person__schema_main_entity_of_page" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_member_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_member_of__record" ON "schema_person__schema_member_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_same_as__record" ON "schema_person__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_works_for" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_works_for__record" ON "schema_person__schema_works_for" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_date_created" TEXT,
  "schema_date_created__term" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_funder" TEXT,
  "schema_funder__term" TEXT,
  "schema_headline" TEXT,
  "schema_headline__term" TEXT,
  "schema_is_accessible_for_free" TEXT,
  "schema_is_accessible_for_free__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_page_end" TEXT,
  "schema_page_end__term" TEXT,
  "schema_page_start" TEXT,
  "schema_page_start__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__record" ON "schema_scholarly_article" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_about__record" ON "schema_scholarly_article__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_article_body" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_article_body__record" ON "schema_scholarly_article__schema_article_body" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_author" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_author__record" ON "schema_scholarly_article__schema_author" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_citation__record" ON "schema_scholarly_article__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_correction" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_correction__record" ON "schema_scholarly_article__schema_correction" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_date_modified" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_date_modified__record" ON "schema_scholarly_article__schema_date_modified" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_editor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_editor__record" ON "schema_scholarly_article__schema_editor" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_identifier__record" ON "schema_scholarly_article__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_in_language" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_in_language__record" ON "schema_scholarly_article__schema_in_language" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_is_based_on__record" ON "schema_scholarly_article__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_is_part_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_is_part_of__record" ON "schema_scholarly_article__schema_is_part_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_keywords__record" ON "schema_scholarly_article__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_pagination" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_pagination__record" ON "schema_scholarly_article__schema_pagination" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_publisher" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_publisher__record" ON "schema_scholarly_article__schema_publisher" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_same_as__record" ON "schema_scholarly_article__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_url__record" ON "schema_scholarly_article__schema_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_is_accessible_for_free" TEXT,
  "schema_is_accessible_for_free__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_thumbnail_url" TEXT,
  "schema_thumbnail_url__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__record" ON "schema_software_application" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__bioschemas_input" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__bioschemas_input__record" ON "schema_software_application__bioschemas_input" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__bioschemas_output" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__bioschemas_output__record" ON "schema_software_application__bioschemas_output" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_application_category" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_application_category__record" ON "schema_software_application__schema_application_category" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_application_sub_category" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_application_sub_category__record" ON "schema_software_application__schema_application_sub_category" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_application_suite" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_application_suite__record" ON "schema_software_application__schema_application_suite" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_author" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_author__record" ON "schema_software_application__schema_author" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_citation__record" ON "schema_software_application__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_code_repository" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_code_repository__record" ON "schema_software_application__schema_code_repository" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_contributor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_contributor__record" ON "schema_software_application__schema_contributor" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_discussion_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_discussion_url__record" ON "schema_software_application__schema_discussion_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_download_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_download_url__record" ON "schema_software_application__schema_download_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_feature_list" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_feature_list__record" ON "schema_software_application__schema_feature_list" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_funder" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_funder__record" ON "schema_software_application__schema_funder" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_has_part__record" ON "schema_software_application__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_identifier__record" ON "schema_software_application__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_is_based_on__record" ON "schema_software_application__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_is_part_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_is_part_of__record" ON "schema_software_application__schema_is_part_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_keywords__record" ON "schema_software_application__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_license" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_license__record" ON "schema_software_application__schema_license" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_operating_system" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_operating_system__record" ON "schema_software_application__schema_operating_system" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_programming_language" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_programming_language__record" ON "schema_software_application__schema_programming_language" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_provider" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_provider__record" ON "schema_software_application__schema_provider" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_software_add_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_software_add_on__record" ON "schema_software_application__schema_software_add_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_software_help" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_software_help__record" ON "schema_software_application__schema_software_help" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_software_version" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_software_version__record" ON "schema_software_application__schema_software_version" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page__record" ON "schema_web_page" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_web_page" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page__schema_about__record" ON "schema_web_page__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_web_page" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page__schema_has_part__record" ON "schema_web_page__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "statements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "property" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "property", "value", "term")
);
CREATE INDEX IF NOT EXISTS "statements__record" ON "statements" ("record");
