from services.api import store
from services.api.cad import default_spec
from services.api.models import Project, TemplateId


def test_revision_specs_are_immutable_and_restore_is_a_new_revision(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DB_PATH", tmp_path / "foldspec.sqlite3")
    store.initialize()
    project = Project(name="Plate", spec=default_spec(TemplateId.RECT_PLATE))
    store.save(project)

    changed = default_spec(TemplateId.RECT_PLATE)
    changed.parameters["width"] = 90
    project.spec = changed
    store.save(project, new_revision=True)
    project.conversation.append({"role": "assistant", "content": "proposal"})
    store.save(project)

    rev1 = store.get_revision(project.id, 1)
    assert rev1 is not None
    assert rev1.spec.parameters["width"] == 70
    assert store.get_revision(project.id, 2).spec.parameters["width"] == 90

    restored = store.get_revision(project.id, 1)
    assert restored is not None
    project.spec = restored.spec
    store.save(project, new_revision=True)
    assert project.revision == 3
    assert store.get_revision(project.id, 3).spec.parameters["width"] == 70
