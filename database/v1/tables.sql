CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_alternate_name" TEXT,
  "schema_alternate_name__term" TEXT,
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
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__record" ON "bioschemas_draft_lab_protocol" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__dct_conforms_to" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__dct_conforms_to__record" ON "bioschemas_draft_lab_protocol__dct_conforms_to" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__glossary_vhp0000151__record" ON "bioschemas_draft_lab_protocol__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__glossary_vhp0000152" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__glossary_vhp0000152__record" ON "bioschemas_draft_lab_protocol__glossary_vhp0000152" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_about__record" ON "bioschemas_draft_lab_protocol__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_additional_type" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_additional_type__record" ON "bioschemas_draft_lab_protocol__schema_additional_type" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_citation__record" ON "bioschemas_draft_lab_protocol__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_creator__record" ON "bioschemas_draft_lab_protocol__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_is_based_on__record" ON "bioschemas_draft_lab_protocol__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_provider" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_provider__record" ON "bioschemas_draft_lab_protocol__schema_provider" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_subject_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_lab_protocol" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__schema_subject_of__record" ON "bioschemas_draft_lab_protocol__schema_subject_of" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__record" ON "bioschemas_draft_study" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__glossary_vhp0000151__record" ON "bioschemas_draft_study__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_about__record" ON "bioschemas_draft_study__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_has_part__record" ON "bioschemas_draft_study__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_draft_study__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "bioschemas_draft_study" ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_draft_study__schema_keywords__record" ON "bioschemas_draft_study__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "bioschemas_formal_parameter" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "bioschemas_formal_parameter__record" ON "bioschemas_formal_parameter" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_biological_system" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_anatomical_assumptions" TEXT,
  "pbpk_anatomical_assumptions__term" TEXT,
  "pbpk_physiological_scope" TEXT,
  "pbpk_physiological_scope__term" TEXT,
  "pbpk_population_description" TEXT,
  "pbpk_population_description__term" TEXT,
  "pbpk_species" TEXT,
  "pbpk_species__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_biological_system__record" ON "pbpk_biological_system" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_biological_system__pbpk_compartments" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_biological_system" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_biological_system__pbpk_compartments__record" ON "pbpk_biological_system__pbpk_compartments" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_biological_system__pbpk_life_stage" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_biological_system" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_biological_system__pbpk_life_stage__record" ON "pbpk_biological_system__pbpk_life_stage" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_calibration" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_calibration_data" TEXT,
  "pbpk_calibration_data__term" TEXT,
  "pbpk_method" TEXT,
  "pbpk_method__term" TEXT,
  "pbpk_notes" TEXT,
  "pbpk_notes__term" TEXT,
  "pbpk_optimization_criteria" TEXT,
  "pbpk_optimization_criteria__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_calibration__record" ON "pbpk_calibration" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_calibration__pbpk_calibrated_parameters" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_calibration" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_calibration__pbpk_calibrated_parameters__record" ON "pbpk_calibration__pbpk_calibrated_parameters" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_compartment" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_biological_reference" TEXT,
  "pbpk_biological_reference__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_compartment__record" ON "pbpk_compartment" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_connection" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_connection_type" TEXT,
  "pbpk_connection_type__term" TEXT,
  "pbpk_source_compartment" TEXT,
  "pbpk_source_compartment__term" TEXT,
  "pbpk_target_compartment" TEXT,
  "pbpk_target_compartment__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_connection__record" ON "pbpk_connection" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_evaluation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_evaluation_data" TEXT,
  "pbpk_evaluation_data__term" TEXT,
  "pbpk_limitations" TEXT,
  "pbpk_limitations__term" TEXT,
  "pbpk_method" TEXT,
  "pbpk_method__term" TEXT,
  "pbpk_outcome" TEXT,
  "pbpk_outcome__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_evaluation__record" ON "pbpk_evaluation" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_evaluation__pbpk_performance_metrics" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_evaluation" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_evaluation__pbpk_performance_metrics__record" ON "pbpk_evaluation__pbpk_performance_metrics" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_implementation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_implementation_location" TEXT,
  "pbpk_implementation_location__term" TEXT,
  "pbpk_implementation_type" TEXT,
  "pbpk_implementation_type__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_implementation__record" ON "pbpk_implementation" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_parameter" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_notes" TEXT,
  "pbpk_notes__term" TEXT,
  "pbpk_parameter_category" TEXT,
  "pbpk_parameter_category__term" TEXT,
  "pbpk_parameter_source" TEXT,
  "pbpk_parameter_source__term" TEXT,
  "pbpk_scope" TEXT,
  "pbpk_scope__term" TEXT,
  "pbpk_source_reference" TEXT,
  "pbpk_source_reference__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_unit_text" TEXT,
  "schema_unit_text__term" TEXT,
  "schema_value" TEXT,
  "schema_value__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_parameter__record" ON "pbpk_parameter" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_chemicals" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_chemicals__record" ON "pbpk_parameter__pbpk_applies_to_chemicals" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_compartments" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_compartments__record" ON "pbpk_parameter__pbpk_applies_to_compartments" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_species" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_parameter" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_parameter__pbpk_applies_to_species__record" ON "pbpk_parameter__pbpk_applies_to_species" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_performance_metric" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_interpretation" TEXT,
  "pbpk_interpretation__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_value" TEXT,
  "schema_value__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_performance_metric__record" ON "pbpk_performance_metric" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_suv_analysis" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_analysis_type" TEXT,
  "pbpk_analysis_type__term" TEXT,
  "pbpk_method" TEXT,
  "pbpk_method__term" TEXT,
  "pbpk_notes" TEXT,
  "pbpk_notes__term" TEXT,
  "pbpk_outcome" TEXT,
  "pbpk_outcome__term" TEXT,
  "pbpk_robustness_interpretation" TEXT,
  "pbpk_robustness_interpretation__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_suv_analysis__record" ON "pbpk_suv_analysis" ("record");
