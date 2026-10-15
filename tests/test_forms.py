"""The editor's form, read from the SHACL shapes of the model and the application profile."""

from linkeddata import forms


def test_the_form_of_tools():
    fields = forms.form("https://schema.org/SoftwareApplication")
    found = [(field["name"], field["label"], field["entry"], field["required"]) for field in fields]
    assert found[:6] == [
        ("name", "Name", "text", True),
        ("description", "Description", "long text", True),
        ("url", "Website", "address", False),
        ("installUrl", "Where to use it", "address", False),
        ("image", "Logo or screenshot", "image", False),
        ("about", "Assessment steps and case-study questions", "links", False),
    ]
    by_name = {field["name"]: field for field in fields}
    assert by_name["maintainer"]["section"] == "Who is behind it"
    assert by_name["softwareHelp"]["entry"] == "details"
    assert by_name["creativeWorkStatus"]["entry"] == "select"
    assert fields[0]["message"] == "Give the tool a name."
    assert by_name["citation"]["pattern"].startswith("^https://doi")
    assert by_name["dct:conformsTo"]["fixed"] == ["https://bioschemas.org/profiles/ComputationalTool/1.0-RELEASE"]
    for field in fields:
        assert field["help"], field["name"]


def test_fields_the_profile_leaves_out_are_explained_by_the_vocabulary():
    fields = {field["name"]: field for field in forms.form("https://schema.org/Question")}
    assert fields["citation"]["help"].startswith("A citation or reference to another creative work")


def test_names_and_descriptions_from_the_vocabulary():
    assert forms.readable("conformsTo") == "Conforms to"
    assert forms.plain("This can be a [[URL]] or a fully described [[ImageObject]].") == "This can be a URL or a fully described ImageObject."
