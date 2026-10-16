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
CREATE TABLE IF NOT EXISTS "schema_dataset__schema_source_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_dataset" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_dataset__schema_source_organization__record" ON "schema_dataset__schema_source_organization" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_defined_term_set" (
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
CREATE INDEX IF NOT EXISTS "schema_defined_term_set__record" ON "schema_defined_term_set" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_creative_work_status" TEXT,
  "schema_creative_work_status__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_position" TEXT,
  "schema_position__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__record" ON "schema_how_to_section" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to_section" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__schema_about__record" ON "schema_how_to_section__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to_section" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__schema_has_part__record" ON "schema_how_to_section__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section__schema_step" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to_section" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__schema_step__record" ON "schema_how_to_section__schema_step" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section__schema_supply" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to_section" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__schema_supply__record" ON "schema_how_to_section__schema_supply" ("record");
CREATE TABLE IF NOT EXISTS "schema_how_to_section__schema_tool" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_how_to_section" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_how_to_section__schema_tool__record" ON "schema_how_to_section__schema_tool" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__record" ON "schema_organization" ("record");
CREATE TABLE IF NOT EXISTS "schema_organization__schema_same_as" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_organization" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_organization__schema_same_as__record" ON "schema_organization__schema_same_as" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_question" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
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
CREATE INDEX IF NOT EXISTS "schema_question__record" ON "schema_question" ("record");
CREATE TABLE IF NOT EXISTS "schema_question__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_question" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_question__schema_has_part__record" ON "schema_question__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_question__schema_step" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_question" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_question__schema_step__record" ON "schema_question__schema_step" ("record");
CREATE TABLE IF NOT EXISTS "schema_question__schema_supply" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_question" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_question__schema_supply__record" ON "schema_question__schema_supply" ("record");
CREATE TABLE IF NOT EXISTS "schema_question__schema_tool" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_question" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_question__schema_tool__record" ON "schema_question__schema_tool" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_abstract" TEXT,
  "schema_abstract__term" TEXT,
  "schema_description" TEXT,
  "schema_description__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__record" ON "schema_research_project" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__glossary_vhp0000151" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__glossary_vhp0000151__record" ON "schema_research_project__glossary_vhp0000151" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_about" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_about__record" ON "schema_research_project__schema_about" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_has_part" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_has_part__record" ON "schema_research_project__schema_has_part" ("record");
CREATE TABLE IF NOT EXISTS "schema_research_project__schema_keywords" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "value", "term"),
  FOREIGN KEY ("iri") REFERENCES "schema_research_project" ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_research_project__schema_keywords__record" ON "schema_research_project__schema_keywords" ("record");
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
CREATE TABLE IF NOT EXISTS "schema_video_object" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
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
  "schema_identifier" TEXT,
  "schema_identifier__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_position" TEXT,
  "schema_position__term" TEXT,
  "schema_text" TEXT,
  "schema_text__term" TEXT,
  PRIMARY KEY ("iri")
);
CREATE INDEX IF NOT EXISTS "schema_web_page_element__record" ON "schema_web_page_element" ("record");
CREATE TABLE IF NOT EXISTS "statements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "property" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "property", "value", "term")
);
CREATE INDEX IF NOT EXISTS "statements__record" ON "statements" ("record");