CREATE TABLE IF NOT EXISTS "pbpk_suv_analysis__pbpk_analyzed_parameters" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "pbpk_suv_analysis" ("iri")
);
CREATE INDEX IF NOT EXISTS "pbpk_suv_analysis__pbpk_analyzed_parameters__record" ON "pbpk_suv_analysis__pbpk_analyzed_parameters" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_data_catalog" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_alternate_name" TEXT,
  "schema_alternate_name__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_publisher" TEXT,
  "schema_publisher__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__record" ON "schema_data_catalog" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__schema_subject_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__schema_subject_of__record" ON "schema_data_catalog__schema_subject_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_data_catalog__void_class_partition" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_data_catalog" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_data_catalog__void_class_partition__record" ON "schema_data_catalog__void_class_partition" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
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
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__record" ON "schema_dataset" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__glossary_vhp0000151__record" ON "schema_dataset__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__glossary_vhp0000152" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__glossary_vhp0000152__record" ON "schema_dataset__glossary_vhp0000152" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_about__record" ON "schema_dataset__schema_about" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_is_part_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_is_part_of__record" ON "schema_dataset__schema_is_part_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_keywords__record" ON "schema_dataset__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_measurement_method" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_measurement_method__record" ON "schema_dataset__schema_measurement_method" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_measurement_technique" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_measurement_technique__record" ON "schema_dataset__schema_measurement_technique" ("record");
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_same_as__record" ON "schema_dataset__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_in_defined_term_set" TEXT,
  "schema_in_defined_term_set__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_term_code" TEXT,
  "schema_term_code__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__record" ON "schema_defined_term" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__schema_alternate_name__record" ON "schema_defined_term__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term__schema_same_as__record" ON "schema_defined_term__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "void_uri_space" TEXT,
  "void_uri_space__term" TEXT,
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
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__record" ON "schema_defined_term_set" ("record");
CREATE TABLE IF NOT EXISTS "schema_defined_term_set__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_defined_term_set" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__schema_same_as__record" ON "schema_defined_term_set__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_additional_type" TEXT,
  "schema_additional_type__term" TEXT,
  "schema_creative_work_status" TEXT,
  "schema_creative_work_status__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_headline" TEXT,
  "schema_headline__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_position" TEXT,
  "schema_position__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__record" ON "schema_how_to" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__bioschemas_input" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__bioschemas_input__record" ON "schema_how_to__bioschemas_input" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__bioschemas_output" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__bioschemas_output__record" ON "schema_how_to__bioschemas_output" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__schema_has_part__record" ON "schema_how_to__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__schema_step" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__schema_step__record" ON "schema_how_to__schema_step" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__schema_supply" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__schema_supply__record" ON "schema_how_to__schema_supply" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to__schema_tool" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to__schema_tool__record" ON "schema_how_to__schema_tool" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_supply" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_item" TEXT,
  "schema_item__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_supply__record" ON "schema_how_to_supply" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_tool" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_item" TEXT,
  "schema_item__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_tool__record" ON "schema_how_to_tool" ("record");
