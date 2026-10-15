CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol" (
"iri" TEXT,
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
  CONSTRAINT bioschemas_draft_lab_protocol_pk PRIMARY KEY ("iri")
);

CREATE TABLE IF NOT EXISTS "bioschemas_draft_lab_protocol__values" (
"iri" TEXT,
  "field" TEXT,
  "value" TEXT,
  "term" TEXT
);

CREATE INDEX IF NOT EXISTS "bioschemas_draft_lab_protocol__values__iri" ON "bioschemas_draft_lab_protocol__values" (iri);

CREATE TABLE IF NOT EXISTS "schema_organization" (
"iri" TEXT,
  "type" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  "schema_url" TEXT,
  "schema_url__term" TEXT,
  CONSTRAINT schema_organization_pk PRIMARY KEY ("iri")
);

CREATE TABLE IF NOT EXISTS "schema_organization__values" (
"iri" TEXT,
  "field" TEXT,
  "value" TEXT,
  "term" TEXT
);

CREATE INDEX IF NOT EXISTS "schema_organization__values__iri" ON "schema_organization__values" (iri);

CREATE TABLE IF NOT EXISTS "schema_person" (
"iri" TEXT,
  "type" TEXT,
  "schema_email" TEXT,
  "schema_email__term" TEXT,
  "schema_name" TEXT,
  "schema_name__term" TEXT,
  CONSTRAINT schema_person_pk PRIMARY KEY ("iri")
);

CREATE TABLE IF NOT EXISTS "schema_person__values" (
"iri" TEXT,
  "field" TEXT,
  "value" TEXT,
  "term" TEXT
);

CREATE INDEX IF NOT EXISTS "schema_person__values__iri" ON "schema_person__values" (iri);

CREATE TABLE IF NOT EXISTS "schema_software_application" (
"iri" TEXT,
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
  CONSTRAINT schema_software_application_pk PRIMARY KEY ("iri")
);

CREATE TABLE IF NOT EXISTS "schema_software_application__values" (
"iri" TEXT,
  "field" TEXT,
  "value" TEXT,
  "term" TEXT
);

CREATE INDEX IF NOT EXISTS "schema_software_application__values__iri" ON "schema_software_application__values" (iri);

CREATE TABLE IF NOT EXISTS "statements" (
"iri" TEXT,
  "property" TEXT,
  "value" TEXT,
  "term" TEXT
);

CREATE INDEX IF NOT EXISTS "statements__iri" ON "statements" (iri);
