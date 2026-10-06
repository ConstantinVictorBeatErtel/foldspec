import hashlib
import json

import pytest

from services.api import cad
from services.api.cad import build_part, default_spec, export_build
from services.api.models import TemplateId


@pytest.mark.parametrize("template", list(TemplateId))
def test_default_recipes_build_as_one_valid_solid(template):
    part, _ = build_part(default_spec(template))
    assert part.val().isValid()
    assert len(part.val().Solids()) == 1


@pytest.mark.parametrize("template", list(TemplateId))
def test_one_face_local_hole_is_cut_from_each_recipe(template):
    spec = default_spec(template)
    p = spec.parameters
    x = 0 if template == TemplateId.ROUND_PLATE else (p.get("length") or p.get("base_length") or p.get("base_width")) / 2
    y = 0 if template == TemplateId.ROUND_PLATE else (p.get("width") or p.get("length")) / 2
    spec.holes = [{"x": x, "y": y, "diameter": 6.5}]
    plain_spec = default_spec(template)
    plain_spec.holes = []
    plain, _ = build_part(plain_spec)
    perforated, features = build_part(spec)
    assert perforated.val().isValid()
    assert len(perforated.val().Solids()) == 1
    assert perforated.val().Volume() < plain.val().Volume()
    assert any(feature.id == "hole:1" for feature in features)


def test_feature_outside_supported_face_is_rejected():
    spec = default_spec(TemplateId.RECT_PLATE)
    spec.holes = [{"x": 119, "y": 35, "diameter": 6.5}]
    with pytest.raises(ValueError, match="does not fit"):
        build_part(spec)


def test_export_package_contains_step_hashes_and_experimental_label(tmp_path, monkeypatch):
    monkeypatch.setattr(cad, "DATA_DIR", tmp_path)
    result = export_build(default_spec(TemplateId.L_BRACKET))
    assert result.geometry_status == "valid"
    assert result.evidence_status == "experimental"
    package = tmp_path / "builds" / result.glb_url.split("/")[-2] / "foldspec-package.zip"
    assert package.is_file()
    import zipfile

    with zipfile.ZipFile(package) as archive:
        assert {"part.step", "dimensions.pdf", "specification.json", "validation.json", "manifest.json"}.issubset(archive.namelist())
        manifest = json.loads(archive.read("manifest.json"))
        assert manifest["evidence_status"] == "experimental"
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read(entry["name"])).hexdigest() == entry["sha256"]