CREATE TABLE IF NOT EXISTS "schema_image_object" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_caption" TEXT,
  "schema_caption__term" TEXT,
  "schema_content_url" TEXT,
  "schema_content_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_image_object__record" ON "schema_image_object" ("record");
CREATE TABLE IF NOT EXISTS "schema_media_object" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_artifact_location" TEXT,
  "pbpk_artifact_location__term" TEXT,
  "pbpk_artifact_type" TEXT,
  "pbpk_artifact_type__term" TEXT,
  "schema_encoding_format" TEXT,
  "schema_encoding_format__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_media_object__record" ON "schema_media_object" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "pbpk_chemical_role" TEXT,
  "pbpk_chemical_role__term" TEXT,
  "pbpk_physicochemical_notes" TEXT,
  "pbpk_physicochemical_notes__term" TEXT,
  "schema_molecular_weight" TEXT,
  "schema_molecular_weight__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__record" ON "schema_molecular_entity" ("record");
CREATE TABLE IF NOT EXISTS "schema_molecular_entity__schema_identifier" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_molecular_entity" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_molecular_entity__schema_identifier__record" ON "schema_molecular_entity__schema_identifier" ("record");
CREATE TABLE IF NOT EXISTS "schema_monetary_amount" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_currency" TEXT,
  "schema_currency__term" TEXT,
  "schema_value" TEXT,
  "schema_value__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_monetary_amount__record" ON "schema_monetary_amount" ("record");
CREATE TABLE IF NOT EXISTS "schema_monetary_grant" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
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
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_disambiguating_description" TEXT,
  "schema_disambiguating_description__term" TEXT,
  "schema_email" TEXT,
  "schema_email__term" TEXT,
  "schema_logo" TEXT,
  "schema_logo__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__record" ON "schema_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_alternate_name__record" ON "schema_organization__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_same_as__record" ON "schema_organization__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization_role" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_member" TEXT,
  "schema_member__term" TEXT,
  "schema_role_name" TEXT,
  "schema_role_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization_role__record" ON "schema_organization_role" ("record");
CREATE TABLE IF NOT EXISTS "schema_periodical" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_periodical__record" ON "schema_periodical" ("record");
CREATE TABLE IF NOT EXISTS "schema_periodical__schema_issn" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_periodical" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_periodical__schema_issn__record" ON "schema_periodical__schema_issn" ("record");
CREATE TABLE IF NOT EXISTS "schema_person" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_email" TEXT,
  "schema_email__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__record" ON "schema_person" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_affiliation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_affiliation__record" ON "schema_person__schema_affiliation" ("record");
CREATE TABLE IF NOT EXISTS "schema_person__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_person" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_person__schema_same_as__record" ON "schema_person__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_property_value" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_property_id" TEXT,
  "schema_property_id__term" TEXT,
  "schema_value" TEXT,
  "schema_value__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_property_value__record" ON "schema_property_value" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_disambiguating_description" TEXT,
  "schema_disambiguating_description__term" TEXT,
  "schema_email" TEXT,
  "schema_email__term" TEXT,
  "schema_logo" TEXT,
  "schema_logo__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__record" ON "schema_research_project" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_alternate_name" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_alternate_name__record" ON "schema_research_project__schema_alternate_name" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_funder" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_funder__record" ON "schema_research_project__schema_funder" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_funding" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_funding__record" ON "schema_research_project__schema_funding" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_image" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_image__record" ON "schema_research_project__schema_image" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_member" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_member__record" ON "schema_research_project__schema_member" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_same_as__record" ON "schema_research_project__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_sub_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_sub_organization__record" ON "schema_research_project__schema_sub_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_subject_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_subject_of__record" ON "schema_research_project__schema_subject_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_date_published" TEXT,
  "schema_date_published__term" TEXT,
  "schema_is_part_of" TEXT,
  "schema_is_part_of__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__record" ON "schema_scholarly_article" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_author" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_author__record" ON "schema_scholarly_article__schema_author" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_funding" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_funding__record" ON "schema_scholarly_article__schema_funding" ("record");
