CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "type" TEXT,
  "bioschemas_draft_reagent" TEXT,
  "bioschemas_draft_reagent__term" TEXT,
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
CREATE TABLE IF NOT EXISTS "statements" (
  "record" TEXT NOT NULL,
  "iri" TEXT NOT NULL,
  "property" TEXT NOT NULL,
  "value" TEXT NOT NULL,
  "term" TEXT NOT NULL,
  PRIMARY KEY ("iri", "property", "value", "term")
);
CREATE INDEX IF NOT EXISTS "statements__record" ON "statements" ("record");