CREATE TABLE IF NOT EXISTS "schema_scholarly_article__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_scholarly_article" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_scholarly_article__schema_same_as__record" ON "schema_scholarly_article__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_citation" TEXT,
  "schema_citation__term" TEXT,
  "schema_creative_work_status" TEXT,
  "schema_creative_work_status__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_image" TEXT,
  "schema_image__term" TEXT,
  "schema_install_url" TEXT,
  "schema_install_url__term" TEXT,
  "schema_keywords" TEXT,
  "schema_keywords__term" TEXT,
  "schema_license" TEXT,
  "schema_license__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_release_notes" TEXT,
  "schema_release_notes__term" TEXT,
  "schema_software_version" TEXT,
  "schema_software_version__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__record" ON "schema_software_application" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__dct_conforms_to" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__dct_conforms_to__record" ON "schema_software_application__dct_conforms_to" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__glossary_vhp0000151__record" ON "schema_software_application__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__glossary_vhp0000152" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__glossary_vhp0000152__record" ON "schema_software_application__glossary_vhp0000152" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_about__record" ON "schema_software_application__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_creator__record" ON "schema_software_application__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_download_url" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_download_url__record" ON "schema_software_application__schema_download_url" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_is_based_on" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_is_based_on__record" ON "schema_software_application__schema_is_based_on" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_maintainer" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_maintainer__record" ON "schema_software_application__schema_maintainer" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_provider" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_provider__record" ON "schema_software_application__schema_provider" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_same_as__record" ON "schema_software_application__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_software_help" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_software_help__record" ON "schema_software_application__schema_software_help" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_subject_of" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_subject_of__record" ON "schema_software_application__schema_subject_of" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_application__schema_video" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_application" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_application__schema_video__record" ON "schema_software_application__schema_video" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code" (
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
  "schema_version" TEXT,
  "schema_version__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__record" ON "schema_software_source_code" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__glossary_vhp0000151__record" ON "schema_software_source_code__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__glossary_vhp0000152" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__glossary_vhp0000152__record" ON "schema_software_source_code__glossary_vhp0000152" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_connections" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_connections__record" ON "schema_software_source_code__pbpk_connections" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_biological_system" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_biological_system__record" ON "schema_software_source_code__pbpk_has_biological_system" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_calibration" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_calibration__record" ON "schema_software_source_code__pbpk_has_calibration" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_chemical" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_chemical__record" ON "schema_software_source_code__pbpk_has_chemical" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_evaluation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_evaluation__record" ON "schema_software_source_code__pbpk_has_evaluation" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_parameter" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_parameter__record" ON "schema_software_source_code__pbpk_has_parameter" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_has_suv_analysis" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_has_suv_analysis__record" ON "schema_software_source_code__pbpk_has_suv_analysis" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_implementation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_implementation__record" ON "schema_software_source_code__pbpk_implementation" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__pbpk_structural_compartments" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__pbpk_structural_compartments__record" ON "schema_software_source_code__pbpk_structural_compartments" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_about__record" ON "schema_software_source_code__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_citation" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_citation__record" ON "schema_software_source_code__schema_citation" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_code_repository" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_code_repository__record" ON "schema_software_source_code__schema_code_repository" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_contributor" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_contributor__record" ON "schema_software_source_code__schema_contributor" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_creator" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_creator__record" ON "schema_software_source_code__schema_creator" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_funding" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_funding__record" ON "schema_software_source_code__schema_funding" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_has_part__record" ON "schema_software_source_code__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_keywords__record" ON "schema_software_source_code__schema_keywords" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_programming_language" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_programming_language__record" ON "schema_software_source_code__schema_programming_language" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_runtime_platform" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_runtime_platform__record" ON "schema_software_source_code__schema_runtime_platform" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_same_as__record" ON "schema_software_source_code__schema_same_as" ("record");
CREATE TABLE IF NOT EXISTS "schema_software_source_code__schema_software_requirements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_software_source_code" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_software_source_code__schema_software_requirements__record" ON "schema_software_source_code__schema_software_requirements" ("record");
CREATE TABLE IF NOT EXISTS "schema_video_object" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_embed_url" TEXT,
  "schema_embed_url__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_video_object__record" ON "schema_video_object" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_web_page_element" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_about" TEXT,
  "schema_about__term" TEXT,
  "schema_creative_work_status" TEXT,
  "schema_creative_work_status__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_position" TEXT,
  "schema_position__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page_element__record" ON "schema_web_page_element" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page_element__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_web_page_element" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page_element__schema_has_part__record" ON "schema_web_page_element__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page_element__schema_image" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_web_page_element" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page_element__schema_image__record" ON "schema_web_page_element__schema_image" ("record");
CREATE TABLE IF NOT EXISTS "schema_web_page_element__schema_video" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_web_page_element" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page_element__schema_video__record" ON "schema_web_page_element__schema_video" ("record");
CREATE TABLE IF NOT EXISTS "statements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "property" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "property", "value", "term")
);
CREATE INDEX IF NOT EXISTS "statements__record" ON "statements" ("record");
